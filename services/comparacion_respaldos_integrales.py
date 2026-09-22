"""Compara dos respaldos firmados sin restaurarlos ni persistir resultados."""

import hashlib
import io
import json


def _canonico(valor):
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _leer(archivo, etiqueta):
    contenido = archivo.read() if hasattr(archivo, "read") else archivo
    if not isinstance(contenido, bytes) or not contenido or len(contenido) > 20_000_000:
        raise ValueError(f"El respaldo {etiqueta} debe ser un JSON de hasta 20 MB.")
    try:
        documento = json.loads(contenido.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"El respaldo {etiqueta} no es un JSON UTF-8 válido.") from error
    firma = documento.get("huella_respaldo")
    base = {clave: valor for clave, valor in documento.items() if clave != "huella_respaldo"}
    if firma != hashlib.sha256(_canonico(base)).hexdigest():
        raise ValueError(f"La huella del respaldo {etiqueta} no coincide.")
    if not isinstance(documento.get("conjuntos"), dict):
        raise ValueError(f"El respaldo {etiqueta} no contiene conjuntos.")
    return documento


def _clave(registro):
    if not isinstance(registro, dict):
        return None
    identidad = registro.get("id")
    return f"{registro.get('_modelo') or 'registro'}:{identidad}" if identidad is not None else None


def comparar(anterior, posterior, *, organizacion_id, unidad_negocio_id):
    anterior = _leer(anterior, "anterior")
    posterior = _leer(posterior, "posterior")
    for etiqueta, documento in (("anterior", anterior), ("posterior", posterior)):
        if int(documento.get("organizacion_id", -1)) != int(organizacion_id):
            raise ValueError(f"El respaldo {etiqueta} pertenece a otro tenant.")
        if int(documento.get("unidad_negocio_id", -1)) != int(unidad_negocio_id):
            raise ValueError(f"El respaldo {etiqueta} pertenece a otra unidad.")
    conjuntos = sorted(set(anterior["conjuntos"]) | set(posterior["conjuntos"]))
    detalle = []
    hallazgos = []
    for nombre in conjuntos:
        antes = anterior["conjuntos"].get(nombre, [])
        despues = posterior["conjuntos"].get(nombre, [])
        mapa_antes = {_clave(x): x for x in antes if _clave(x) is not None}
        mapa_despues = {_clave(x): x for x in despues if _clave(x) is not None}
        altas = sorted(set(mapa_despues) - set(mapa_antes))
        bajas = sorted(set(mapa_antes) - set(mapa_despues))
        cambios = sorted(clave for clave in set(mapa_antes) & set(mapa_despues) if _canonico(mapa_antes[clave]) != _canonico(mapa_despues[clave]))
        sin_identidad_antes = sum(_clave(x) is None for x in antes)
        sin_identidad_despues = sum(_clave(x) is None for x in despues)
        if bajas:
            hallazgos.append({"codigo": "registros_ausentes", "conjunto": nombre, "cantidad": len(bajas), "detalle": "El respaldo posterior no contiene registros presentes en el anterior."})
        if sin_identidad_antes or sin_identidad_despues:
            hallazgos.append({"codigo": "registros_sin_identidad", "conjunto": nombre, "cantidad": sin_identidad_antes + sin_identidad_despues, "detalle": "Hay registros que no pueden compararse individualmente."})
        detalle.append({
            "conjunto": nombre,
            "anteriores": len(antes),
            "posteriores": len(despues),
            "altas": len(altas),
            "bajas": len(bajas),
            "cambios": len(cambios),
            "claves_altas": altas[:100],
            "claves_bajas": bajas[:100],
            "claves_cambiadas": cambios[:100],
        })
    resultado = {
        "organizacion_id": int(organizacion_id),
        "unidad_negocio_id": int(unidad_negocio_id),
        "modo": "comparacion_respaldos_offline_solo_lectura",
        "estado": "sin_perdidas_detectadas" if not hallazgos else "requiere_revision",
        "restauracion_autorizada": False,
        "origenes": {
            "anterior": {"generado_en": anterior.get("generado_en"), "huella": anterior["huella_respaldo"]},
            "posterior": {"generado_en": posterior.get("generado_en"), "huella": posterior["huella_respaldo"]},
        },
        "resumen": {
            "conjuntos": len(detalle),
            "altas": sum(x["altas"] for x in detalle),
            "bajas": sum(x["bajas"] for x in detalle),
            "cambios": sum(x["cambios"] for x in detalle),
            "hallazgos": len(hallazgos),
        },
        "detalle": detalle,
        "hallazgos": hallazgos,
        "controles": {"escrituras": 0, "restauraciones": 0, "eliminaciones": 0, "conexiones_externas": 0},
    }
    resultado["huella_comparacion"] = hashlib.sha256(_canonico(resultado)).hexdigest()
    return resultado


def exportar(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))

