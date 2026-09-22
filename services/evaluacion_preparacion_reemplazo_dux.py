"""Evaluación consolidada, firmada y no habilitante del reemplazo de DUX."""
import hashlib
import io
import json


EVIDENCIAS = {
    "expediente_maestro": ("huella_expediente_maestro", "expediente_maestro_preparacion_no_habilitante"),
    "continuidad": ("huella_expediente_continuidad", "expediente_continuidad_no_ejecutable"),
    "aceptacion": ("huella_aceptacion", "aceptacion_operativa_integral_offline"),
}
CONTROLES_HUMANOS = (
    ("responsables_confirmados", "Responsables y suplentes confirmados"),
    ("ventana_acordada", "Ventana de transición acordada"),
    ("comunicacion_preparada", "Comunicación interna y externa preparada"),
    ("reversion_asignada", "Responsable de reversión asignado"),
    ("inventario_congelado", "Criterio de congelamiento de inventario definido"),
    ("conciliacion_programada", "Conciliación final programada"),
)


def _canonico(valor):
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _leer(archivo, tipo):
    contenido = archivo.read() if hasattr(archivo, "read") else archivo
    if not isinstance(contenido, bytes) or not contenido or len(contenido) > 20_000_000:
        raise ValueError(f"La evidencia {tipo} debe ser JSON y no superar 20 MB.")
    try:
        documento = json.loads(contenido.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"La evidencia {tipo} no es JSON UTF-8 válido.") from error
    if not isinstance(documento, dict):
        raise ValueError(f"La evidencia {tipo} debe contener un objeto JSON.")
    campo, modo = EVIDENCIAS[tipo]
    declarada = documento.get(campo)
    base = {clave: valor for clave, valor in documento.items() if clave != campo}
    if declarada != hashlib.sha256(_canonico(base)).hexdigest():
        raise ValueError(f"La firma de la evidencia {tipo} no coincide.")
    if documento.get("modo") != modo:
        raise ValueError(f"La evidencia {tipo} no corresponde al modo esperado.")
    return documento


def evaluar(archivos, datos, *, organizacion_id, unidad_negocio_id):
    archivos = archivos or {}
    documentos = {tipo: _leer(archivos.get(tipo), tipo) for tipo in EVIDENCIAS}
    hallazgos = []
    for tipo, documento in documentos.items():
        if int(documento.get("organizacion_id", -1)) != int(organizacion_id):
            raise ValueError(f"La evidencia {tipo} pertenece a otro tenant.")
        if int(documento.get("unidad_negocio_id", -1)) != int(unidad_negocio_id):
            raise ValueError(f"La evidencia {tipo} pertenece a otra unidad.")
    criterios = {
        "expediente_maestro": documentos["expediente_maestro"].get("estado") == "preparado_para_revision_humana",
        "continuidad": documentos["continuidad"].get("estado") == "apto_para_simulacro_humano",
        "aceptacion": documentos["aceptacion"].get("aprobado") is True,
    }
    for codigo, aprobado in criterios.items():
        if not aprobado:
            hallazgos.append({"codigo": f"{codigo}_no_aprobado", "tipo": "tecnico", "detalle": "La evidencia técnica requiere revisión."})
    controles_humanos = []
    for codigo, etiqueta in CONTROLES_HUMANOS:
        confirmado = str(datos.get(codigo, "")).lower() in {"1", "true", "on", "si"}
        controles_humanos.append({"codigo": codigo, "etiqueta": etiqueta, "confirmado": confirmado})
        if not confirmado:
            hallazgos.append({"codigo": codigo, "tipo": "humano", "detalle": etiqueta + "."})
    tecnicos_aprobados = sum(criterios.values())
    humanos_confirmados = sum(x["confirmado"] for x in controles_humanos)
    resultado = {
        "organizacion_id": int(organizacion_id),
        "unidad_negocio_id": int(unidad_negocio_id),
        "modo": "evaluacion_preparacion_reemplazo_dux_no_habilitante",
        "estado": "preparado_para_decision_humana" if not hallazgos else "bloqueado_por_brechas",
        "corte_dux_autorizado": False,
        "activacion_integraciones_autorizada": False,
        "criterios_tecnicos": [{"codigo": codigo, "aprobado": aprobado} for codigo, aprobado in criterios.items()],
        "controles_humanos": controles_humanos,
        "evidencias": {tipo: {"modo": documento["modo"], "huella": documento[EVIDENCIAS[tipo][0]]} for tipo, documento in documentos.items()},
        "hallazgos": hallazgos,
        "resumen": {"tecnicos_aprobados": tecnicos_aprobados, "tecnicos_requeridos": len(criterios), "humanos_confirmados": humanos_confirmados, "humanos_requeridos": len(CONTROLES_HUMANOS), "brechas": len(hallazgos)},
        "controles": {"cortes": 0, "escrituras": 0, "integraciones_activadas": 0, "stock_modificado": 0, "precios_publicados": 0, "facturas_emitidas": 0, "pagos_registrados": 0, "conexiones_externas": 0},
    }
    resultado["huella_evaluacion_preparacion"] = hashlib.sha256(_canonico(resultado)).hexdigest()
    return resultado


def exportar(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
