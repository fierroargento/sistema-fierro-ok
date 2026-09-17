from pathlib import Path

from services.control_comercial_masivo import evaluar_control
from services.motor_comercial_canal import precio_lista_para_descuento


class Obj:
    def __init__(self, **datos):
        self.__dict__.update(datos)


def _simulacion():
    regla = Obj(
        lista_precio_id=3, comision_pct=10, publicidad_pct=5,
        financiacion_pct=4, devoluciones_pct=3,
        incremento_redondeo_centavos=100,
        umbral_envio_centavos=0, costo_envio_default_centavos=0,
        tramos=(),
    )
    return {
        "costo": Obj(producto_id=7), "inclusion": Obj(id=11),
        "regla_canal": regla,
        "minimo": {"precio_final_centavos": 100000, "piso_liquidacion_centavos": 70000},
        "objetivo": {"precio_final_centavos": 90000, "piso_liquidacion_centavos": 70000},
    }


def test_reconstruye_precio_base_para_conservar_descuento():
    assert precio_lista_para_descuento(90000, 10, 100) == 100000


def test_control_propone_cancelar_promocion_y_precio_base_equivalente():
    promocion = Obj(estado_observado="activa", descuento_pct=10)
    fila = evaluar_control(_simulacion(), 80000, promocion=promocion, precio_base_centavos=88889)
    assert fila["accion_recomendada"] == "cancelar_promocion_antes_de_actualizar"
    assert fila["precio_base_promocional_sugerido_centavos"] == 100000
    assert fila["actual"]["devoluciones_centavos"] == 2400


def test_contrato_persiste_y_migra_devoluciones_con_default_cero():
    modelo = Path("models/regla_canal.py").read_text(encoding="utf-8")
    migraciones = Path("services/migraciones_saas.py").read_text(encoding="utf-8")
    servicio = Path("services/comercial_admin.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    assert "devoluciones_pct = db.Column" in modelo
    assert '"devoluciones_pct": "NUMERIC(9, 6) NOT NULL DEFAULT 0"' in migraciones
    assert 'devoluciones_pct=formulario.get("devoluciones_pct", 0)' in servicio
    assert 'name="devoluciones_pct"' in panel


def test_consumidores_usen_todos_los_costos_porcentuales():
    for ruta in (
        "services/control_comercial_masivo.py",
        "services/simulador_integral_comercial.py",
    ):
        fuente = Path(ruta).read_text(encoding="utf-8")
        assert "publicidad_pct=" in fuente
        assert "financiacion_pct=" in fuente
        assert "devoluciones_pct=" in fuente


def test_bloque_permanece_offline_y_no_publica_precios():
    fuentes = "\n".join(
        Path(ruta).read_text(encoding="utf-8").lower()
        for ruta in (
            "services/motor_comercial_canal.py",
            "services/control_comercial_masivo.py",
        )
    )
    for prohibido in ("requests", "access_token", "oauth", "webhook", "db.session"):
        assert prohibido not in fuentes
