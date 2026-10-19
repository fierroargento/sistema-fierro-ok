"""Lectura acotada de evidencia normalizada; sin almacenamiento ni conexiones."""
import json

from services.rentabilidad_ml_offline import analizar_rentabilidad
from services.lectura_ml_rentabilidad import FORMATO_ML, normalizar_snapshot_ml
from services.lectura_mp_rentabilidad import FORMATO_MP, normalizar_snapshot_mp

MAX_ARCHIVO_BYTES = 2_000_000


def _objeto_sin_repetidos(pares):
    objeto = {}
    for clave, valor in pares:
        if clave in objeto:
            raise ValueError("El JSON contiene claves repetidas.")
        objeto[clave] = valor
    return objeto


def _constante_invalida(_valor):
    raise ValueError("El JSON no admite NaN ni infinito.")


def analizar_archivo(contenido, *, organizacion_id, unidad_negocio_id, cuenta_codigo):
    if not isinstance(contenido, bytes) or not contenido or len(contenido) > MAX_ARCHIVO_BYTES:
        raise ValueError("Seleccioná un JSON de hasta 2 MB.")
    try:
        documento = json.loads(contenido.decode("utf-8-sig"),
            object_pairs_hook=_objeto_sin_repetidos, parse_constant=_constante_invalida)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("El archivo debe ser un JSON UTF-8 válido, sin estructuras excesivamente anidadas.") from None
    if not isinstance(documento, dict):
        raise ValueError("Se requiere un objeto JSON con el contrato de rentabilidad.")
    # Una exportación incluye también resultado/escenario. Nunca se confía en ellos.
    entrada = documento.get("entrada") if "entrada" in documento else documento
    if not isinstance(entrada, dict):
        raise ValueError("El campo entrada debe contener el contrato normalizado.")
    try:
        if entrada.get("formato") == FORMATO_MP:
            entrada = normalizar_snapshot_mp(entrada, organizacion_id=organizacion_id,
                unidad_negocio_id=unidad_negocio_id, cuenta_codigo=cuenta_codigo)
        elif entrada.get("formato") == FORMATO_ML:
            entrada = normalizar_snapshot_ml(entrada, organizacion_id=organizacion_id,
                unidad_negocio_id=unidad_negocio_id, cuenta_codigo=cuenta_codigo)
        resultado = analizar_rentabilidad(entrada, organizacion_id=organizacion_id,
            unidad_negocio_id=unidad_negocio_id, cuenta_codigo=cuenta_codigo)
    except (TypeError, AttributeError, RecursionError, OverflowError):
        raise ValueError("La estructura del contrato no es válida. Revisá tipos, referencias y fechas.") from None
    return entrada, resultado
