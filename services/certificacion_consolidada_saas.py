"""Consolida controles firmados del SaaS completamente en memoria."""

import hashlib
import io
import json


COMPONENTES_REQUERIDOS = {"estructura", "accesos", "inventario", "crm", "facturacion"}


def _leer(archivo):
    contenido = archivo.read() if hasattr(archivo, "read") else archivo
    if not isinstance(contenido, bytes) or not contenido or len(contenido) > 2_000_000:
        raise ValueError("Cada certificación debe ser un JSON de hasta 2 MB.")
    try:
        documento = json.loads(contenido.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Una certificación no es un JSON UTF-8 válido.") from error
    if not isinstance(documento, dict):
        raise ValueError("La certificación debe contener un objeto JSON.")
    return documento


def _componente(documento):
    resumen = documento.get("resumen", {})
    controles = documento.get("controles", {})
    if "vinculos_canales" in resumen and "modulos_activados" in controles:
        return "estructura"
    if "administradores_activos" in resumen and "credenciales_expuestas" in controles:
        return "accesos"
    if "existencias" in resumen and "publicaciones_canales" in controles:
        return "inventario"
    if "clientes" in resumen and "automatizaciones" in controles:
        return "crm"
    if "entidades_fiscales" in resumen or "emision_real" in controles or "comprobantes" in resumen:
        return "facturacion"
    if "movimientos" in resumen and ("movimiento_dinero" in controles or "acciones_externas" in controles):
        return "mercado_pago"
    if "publicaciones" in resumen or "tareas" in resumen:
        return "mercado_libre"
    if "eventos" in resumen and "mensajes_enviados" in controles:
        return "whatsapp"
    if "pedidos" in resumen:
        return "pedidos"
    if "cuentas" in resumen or "canales" in resumen:
        return "integraciones"
    raise ValueError("No se pudo identificar el componente de una certificación.")


def _verificar_firma(documento):
    campo = "huella_control" if "huella_control" in documento else "huella" if "huella" in documento else None
    if campo is None:
        raise ValueError("Una certificación no contiene huella digital.")
    declarada = documento.get(campo)
    base = {clave: valor for clave, valor in documento.items() if clave != campo}
    calculada = hashlib.sha256(json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if declarada != calculada:
        raise ValueError("La huella digital de una certificación no coincide.")
    return declarada


def consolidar_certificaciones(archivos, *, organizacion_id):
    archivos = list(archivos or [])
    if not 1 <= len(archivos) <= 20:
        raise ValueError("Seleccioná entre 1 y 20 certificaciones JSON.")
    componentes = {}
    hallazgos = []
    for archivo in archivos:
        documento = _leer(archivo)
        if documento.get("organizacion_id") != organizacion_id:
            raise ValueError("Una certificación pertenece a otro tenant.")
        huella = _verificar_firma(documento)
        componente = _componente(documento)
        if componente in componentes:
            hallazgos.append({"codigo": "componente_duplicado", "componente": componente, "detalle": "Se cargó más de una certificación del mismo componente."})
            continue
        aprobado = documento.get("aprobado", documento.get("aprobada", False)) is True
        componentes[componente] = {
            "componente": componente,
            "aprobado": aprobado,
            "huella": huella,
            "hallazgos": int(documento.get("resumen", {}).get("hallazgos", 0) or 0),
            "modo": documento.get("modo"),
        }
        if not aprobado:
            hallazgos.append({"codigo": "componente_no_aprobado", "componente": componente, "detalle": "El control del componente requiere revisión."})
        if documento.get("modo") not in {"offline", "solo_lectura"}:
            hallazgos.append({"codigo": "modo_no_desconectado", "componente": componente, "detalle": "El control no declara modo offline o de solo lectura."})
    faltantes = sorted(COMPONENTES_REQUERIDOS - set(componentes))
    for componente in faltantes:
        hallazgos.append({"codigo": "componente_faltante", "componente": componente, "detalle": "Falta la certificación requerida."})
    resultado = {
        "organizacion_id": organizacion_id,
        "modo": "offline",
        "aprobada": not hallazgos,
        "componentes": [componentes[x] for x in sorted(componentes)],
        "resumen": {
            "archivos_recibidos": len(archivos),
            "componentes_identificados": len(componentes),
            "componentes_requeridos": len(COMPONENTES_REQUERIDOS),
            "faltantes": len(faltantes),
            "hallazgos": len(hallazgos),
        },
        "hallazgos": hallazgos,
        "controles": {
            "documentos_persistidos": 0,
            "configuraciones_modificadas": 0,
            "modulos_activados": 0,
            "acciones_externas": 0,
            "escrituras": 0,
        },
    }
    resultado["huella_expediente"] = hashlib.sha256(json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return resultado


def exportar_expediente(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
