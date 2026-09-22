"""Campaña UAT integral por roles, offline, firmada y no habilitante."""
import hashlib
import io
import json


CASOS = (
    ("administracion", "ADM-01", "Revisar estructura, permisos y expediente maestro"),
    ("carga", "CAR-01", "Preparar un pedido sin enviarlo a canales"),
    ("despacho", "DES-01", "Validar preparación, etiqueta y trazabilidad sin despachar"),
    ("comercial", "COM-01", "Simular precio, promoción y devolución por canal"),
    ("compras", "CMP-01", "Simular orden, recepción parcial y factura de proveedor"),
    ("produccion", "PRO-01", "Simular orden, avance, calidad, cierre y costeo"),
    ("tesoreria", "TES-01", "Validar proyección, liquidez y conciliación offline"),
    ("contabilidad", "CON-01", "Validar borrador, diario, mayor y balance"),
    ("postventa", "POS-01", "Simular caso, evidencia, recepción y resolución"),
)


def _canonico(valor):
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _leer(archivo, etiqueta, limite=5_000_000):
    contenido = archivo.read() if hasattr(archivo, "read") else archivo
    if not isinstance(contenido, bytes) or not contenido or len(contenido) > limite:
        raise ValueError(f"{etiqueta} debe ser JSON y no superar {limite // 1_000_000} MB.")
    try:
        documento = json.loads(contenido.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{etiqueta} no es JSON UTF-8 válido.") from error
    if not isinstance(documento, dict):
        raise ValueError(f"{etiqueta} debe contener un objeto JSON.")
    return documento


def plantilla(*, organizacion_id, unidad_negocio_id):
    documento = {
        "version": 1,
        "organizacion_id": int(organizacion_id),
        "unidad_negocio_id": int(unidad_negocio_id),
        "modo": "resultados_uat_offline",
        "participantes": [],
        "casos": [
            {"area": area, "codigo": codigo, "objetivo": objetivo, "resultado": "pendiente", "responsable": "", "observacion": ""}
            for area, codigo, objetivo in CASOS
        ],
    }
    return io.BytesIO(json.dumps(documento, ensure_ascii=False, indent=2).encode("utf-8"))


def _verificar_evaluacion(documento):
    campo = "huella_evaluacion_preparacion"
    firma = documento.get(campo)
    base = {clave: valor for clave, valor in documento.items() if clave != campo}
    if firma != hashlib.sha256(_canonico(base)).hexdigest():
        raise ValueError("La firma de la evaluación de preparación no coincide.")
    if documento.get("modo") != "evaluacion_preparacion_reemplazo_dux_no_habilitante":
        raise ValueError("El archivo no es una evaluación de preparación reconocida.")


def evaluar(evaluacion, resultados, *, organizacion_id, unidad_negocio_id):
    preparacion = _leer(evaluacion, "La evaluación de preparación", 20_000_000)
    _verificar_evaluacion(preparacion)
    documento = _leer(resultados, "Los resultados UAT")
    for etiqueta, origen in (("evaluación", preparacion), ("resultados", documento)):
        if int(origen.get("organizacion_id", -1)) != int(organizacion_id):
            raise ValueError(f"La {etiqueta} pertenece a otro tenant.")
        if int(origen.get("unidad_negocio_id", -1)) != int(unidad_negocio_id):
            raise ValueError(f"La {etiqueta} pertenece a otra unidad.")
    if documento.get("modo") != "resultados_uat_offline":
        raise ValueError("El archivo de resultados no corresponde a la campaña UAT.")
    hallazgos = []
    if preparacion.get("estado") != "preparado_para_decision_humana":
        hallazgos.append({"codigo": "preparacion_con_brechas", "area": "gobierno", "detalle": "La evaluación previa todavía contiene brechas."})
    recibidos = {}
    for caso in documento.get("casos", []):
        if not isinstance(caso, dict):
            continue
        codigo = str(caso.get("codigo") or "").strip().upper()
        if codigo in recibidos:
            hallazgos.append({"codigo": "caso_duplicado", "area": str(caso.get("area") or "general"), "detalle": f"El caso {codigo} está duplicado."})
        else:
            recibidos[codigo] = caso
    detalle = []
    for area, codigo, objetivo in CASOS:
        caso = recibidos.get(codigo)
        if caso is None:
            hallazgos.append({"codigo": "caso_faltante", "area": area, "detalle": f"Falta el caso {codigo}."})
            detalle.append({"area": area, "codigo": codigo, "objetivo": objetivo, "resultado": "faltante", "responsable": ""})
            continue
        resultado = str(caso.get("resultado") or "").strip().lower()
        responsable = str(caso.get("responsable") or "").strip()
        observacion = str(caso.get("observacion") or "").strip()
        if resultado not in {"aprobado", "fallido", "bloqueado"}:
            hallazgos.append({"codigo": "resultado_invalido", "area": area, "detalle": f"El caso {codigo} no tiene un resultado final válido."})
        elif resultado != "aprobado":
            hallazgos.append({"codigo": "caso_no_aprobado", "area": area, "detalle": f"El caso {codigo} terminó {resultado}."})
        if len(responsable) < 3:
            hallazgos.append({"codigo": "responsable_faltante", "area": area, "detalle": f"El caso {codigo} no identifica responsable."})
        if resultado != "aprobado" and len(observacion) < 10:
            hallazgos.append({"codigo": "observacion_insuficiente", "area": area, "detalle": f"El caso {codigo} requiere explicar el problema."})
        detalle.append({"area": area, "codigo": codigo, "objetivo": objetivo, "resultado": resultado, "responsable": responsable, "observacion": observacion})
    participantes = sorted({str(x).strip() for x in documento.get("participantes", []) if len(str(x).strip()) >= 3})
    if not participantes:
        hallazgos.append({"codigo": "participantes_faltantes", "area": "gobierno", "detalle": "La campaña no identifica participantes."})
    aprobados = sum(x["resultado"] == "aprobado" for x in detalle)
    resultado = {
        "organizacion_id": int(organizacion_id),
        "unidad_negocio_id": int(unidad_negocio_id),
        "modo": "acta_aceptacion_usuarios_no_habilitante",
        "estado": "uat_aprobada_para_revision_humana" if not hallazgos else "uat_con_brechas",
        "corte_dux_autorizado": False,
        "integraciones_autorizadas": False,
        "evaluacion_preparacion": {"estado": preparacion.get("estado"), "huella": preparacion["huella_evaluacion_preparacion"]},
        "participantes": participantes,
        "casos": detalle,
        "hallazgos": hallazgos,
        "resumen": {"casos_requeridos": len(CASOS), "casos_aprobados": aprobados, "participantes": len(participantes), "brechas": len(hallazgos)},
        "controles": {"persistencia": False, "pedidos_creados": 0, "stock_movido": 0, "facturas_emitidas": 0, "dinero_movido": 0, "asientos_publicados": 0, "acciones_externas": 0, "conexiones_externas": 0},
    }
    resultado["huella_acta_uat"] = hashlib.sha256(_canonico(resultado)).hexdigest()
    return resultado


def exportar(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
