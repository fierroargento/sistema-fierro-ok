"""Confirma planes CRM firmados con una única transacción interna."""

import hashlib
import json


def deserializar_plan(documento):
    try:
        resultado = json.loads(documento.decode("utf-8-sig") if isinstance(documento, bytes) else documento)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
        raise ValueError("El plan CRM no es un JSON UTF-8 válido.") from error
    if not isinstance(resultado.get("filas"), list) or not 1 <= len(resultado["filas"]) <= 1000:
        raise ValueError("El plan CRM no contiene filas válidas.")
    return resultado


def _huella_plan(resultado):
    base = {clave: valor for clave, valor in resultado.items() if clave != "huella_plan"}
    return hashlib.sha256(json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def validar_confirmacion(resultado, *, organizacion_id, unidades, etapas, clientes, identidades, lotes):
    """Revalida todo antes de construir cualquier modelo mutable."""
    if resultado.get("organizacion_id") != organizacion_id or resultado.get("modo") != "offline":
        raise ValueError("El plan no pertenece al tenant activo.")
    if resultado.get("confirmacion_habilitada") is not False or resultado.get("automatizaciones") is not False:
        raise ValueError("El contrato desconectado del plan fue alterado.")
    if resultado.get("huella_plan") != _huella_plan(resultado):
        raise ValueError("La firma del plan CRM no coincide.")
    if any(x.organizacion_id == organizacion_id and x.huella_documento == resultado.get("huella_documento") for x in lotes):
        raise ValueError("Este archivo CRM ya fue confirmado.")
    unidad_ids = {x.id for x in unidades if x.organizacion_id == organizacion_id}
    etapa_ids = {x.id for x in etapas if x.organizacion_id == organizacion_id}
    codigos = {str(x.codigo).strip().lower() for x in clientes if x.organizacion_id == organizacion_id}
    identidades_vistas = {
        (str(x.canal).strip().lower(), str(x.identificador_externo).strip())
        for x in identidades if x.organizacion_id == organizacion_id
    }
    nuevos = set()
    referencias = set()
    permitidos = {
        "cliente": {"potencial", "cliente", "inactivo"},
        "oportunidad": {"abierta", "ganada", "perdida", "cancelada"},
        "actividad": {"pendiente", "completada", "cancelada"},
    }
    for fila in resultado["filas"]:
        tipo = fila.get("tipo")
        codigo = str(fila.get("codigo_cliente") or "").strip().lower()
        if tipo not in permitidos or fila.get("resultado") != "preparado" or fila.get("errores"):
            raise ValueError("El plan contiene filas rechazadas o tipos inválidos.")
        if not codigo or not str(fila.get("nombre") or "").strip():
            raise ValueError("Una fila perdió sus campos obligatorios.")
        if fila.get("unidad_negocio_id") is not None and fila["unidad_negocio_id"] not in unidad_ids:
            raise ValueError("Una unidad de negocio quedó fuera del tenant.")
        if fila.get("estado") not in permitidos[tipo]:
            raise ValueError("Un estado CRM fue alterado.")
        if tipo == "cliente":
            if codigo in codigos or codigo in nuevos:
                raise ValueError("Un código de cliente ya existe o está duplicado.")
            nuevos.add(codigo)
        elif codigo not in codigos | nuevos:
            raise ValueError("Una fila referencia un cliente inexistente.")
        canal = str(fila.get("canal") or "").strip().lower()
        identidad = str(fila.get("identificador_externo") or "").strip()
        if bool(canal) != bool(identidad):
            raise ValueError("Una identidad externa está incompleta.")
        if canal:
            clave = (canal, identidad)
            if clave in identidades_vistas:
                raise ValueError("Una identidad externa ya existe o está duplicada.")
            identidades_vistas.add(clave)
        if tipo == "oportunidad":
            referencia = str(fila.get("referencia") or "").strip()
            if not referencia or referencia in referencias:
                raise ValueError("Una referencia de oportunidad está duplicada.")
            referencias.add(referencia)
            if fila.get("etapa_crm_id") is not None and fila["etapa_crm_id"] not in etapa_ids:
                raise ValueError("Una etapa CRM quedó fuera del tenant.")
            if not isinstance(fila.get("importe_estimado_centavos"), int) or fila["importe_estimado_centavos"] < 0:
                raise ValueError("Un importe estimado fue alterado.")
            if not isinstance(fila.get("probabilidad"), int) or not 0 <= fila["probabilidad"] <= 100:
                raise ValueError("Una probabilidad fue alterada.")
    return resultado


def confirmar_importacion(resultado, *, organizacion_id, usuario, nombre_archivo, clientes_existentes, modelos, db_session):
    """Crea clientes y su seguimiento interno; nunca importa pedidos ni contacta canales."""
    ClienteCRM = modelos["ClienteCRM"]
    ClienteIdentidadCanal = modelos["ClienteIdentidadCanal"]
    OportunidadCRM = modelos["OportunidadCRM"]
    ActividadCRM = modelos["ActividadCRM"]
    LoteImportacionCRM = modelos["LoteImportacionCRM"]
    clientes_por_codigo = {
        str(cliente.codigo).strip().lower(): cliente
        for cliente in clientes_existentes
        if cliente.organizacion_id == organizacion_id
    }
    clientes_nuevos = []
    identidades_nuevas = []
    oportunidades_nuevas = []
    actividades_pendientes = []

    for fila in resultado["filas"]:
        codigo = str(fila["codigo_cliente"]).strip()
        if fila["tipo"] == "cliente":
            cliente = ClienteCRM(
                organizacion_id=organizacion_id,
                unidad_negocio_id=fila.get("unidad_negocio_id"),
                codigo=codigo,
                nombre=fila["nombre"],
                documento=fila.get("documento") or None,
                email=fila.get("email") or None,
                telefono=fila.get("telefono") or None,
                observaciones=fila.get("detalle") or None,
                estado=fila["estado"],
                activo=False,
            )
            clientes_por_codigo[codigo.lower()] = cliente
            clientes_nuevos.append(cliente)
            if fila.get("canal"):
                identidades_nuevas.append(ClienteIdentidadCanal(
                    organizacion_id=organizacion_id,
                    cliente=cliente,
                    canal=fila["canal"],
                    identificador_externo=fila["identificador_externo"],
                    activo=False,
                ))

    for fila in resultado["filas"]:
        if fila["tipo"] == "cliente":
            continue
        cliente = clientes_por_codigo.get(str(fila["codigo_cliente"]).strip().lower())
        if cliente is None:
            raise ValueError("La confirmación solo admite relaciones con clientes del mismo archivo.")
        if fila["tipo"] == "oportunidad":
            oportunidad = OportunidadCRM(
                organizacion_id=organizacion_id,
                cliente=cliente,
                unidad_negocio_id=fila.get("unidad_negocio_id"),
                etapa_crm_id=fila.get("etapa_crm_id"),
                titulo=fila["nombre"],
                estado=fila["estado"],
                importe_estimado_centavos=fila["importe_estimado_centavos"],
                probabilidad=fila["probabilidad"],
                detalle=fila.get("detalle") or None,
                activa=False,
            )
            oportunidades_nuevas.append(oportunidad)
        else:
            actividades_pendientes.append((fila, cliente))

    actividades_nuevas = [
        ActividadCRM(
            organizacion_id=organizacion_id,
            cliente=cliente,
            tipo="nota",
            asunto=fila["nombre"],
            detalle=fila.get("detalle") or None,
            estado=fila["estado"],
            creado_por=getattr(usuario, "username", None) or "admin",
        )
        for fila, cliente in actividades_pendientes
    ]
    lote = LoteImportacionCRM(
        organizacion_id=organizacion_id,
        nombre_archivo=(nombre_archivo or "plan_crm.json")[:255],
        huella_documento=resultado["huella_documento"],
        huella_plan=resultado["huella_plan"],
        estado="confirmado",
        clientes_creados=len(clientes_nuevos),
        identidades_creadas=len(identidades_nuevas),
        oportunidades_creadas=len(oportunidades_nuevas),
        actividades_creadas=len(actividades_nuevas),
        evidencia_json=json.dumps(resultado, ensure_ascii=False, sort_keys=True),
        automatizaciones=False,
        creado_por_usuario_id=getattr(usuario, "id", None),
        creado_por_username=getattr(usuario, "username", None) or "admin",
    )
    db_session.add_all(clientes_nuevos + identidades_nuevas + oportunidades_nuevas + actividades_nuevas + [lote])
    db_session.commit()
    return lote
