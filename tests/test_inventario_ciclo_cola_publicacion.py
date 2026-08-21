from types import SimpleNamespace

from services.inventario_cola_publicacion import (
    construir_clave_idempotencia,
    diagnosticar_cola,
    diagnosticar_propuesta,
    planificar_reemplazo,
)


def _propuesta(**cambios):
    datos = dict(id=1, clave_idempotencia="clave-1", huella_calculo="huella-1", puede_ejecutar=False)
    datos.update(cambios)
    return SimpleNamespace(**datos)


def test_clave_es_estable_y_aislada_por_tenant_cuenta_y_politica():
    clave = construir_clave_idempotencia(1, 2, 3, "ABC")
    assert clave == construir_clave_idempotencia(1, 2, 3, "abc")
    assert clave != construir_clave_idempotencia(2, 2, 3, "abc")
    assert clave != construir_clave_idempotencia(1, 2, 4, "abc")


def test_diagnostico_detecta_duplicada_obsoleta_e_invalida():
    vistas = set()
    assert diagnosticar_propuesta(_propuesta(), claves_vistas=vistas)["estado"] == "preparada_sin_ejecucion"
    assert diagnosticar_propuesta(_propuesta(id=2), claves_vistas=vistas)["estado"] == "duplicada"
    assert diagnosticar_propuesta(_propuesta(), huella_actual="otra")["estado"] == "obsoleta"
    assert diagnosticar_propuesta(_propuesta(puede_ejecutar=True))["estado"] == "invalida"


def test_reemplazo_es_solo_plan_y_permanece_bloqueado():
    plan = planificar_reemplazo(_propuesta(), "huella-2")
    assert plan["reemplaza_id"] == 1
    assert plan["estado_anterior"] == "obsoleta"
    assert plan["puede_aprobar"] is False
    assert plan["puede_ejecutar"] is False
    assert plan["persistir"] is False


def test_resumen_no_modifica_los_objetos():
    propuestas = [_propuesta(), _propuesta(id=2)]
    antes = [vars(p).copy() for p in propuestas]
    diagnosticos, resumen = diagnosticar_cola(propuestas)
    assert diagnosticos[1]["estado"] == "preparada_sin_ejecucion"
    assert diagnosticos[2]["estado"] == "duplicada"
    assert resumen["duplicada"] == 1
    assert [vars(p) for p in propuestas] == antes
