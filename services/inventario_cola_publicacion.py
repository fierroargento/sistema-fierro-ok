"""Reglas puras de la futura cola de publicación, sin escritura ni APIs."""

import hashlib


ESTADO_PREPARADA = "preparada_sin_ejecucion"
ESTADO_DUPLICADA = "duplicada"
ESTADO_OBSOLETA = "obsoleta"
ESTADO_INVALIDA = "invalida"


def construir_clave_idempotencia(organizacion_id, politica_id, vinculo_id, huella_calculo):
    contrato = ":".join((str(int(organizacion_id)), str(int(politica_id)), str(int(vinculo_id)), str(huella_calculo or "").strip().lower()))
    return hashlib.sha256(contrato.encode("utf-8")).hexdigest()


def diagnosticar_propuesta(propuesta, *, huella_actual=None, claves_vistas=None):
    claves_vistas = claves_vistas if claves_vistas is not None else set()
    clave = str(getattr(propuesta, "clave_idempotencia", "") or "")
    huella = str(getattr(propuesta, "huella_calculo", "") or "")
    if bool(getattr(propuesta, "puede_ejecutar", False)):
        estado, bloqueo = ESTADO_INVALIDA, "El contrato habilita ejecución y debe revisarse"
    elif not clave or not huella:
        estado, bloqueo = ESTADO_INVALIDA, "Falta clave de idempotencia o huella"
    elif clave in claves_vistas:
        estado, bloqueo = ESTADO_DUPLICADA, "La clave ya existe en la cola evaluada"
    elif huella_actual is not None and huella != str(huella_actual):
        estado, bloqueo = ESTADO_OBSOLETA, "El cálculo cambió y requiere una nueva propuesta"
    else:
        estado, bloqueo = ESTADO_PREPARADA, "Ejecución y aprobación no implementadas"
    if clave:
        claves_vistas.add(clave)
    return {"estado": estado, "bloqueos": [bloqueo], "puede_aprobar": False, "puede_ejecutar": False}


def diagnosticar_cola(propuestas):
    claves_vistas = set()
    diagnosticos = {}
    resumen = {ESTADO_PREPARADA: 0, ESTADO_DUPLICADA: 0, ESTADO_OBSOLETA: 0, ESTADO_INVALIDA: 0}
    for propuesta in propuestas:
        diagnostico = diagnosticar_propuesta(propuesta, claves_vistas=claves_vistas)
        diagnosticos[getattr(propuesta, "id", None)] = diagnostico
        resumen[diagnostico["estado"]] += 1
    return diagnosticos, resumen


def planificar_reemplazo(propuesta, nueva_huella):
    """Describe un reemplazo teórico; nunca persiste ni ejecuta nada."""
    return {
        "reemplaza_id": getattr(propuesta, "id", None),
        "huella_anterior": getattr(propuesta, "huella_calculo", None),
        "huella_nueva": str(nueva_huella or ""),
        "estado_anterior": ESTADO_OBSOLETA,
        "estado_nuevo": ESTADO_PREPARADA,
        "puede_aprobar": False,
        "puede_ejecutar": False,
        "persistir": False,
    }
