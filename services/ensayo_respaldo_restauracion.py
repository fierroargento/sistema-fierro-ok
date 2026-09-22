"""Valida respaldos y ensaya su restauración completamente en memoria."""

import hashlib
import io
import json


CONJUNTOS_REQUERIDOS = (
    "estructura",
    "usuarios",
    "catalogo",
    "costos",
    "inventario",
    "pedidos",
    "compras",
    "produccion",
    "tesoreria",
    "contabilidad",
    "postventa",
    "auditoria",
)

ORDEN_RESTAURACION = (
    "estructura",
    "usuarios",
    "catalogo",
    "costos",
    "inventario",
    "pedidos",
    "compras",
    "produccion",
    "tesoreria",
    "contabilidad",
    "postventa",
    "auditoria",
)


def _canonico(valor):
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _leer(archivo):
    contenido = archivo.read() if hasattr(archivo, "read") else archivo
    if not isinstance(contenido, bytes) or not contenido or len(contenido) > 20_000_000:
        raise ValueError("El respaldo debe ser un JSON de hasta 20 MB.")
    try:
        documento = json.loads(contenido.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("El respaldo no es un JSON UTF-8 válido.") from error
    if not isinstance(documento, dict) or not isinstance(documento.get("conjuntos"), dict):
        raise ValueError("El respaldo debe contener un objeto conjuntos.")
    return documento


def plantilla(*, organizacion_id, unidad_negocio_id):
    documento = {
        "version": 1,
        "organizacion_id": int(organizacion_id),
        "unidad_negocio_id": int(unidad_negocio_id),
        "origen": "exportacion_controlada_sistema_fierro",
        "conjuntos": {nombre: [] for nombre in CONJUNTOS_REQUERIDOS},
    }
    return io.BytesIO(json.dumps(documento, ensure_ascii=False, indent=2).encode("utf-8"))


def ensayar(archivo, *, organizacion_id, unidad_negocio_id):
    documento = _leer(archivo)
    if int(documento.get("organizacion_id", -1)) != int(organizacion_id):
        raise ValueError("El respaldo pertenece a otro tenant.")
    if int(documento.get("unidad_negocio_id", -1)) != int(unidad_negocio_id):
        raise ValueError("El respaldo pertenece a otra unidad de negocio.")
    conjuntos = documento["conjuntos"]
    hallazgos = []
    detalle = []
    desconocidos = sorted(set(conjuntos) - set(CONJUNTOS_REQUERIDOS))
    for nombre in desconocidos:
        hallazgos.append({"codigo": "conjunto_desconocido", "conjunto": nombre, "detalle": "El conjunto no pertenece al contrato de respaldo."})
    for nombre in CONJUNTOS_REQUERIDOS:
        registros = conjuntos.get(nombre)
        if registros is None:
            hallazgos.append({"codigo": "conjunto_faltante", "conjunto": nombre, "detalle": "Falta el conjunto obligatorio."})
            registros = []
        if not isinstance(registros, list):
            hallazgos.append({"codigo": "formato_invalido", "conjunto": nombre, "detalle": "El conjunto debe ser una lista."})
            registros = []
        ids = set()
        duplicados = 0
        ajenos = 0
        unidades_ajenas = 0
        for registro in registros:
            if not isinstance(registro, dict):
                hallazgos.append({"codigo": "registro_invalido", "conjunto": nombre, "detalle": "Hay un registro que no es un objeto."})
                continue
            identidad_simple = registro.get("id")
            identidad = (registro.get("_modelo"), identidad_simple) if registro.get("_modelo") else identidad_simple
            if identidad is not None and identidad in ids:
                duplicados += 1
            if identidad is not None:
                ids.add(identidad)
            tenant = registro.get("organizacion_id")
            if tenant is not None and int(tenant) != int(organizacion_id):
                ajenos += 1
            unidad = registro.get("unidad_negocio_id")
            if unidad is not None and int(unidad) != int(unidad_negocio_id):
                unidades_ajenas += 1
        if duplicados:
            hallazgos.append({"codigo": "ids_duplicados", "conjunto": nombre, "detalle": f"Se detectaron {duplicados} identificadores duplicados."})
        if ajenos:
            hallazgos.append({"codigo": "registros_otro_tenant", "conjunto": nombre, "detalle": f"Se detectaron {ajenos} registros de otro tenant."})
        if unidades_ajenas:
            hallazgos.append({"codigo": "registros_otra_unidad", "conjunto": nombre, "detalle": f"Se detectaron {unidades_ajenas} registros de otra unidad."})
        detalle.append({
            "conjunto": nombre,
            "orden": ORDEN_RESTAURACION.index(nombre) + 1,
            "registros": len(registros),
            "huella": hashlib.sha256(_canonico(registros)).hexdigest(),
            "restaurado": False,
        })
    vacios = [item["conjunto"] for item in detalle if item["registros"] == 0]
    resultado = {
        "organizacion_id": int(organizacion_id),
        "unidad_negocio_id": int(unidad_negocio_id),
        "modo": "ensayo_respaldo_restauracion_offline_no_ejecutable",
        "aprobado": not hallazgos,
        "restauracion_autorizada": False,
        "resumen": {
            "conjuntos_requeridos": len(CONJUNTOS_REQUERIDOS),
            "conjuntos_presentes": sum(nombre in conjuntos for nombre in CONJUNTOS_REQUERIDOS),
            "registros": sum(item["registros"] for item in detalle),
            "conjuntos_vacios": len(vacios),
            "hallazgos": len(hallazgos),
        },
        "conjuntos_vacios": vacios,
        "orden_restauracion": detalle,
        "hallazgos": hallazgos,
        "controles": {
            "archivos_escritos": 0,
            "base_restaurada": 0,
            "tablas_modificadas": 0,
            "registros_insertados": 0,
            "registros_actualizados": 0,
            "registros_eliminados": 0,
            "conexiones_externas": 0,
        },
    }
    resultado["huella_ensayo_restauracion"] = hashlib.sha256(_canonico(resultado)).hexdigest()
    return resultado


def exportar(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
