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

PRUEBAS_DATOS = (
    {
        "codigo": "DAT-01", "area": "administracion",
        "objetivo": "Confirmar el contexto exclusivo de ensayo",
        "recorrido": "Verificar organización, unidad activa, catálogo catalogo-uat desactivado y avisos de laboratorio desconectado.",
        "criterio": "La pantalla identifica únicamente el tenant/unidad UAT y el catálogo continúa desactivado.",
    },
    {
        "codigo": "DAT-02", "area": "carga",
        "objetivo": "Incorporar el producto sintético al catálogo",
        "recorrido": "Importar 01_inclusiones_catalogo.csv, revisar el mapeo y la vista previa antes de confirmar.",
        "criterio": "UAT-PROD-001 queda en catalogo-uat sin rechazos y sin publicarse en ningún canal.",
    },
    {
        "codigo": "DAT-03", "area": "carga",
        "objetivo": "Clasificar el producto sintético",
        "recorrido": "Importar 02_clasificacion_productos.csv y escribir IMPORTAR PRODUCTOS sólo después de revisar la vista previa.",
        "criterio": "UAT-PROD-001 queda clasificado como producción dentro de la unidad UAT.",
    },
    {
        "codigo": "DAT-04", "area": "costos",
        "objetivo": "Cargar las cuatro fuentes productivas",
        "recorrido": "Importar 03_insumos.csv, 04_empleados.csv, 05_maquinas.csv y 06_costos_fijos.csv; confirmar cada lote con IMPORTAR COSTOS.",
        "criterio": "Las cuatro fuentes aparecen sin rechazos, con alcance exclusivo de la unidad UAT.",
    },
    {
        "codigo": "DAT-05", "area": "costos",
        "objetivo": "Componer la ficha técnica sintética",
        "recorrido": "Importar 07_fichas_tecnicas.csv, revisar insumo, operación, máquina y costo fijo antes de confirmar.",
        "criterio": "La ficha de UAT-PROD-001 contiene las cuatro líneas y permite calcular un costo interno.",
    },
    {
        "codigo": "DAT-06", "area": "compras",
        "objetivo": "Incorporar el proveedor sintético",
        "recorrido": "Importar 08_proveedores.csv y escribir IMPORTAR PROVEEDORES después de revisar la vista previa.",
        "criterio": "UAT-PROV-001 queda visible sólo en la organización UAT y no genera comunicaciones.",
    },
    {
        "codigo": "DAT-07", "area": "catalogo",
        "objetivo": "Validar imagen y galería del producto",
        "recorrido": "Seleccionar 09_imagen_producto_uat.png, comprobar la vista previa y guardar la ficha de UAT-PROD-001.",
        "criterio": "La imagen se visualiza y su referencia pertenece al almacenamiento local aislado del tenant/unidad UAT.",
    },
    {
        "codigo": "DAT-08", "area": "control",
        "objetivo": "Comprobar idempotencia y ausencia de activación",
        "recorrido": "Repetir los archivos sin alterar su contenido y revisar catálogo, integraciones, webhooks y scheduler.",
        "criterio": "La repetición no duplica datos; catálogo e integraciones siguen inactivos y no hubo efectos externos.",
    },
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
        "pruebas_datos": [
            {
                **prueba, "resultado": "pendiente", "responsable": "",
                "evidencia": "", "observacion": "",
            }
            for prueba in PRUEBAS_DATOS
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
    pruebas_recibidas = {}
    for prueba in documento.get("pruebas_datos", []):
        if not isinstance(prueba, dict):
            continue
        codigo = str(prueba.get("codigo") or "").strip().upper()
        if codigo in pruebas_recibidas:
            hallazgos.append({"codigo": "prueba_datos_duplicada", "area": "datos_uat", "detalle": f"La prueba {codigo} está duplicada."})
        else:
            pruebas_recibidas[codigo] = prueba
    detalle_datos = []
    for definicion in PRUEBAS_DATOS:
        codigo = definicion["codigo"]
        prueba = pruebas_recibidas.get(codigo)
        if prueba is None:
            hallazgos.append({"codigo": "prueba_datos_faltante", "area": definicion["area"], "detalle": f"Falta la prueba {codigo}."})
            detalle_datos.append({**definicion, "resultado": "faltante", "responsable": "", "evidencia": "", "observacion": ""})
            continue
        resultado_prueba = str(prueba.get("resultado") or "").strip().lower()
        responsable_prueba = str(prueba.get("responsable") or "").strip()
        evidencia = str(prueba.get("evidencia") or "").strip()
        observacion_prueba = str(prueba.get("observacion") or "").strip()
        if resultado_prueba not in {"aprobado", "fallido", "bloqueado"}:
            hallazgos.append({"codigo": "resultado_prueba_datos_invalido", "area": definicion["area"], "detalle": f"La prueba {codigo} no tiene un resultado final válido."})
        elif resultado_prueba != "aprobado":
            hallazgos.append({"codigo": "prueba_datos_no_aprobada", "area": definicion["area"], "detalle": f"La prueba {codigo} terminó {resultado_prueba}."})
        if len(responsable_prueba) < 3:
            hallazgos.append({"codigo": "responsable_prueba_datos_faltante", "area": definicion["area"], "detalle": f"La prueba {codigo} no identifica responsable."})
        if len(evidencia) < 5:
            hallazgos.append({"codigo": "evidencia_prueba_datos_faltante", "area": definicion["area"], "detalle": f"La prueba {codigo} requiere una referencia de evidencia visual."})
        if resultado_prueba != "aprobado" and len(observacion_prueba) < 10:
            hallazgos.append({"codigo": "observacion_prueba_datos_insuficiente", "area": definicion["area"], "detalle": f"La prueba {codigo} requiere explicar el problema."})
        detalle_datos.append({**definicion, "resultado": resultado_prueba, "responsable": responsable_prueba, "evidencia": evidencia, "observacion": observacion_prueba})
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
        "pruebas_datos": detalle_datos,
        "hallazgos": hallazgos,
        "resumen": {"casos_requeridos": len(CASOS), "casos_aprobados": aprobados, "pruebas_datos_requeridas": len(PRUEBAS_DATOS), "pruebas_datos_aprobadas": sum(x["resultado"] == "aprobado" for x in detalle_datos), "participantes": len(participantes), "brechas": len(hallazgos)},
        "controles": {"persistencia": False, "pedidos_creados": 0, "stock_movido": 0, "facturas_emitidas": 0, "dinero_movido": 0, "asientos_publicados": 0, "acciones_externas": 0, "conexiones_externas": 0},
    }
    resultado["huella_acta_uat"] = hashlib.sha256(_canonico(resultado)).hexdigest()
    return resultado


def exportar(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
