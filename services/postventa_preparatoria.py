"""Gestión tenant de postventa sin stock, dinero, mensajes o canales."""

import hashlib
import io
import json


def _validar_contexto(objeto, organizacion_id, unidad_negocio_id, nombre):
    if (objeto is None or int(objeto.organizacion_id) != int(organizacion_id)
            or int(objeto.unidad_negocio_id) != int(unidad_negocio_id)):
        raise ValueError(f"{nombre} no pertenece al contexto activo.")


def _validar_caso_pedido(caso, pedido, organizacion_id, unidad_negocio_id):
    _validar_contexto(caso, organizacion_id, unidad_negocio_id, "El caso")
    _validar_contexto(pedido, organizacion_id, unidad_negocio_id, "El pedido")
    if int(caso.pedido_id) != int(pedido.id):
        raise ValueError("El caso no corresponde al pedido indicado.")


def crear_caso(datos, *, pedido, organizacion_id, unidad_negocio_id, Caso,
               db_session, usuario_id=None):
    _validar_contexto(pedido, organizacion_id, unidad_negocio_id, "El pedido")
    tipo = str(datos.get("tipo") or "").strip()
    titulo = str(datos.get("titulo") or "").strip()
    descripcion = str(datos.get("descripcion") or "").strip()
    if (tipo not in {"devolucion", "garantia", "reclamo", "cambio"}
            or not 3 <= len(titulo) <= 180
            or not 10 <= len(descripcion) <= 1000):
        raise ValueError("Tipo, título y descripción no son válidos.")
    clave = hashlib.sha256(
        f"{organizacion_id}|{unidad_negocio_id}|{pedido.id}|{tipo}|{titulo.lower()}".encode()
    ).hexdigest()
    caso = Caso(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        pedido_id=pedido.id, tipo=tipo, titulo=titulo, descripcion=descripcion,
        clave_idempotencia=clave, estado="abierto", contacto_externo=False,
        afecta_stock=False, afecta_saldo=False,
        creado_por_usuario_id=usuario_id,
    )
    db_session.add(caso)
    db_session.commit()
    return caso


def proponer_resolucion(datos, *, caso, pedido, organizacion_id,
                        unidad_negocio_id, Propuesta, db_session):
    _validar_caso_pedido(caso, pedido, organizacion_id, unidad_negocio_id)
    if caso.estado in {"cancelado", "cerrado_sin_efecto"}:
        raise ValueError("El caso no admite propuestas en el contexto activo.")
    tipo = str(datos.get("tipo_resolucion") or "").strip()
    detalle = str(datos.get("detalle") or "").strip()
    try:
        importe = int(datos.get("importe_centavos") or 0)
    except (TypeError, ValueError) as error:
        raise ValueError("El importe debe expresarse en centavos.") from error
    if (tipo not in {"reposicion", "reintegro", "reparacion", "cambio", "rechazo"}
            or not 5 <= len(detalle) <= 800
            or not 0 <= importe <= 9_999_999_999_999):
        raise ValueError("La propuesta es inválida.")
    propuesta = Propuesta(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        caso_id=caso.id, tipo=tipo, detalle=detalle,
        importe_centavos=importe, aprobada=False, ejecutada=False,
        afecta_stock=False, emite_credito=False,
    )
    caso.estado = "propuesta"
    db_session.add(propuesta)
    db_session.commit()
    return propuesta


def cambiar_estado(caso, *, pedido, organizacion_id, unidad_negocio_id,
                   estado, db_session):
    _validar_caso_pedido(caso, pedido, organizacion_id, unidad_negocio_id)
    permitidos = {
        "abierto": {"diagnostico", "cancelado"},
        "diagnostico": {"cancelado"},
        "propuesta": {"cerrado_sin_efecto", "cancelado"},
    }
    if estado not in permitidos.get(caso.estado, set()):
        raise ValueError("La transición no es válida o implicaría ejecución.")
    caso.estado = estado
    db_session.commit()
    return caso


def expediente_postventa(*, organizacion_id, unidad_negocio_id, casos, propuestas):
    casos = [x for x in casos if int(x.organizacion_id) == int(organizacion_id)
             and int(x.unidad_negocio_id) == int(unidad_negocio_id)]
    ids = {x.id for x in casos}
    propuestas = [x for x in propuestas
                   if int(x.organizacion_id) == int(organizacion_id)
                   and int(x.unidad_negocio_id) == int(unidad_negocio_id)]
    hallazgos = []
    for caso in casos:
        if caso.contacto_externo or caso.afecta_stock or caso.afecta_saldo:
            hallazgos.append({"codigo": "caso_con_impacto", "caso_id": caso.id})
    for propuesta in propuestas:
        if propuesta.caso_id not in ids:
            hallazgos.append({"codigo": "propuesta_huerfana", "propuesta_id": propuesta.id})
        if (propuesta.aprobada or propuesta.ejecutada or propuesta.afecta_stock
                or propuesta.emite_credito):
            hallazgos.append({"codigo": "propuesta_ejecutable", "propuesta_id": propuesta.id})
    resultado = {
        "organizacion_id": int(organizacion_id),
        "unidad_negocio_id": int(unidad_negocio_id),
        "modo": "postventa_preparatoria_no_ejecutable",
        "aprobado": not hallazgos,
        "resumen": {
            "casos": len(casos),
            "abiertos": sum(x.estado not in {"cancelado", "cerrado_sin_efecto"} for x in casos),
            "propuestas": len(propuestas),
            "importe_propuesto_centavos": sum(int(x.importe_centavos) for x in propuestas),
            "hallazgos": len(hallazgos),
        },
        "hallazgos": hallazgos,
        "controles": {
            "stock_movido": 0, "reintegros": 0, "notas_credito": 0,
            "mensajes_enviados": 0, "reclamos_canal": 0,
            "conexiones_externas": 0,
        },
    }
    resultado["huella_expediente"] = hashlib.sha256(
        json.dumps(resultado, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return resultado


def exportar(resultado):
    return io.BytesIO(json.dumps(
        resultado, ensure_ascii=False, sort_keys=True, indent=2
    ).encode())
