"""Expediente maestro de preparación del reemplazo de DUX, sólo en memoria."""

import hashlib
import io
import json


DOMINIOS_REQUERIDOS = (
    "saas_base",
    "compras",
    "produccion",
    "tesoreria",
    "contabilidad",
    "mantenimiento",
    "personas",
    "postventa",
    "transicion_dux",
)

HUELLAS = (
    "huella_control",
    "huella_expediente",
    "huella_presupuesto",
    "huella_reporte",
    "huella_expediente_transicion",
)


def _leer(archivo):
    contenido = archivo.read() if hasattr(archivo, "read") else archivo
    if not isinstance(contenido, bytes) or not contenido or len(contenido) > 3_000_000:
        raise ValueError("Cada evidencia debe ser un JSON de hasta 3 MB.")
    try:
        documento = json.loads(contenido.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Una evidencia no es un JSON UTF-8 válido.") from error
    if not isinstance(documento, dict):
        raise ValueError("Cada evidencia debe contener un objeto JSON.")
    return documento


def _verificar_huella(documento):
    campos = [campo for campo in HUELLAS if campo in documento]
    if len(campos) != 1:
        raise ValueError("Una evidencia no contiene una única huella reconocida.")
    campo = campos[0]
    declarada = documento[campo]
    base = {clave: valor for clave, valor in documento.items() if clave != campo}
    calculada = hashlib.sha256(
        json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    if declarada != calculada:
        raise ValueError("La huella digital de una evidencia no coincide.")
    return campo, declarada


def _dominio(documento):
    modo = documento.get("modo")
    resumen = documento.get("resumen", {})
    controles = documento.get("controles", {})
    if modo == "expediente_transicion_dux_no_ejecutable":
        return "transicion_dux"
    if modo == "expediente_mantenimiento_no_ejecutable":
        return "mantenimiento"
    if modo == "expediente_personas_no_laboral":
        return "personas"
    if modo == "cierre_postventa_no_ejecutable":
        return "postventa"
    if modo == "presupuesto_offline_no_ejecutable":
        return "tesoreria"
    if modo == "reportes_contables_borrador_no_oficiales":
        return "contabilidad"
    if "componentes_identificados" in resumen and "componentes_requeridos" in resumen:
        return "saas_base"
    if modo == "solo_lectura" and "recepciones" in resumen and "facturas" in resumen:
        return "compras"
    if modo == "solo_lectura" and "simulaciones" in resumen and "consumos" in controles:
        return "produccion"
    raise ValueError("No se pudo identificar el dominio de una evidencia.")


def _aprobado(dominio, documento):
    if dominio == "saas_base":
        return documento.get("aprobada") is True
    if dominio == "transicion_dux":
        return documento.get("decision_recomendada") == "apto_para_ensayo_controlado"
    if dominio == "tesoreria":
        return not documento.get("errores")
    return documento.get("aprobado") is True


def construir_expediente(archivos, *, organizacion_id, unidad_negocio_id):
    archivos = list(archivos or [])
    if not 1 <= len(archivos) <= 20:
        raise ValueError("Seleccioná entre 1 y 20 evidencias JSON.")
    dominios = {}
    hallazgos = []
    for archivo in archivos:
        documento = _leer(archivo)
        if int(documento.get("organizacion_id", -1)) != int(organizacion_id):
            raise ValueError("Una evidencia pertenece a otro tenant.")
        unidad = documento.get("unidad_negocio_id")
        if unidad is not None and int(unidad) != int(unidad_negocio_id):
            raise ValueError("Una evidencia pertenece a otra unidad de negocio.")
        campo_huella, huella = _verificar_huella(documento)
        dominio = _dominio(documento)
        if dominio in dominios:
            hallazgos.append({"codigo": "dominio_duplicado", "dominio": dominio, "detalle": "Se recibió más de una evidencia del dominio."})
            continue
        aprobado = _aprobado(dominio, documento)
        dominios[dominio] = {
            "dominio": dominio,
            "aprobado": aprobado,
            "modo": documento.get("modo"),
            "campo_huella": campo_huella,
            "huella": huella,
        }
        if not aprobado:
            hallazgos.append({"codigo": "dominio_no_aprobado", "dominio": dominio, "detalle": "La evidencia del dominio requiere revisión."})
    faltantes = [dominio for dominio in DOMINIOS_REQUERIDOS if dominio not in dominios]
    for dominio in faltantes:
        hallazgos.append({"codigo": "dominio_faltante", "dominio": dominio, "detalle": "Falta incorporar la evidencia requerida."})
    transicion = dominios.get("transicion_dux")
    if transicion and not all(x in dominios and dominios[x]["aprobado"] for x in DOMINIOS_REQUERIDOS[:-1]):
        hallazgos.append({"codigo": "transicion_sin_dependencias", "dominio": "transicion_dux", "detalle": "La transición no puede considerarse lista sin aprobar los dominios previos."})
    resultado = {
        "organizacion_id": int(organizacion_id),
        "unidad_negocio_id": int(unidad_negocio_id),
        "modo": "expediente_maestro_preparacion_no_habilitante",
        "estado": "preparado_para_revision_humana" if not hallazgos else "incompleto",
        "autorizacion_corte_real": False,
        "dominios": [dominios[x] for x in DOMINIOS_REQUERIDOS if x in dominios],
        "hallazgos": hallazgos,
        "resumen": {
            "archivos": len(archivos),
            "dominios_identificados": len(dominios),
            "dominios_requeridos": len(DOMINIOS_REQUERIDOS),
            "dominios_aprobados": sum(x["aprobado"] for x in dominios.values()),
            "faltantes": len(faltantes),
            "hallazgos": len(hallazgos),
        },
        "controles": {
            "corte_dux": 0,
            "integraciones_activadas": 0,
            "stock_modificado": 0,
            "precios_publicados": 0,
            "pedidos_modificados": 0,
            "facturas_emitidas": 0,
            "pagos_registrados": 0,
            "documentos_persistidos": 0,
            "conexiones_externas": 0,
        },
    }
    resultado["huella_expediente_maestro"] = hashlib.sha256(
        json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return resultado


def exportar(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))

