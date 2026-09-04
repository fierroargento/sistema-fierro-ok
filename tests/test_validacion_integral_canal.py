from datetime import datetime, timedelta
from pathlib import Path

from services.cola_acciones_comerciales import planificar_fila, propuesta_esta_vigente
from services.validacion_integral_canal import evaluar_fila


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


def fila():
    return {
        "regla_canal": Obj(lista_precio_id=3), "inclusion": Obj(id=11),
        "costo": Obj(id=6, producto_id=7), "promocion": None,
        "actual": {"precio_final_centavos": 100000},
        "propuesto": {"precio_final_centavos": 130000},
        "minimo": {"piso_liquidacion_centavos": 90000},
        "objetivo": {"piso_liquidacion_centavos": 110000},
        "estado_control": "debajo_del_piso", "accion_recomendada": "actualizar_precio",
        "desvios_observados": [],
    }


def regla(**cambios):
    datos = dict(
        exigir_precio_observado=True, exigir_cargos_observados=True,
        exigir_envio_observado=True, exigir_promocion_observada=False,
        exigir_identidad_unica=True, vigencia_precio_horas=24,
        vigencia_cargos_horas=24, vigencia_envio_horas=24,
        vigencia_promocion_horas=24,
    )
    datos.update(cambios); return Obj(**datos)


def observacion(tipo, ahora, cuenta="CUENTA-1", publicacion="PUB-1"):
    return Obj(
        tipo=tipo, lista_precio_id=3, catalogo_producto_id=11,
        fecha_observacion=ahora, cuenta_codigo=cuenta,
        referencia_publicacion=publicacion,
    )


def test_fila_lista_exige_datos_frescos_y_misma_identidad():
    ahora = datetime(2026, 9, 4, 12)
    resultado = evaluar_fila(
        fila(), regla(), [observacion(tipo, ahora) for tipo in ("precio", "cargo", "envio")],
        [], ahora=ahora,
    )
    assert resultado["estado_preparacion"] == "advertencia"
    assert resultado["advertencias"] == ["promocion_no_observada"]
    assert resultado["identidades"] == [("CUENTA-1", "PUB-1")]


def test_datos_vencidos_faltantes_o_de_otra_publicacion_bloquean():
    ahora = datetime(2026, 9, 4, 12)
    datos = [
        observacion("precio", ahora - timedelta(hours=25)),
        observacion("cargo", ahora, publicacion="PUB-OTRA"),
    ]
    resultado = evaluar_fila(fila(), regla(), datos, [], ahora=ahora)
    assert resultado["estado_preparacion"] == "bloqueada"
    assert "precio_vencido" in resultado["bloqueos"]
    assert "envio_no_observado" in resultado["bloqueos"]
    assert "cuenta_o_publicacion_inconsistente" in resultado["bloqueos"]


def test_desvio_contra_regla_comercial_es_bloqueante():
    actual = fila(); actual["desvios_observados"] = ["comision_observada_distinta"]
    ahora = datetime(2026, 9, 4, 12)
    resultado = evaluar_fila(actual, regla(exigir_precio_observado=False, exigir_cargos_observados=False, exigir_envio_observado=False), [], [], ahora=ahora)
    assert "comision_observada_distinta" in resultado["bloqueos"]


def test_propuesta_se_vuelve_obsoleta_si_cambia_el_calculo():
    actual = fila(); especificacion = planificar_fila(actual)[0]
    propuesta = Obj(tipo_accion="actualizar_precio", huella_calculo=especificacion["huella_calculo"])
    assert propuesta_esta_vigente(propuesta, actual) is True
    actual["propuesto"] = {"precio_final_centavos": 140000}
    assert propuesta_esta_vigente(propuesta, actual) is False


def test_modelo_panel_y_motor_no_tienen_ejecucion_externa():
    modelo = Path("models/regla_validacion_canal.py").read_text(encoding="utf-8")
    servicio = Path("services/validacion_integral_canal.py").read_text(encoding="utf-8")
    cola = Path("services/cola_acciones_comerciales.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    assert "class ReglaValidacionCanalVersion" in modelo
    assert 'value="crear_regla_validacion_canal"' in panel
    assert "Tablero de preparación integral" in panel
    assert "propuesta quedo obsoleta" in cola
    for prohibido in ("requests", "OAuth", "Webhook", "MercadoLibre", "access_token"):
        assert prohibido not in servicio
