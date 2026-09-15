"""Certificación integral del subsistema fiscal sin emitir comprobantes."""

import hashlib
import io
import json


def certificar_facturacion(*, organizacion_id, modulo, entidades, configuraciones, puntos, tipos, borradores, eventos):
    entidades = [x for x in (entidades or []) if x.organizacion_id == organizacion_id]
    configuraciones = [x for x in (configuraciones or []) if x.organizacion_id == organizacion_id]
    puntos = [x for x in (puntos or []) if x.organizacion_id == organizacion_id]
    borradores = [x for x in (borradores or []) if x.organizacion_id == organizacion_id]
    eventos = [x for x in (eventos or []) if x.organizacion_id == organizacion_id]
    entidad_ids = {x.id for x in entidades}
    configuracion_ids = {x.id for x in configuraciones}
    punto_ids = {x.id for x in puntos}
    hallazgos = []

    def agregar(nivel, codigo, entidad, identificador, detalle):
        hallazgos.append({"nivel": nivel, "codigo": codigo, "entidad": entidad, "id": identificador, "detalle": detalle})

    cuit_vistos = set()
    for entidad in entidades:
        cuit = "".join(caracter for caracter in str(entidad.cuit or "") if caracter.isdigit())
        if len(cuit) != 11:
            agregar("bloqueo", "cuit_invalido", "entidad_fiscal", entidad.id, "El CUIT debe contener 11 dígitos.")
        elif cuit in cuit_vistos:
            agregar("bloqueo", "cuit_duplicado", "entidad_fiscal", entidad.id, "El CUIT está repetido.")
        cuit_vistos.add(cuit)
        if entidad.facturacion_habilitada and not entidad.activa:
            agregar("bloqueo", "entidad_inactiva", "entidad_fiscal", entidad.id, "La facturación no puede habilitarse sobre una entidad inactiva.")

    configuraciones_por_entidad = {}
    for configuracion in configuraciones:
        configuraciones_por_entidad.setdefault(configuracion.entidad_fiscal_id, []).append(configuracion)
        if configuracion.entidad_fiscal_id not in entidad_ids:
            agregar("bloqueo", "configuracion_ajena", "configuracion_fiscal", configuracion.id, "La entidad fiscal no pertenece al tenant.")
        if configuracion.ambiente not in {"homologacion", "produccion"}:
            agregar("bloqueo", "ambiente_invalido", "configuracion_fiscal", configuracion.id, "El ambiente fiscal es inválido.")
        valores = (configuracion.certificado_env, configuracion.clave_privada_env, configuracion.token_env)
        if any(valor and ("BEGIN " in valor or " " in valor) for valor in valores):
            agregar("bloqueo", "secreto_persistido", "configuracion_fiscal", configuracion.id, "Solo deben guardarse nombres de variables de entorno.")
    for entidad_id, registros in configuraciones_por_entidad.items():
        if len(registros) > 1:
            agregar("bloqueo", "configuracion_duplicada", "entidad_fiscal", entidad_id, "Existe más de una configuración para el mismo CUIT.")

    claves_punto = set()
    for punto in puntos:
        clave = (punto.entidad_fiscal_id, punto.numero)
        if clave in claves_punto:
            agregar("bloqueo", "punto_venta_duplicado", "punto_venta_fiscal", punto.id, "El número se repite para la entidad fiscal.")
        claves_punto.add(clave)
        if punto.entidad_fiscal_id not in entidad_ids or punto.configuracion_fiscal_id not in configuracion_ids:
            agregar("bloqueo", "punto_venta_ajeno", "punto_venta_fiscal", punto.id, "La cadena fiscal no pertenece al tenant.")
        if punto.emision_real_habilitada:
            agregar("bloqueo", "emision_real_habilitada", "punto_venta_fiscal", punto.id, "La emisión real debe permanecer bloqueada.")

    claves_tipo = set()
    for tipo in tipos or []:
        punto = getattr(tipo, "punto_venta", None)
        if punto is None or punto.id not in punto_ids:
            agregar("bloqueo", "tipo_ajeno", "tipo_comprobante_fiscal", tipo.id, "El tipo no pertenece a un punto de venta del tenant.")
            continue
        clave = (tipo.punto_venta_fiscal_id, tipo.codigo_arca)
        if clave in claves_tipo:
            agregar("bloqueo", "tipo_duplicado", "tipo_comprobante_fiscal", tipo.id, "El código se repite en el punto de venta.")
        claves_tipo.add(clave)

    filas_borrador = []
    for borrador in borradores:
        bloqueos = []
        if borrador.entidad_fiscal_id not in entidad_ids or borrador.punto_venta_fiscal_id not in punto_ids:
            bloqueos.append("cadena_fiscal_ajena")
        items = list(getattr(borrador, "items", []) or [])
        neto = sum(int(item.neto_centavos or 0) for item in items)
        iva = sum(int(item.iva_centavos or 0) for item in items)
        total = neto + iva + int(borrador.otros_tributos_centavos or 0)
        if (neto, iva, total) != (borrador.neto_centavos, borrador.iva_centavos, borrador.total_centavos):
            bloqueos.append("totales_inconsistentes")
        if borrador.estado == "listo" and not items:
            bloqueos.append("borrador_listo_sin_items")
        if borrador.estado != "autorizado" and (borrador.cae or borrador.numero_autorizado):
            bloqueos.append("autorizacion_impropia")
        for codigo in bloqueos:
            agregar("bloqueo", codigo, "borrador_comprobante_fiscal", borrador.id, "El borrador requiere corrección antes de cualquier integración.")
        filas_borrador.append({"id": borrador.id, "estado": borrador.estado, "items": len(items), "total_centavos": total, "bloqueos": bloqueos})

    resumen = {
        "entidades": len(entidades), "configuraciones": len(configuraciones), "puntos_venta": len(puntos),
        "tipos": len(list(tipos or [])), "borradores": len(borradores), "eventos": len(eventos),
        "bloqueos": sum(x["nivel"] == "bloqueo" for x in hallazgos),
    }
    base = {"organizacion_id": organizacion_id, "modulo_estado": getattr(modulo, "estado", "desactivado") if modulo else "desactivado", "resumen": resumen, "borradores": filas_borrador, "hallazgos": hallazgos}
    firma = hashlib.sha256(json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    return {**base, "firma_certificacion": firma, "aprobada": resumen["bloqueos"] == 0, "emision_real": False, "acciones_externas": 0, "escrituras": 0}


def exportar_certificacion(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2, default=str).encode("utf-8"))
