from datetime import datetime, timedelta
from pathlib import Path

from services.control_comercial_masivo import construir_bandeja, evaluar_control
from services.promociones_canal import (
    calcular_descuento_pct,
    observaciones_actuales,
    registrar_observacion,
)


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


class Sesion:
    def __init__(self): self.agregados = []; self.commits = 0
    def add(self, valor): self.agregados.append(valor)
    def commit(self): self.commits += 1


def simulacion():
    return {
        "costo": Obj(producto_id=7, producto=Obj(sku="SAAS-001")),
        "inclusion": Obj(id=11),
        "regla_canal": Obj(
            lista_precio_id=3, lista_precio=Obj(nombre="Canal"), comision_pct=10,
            umbral_envio_centavos=3300000, costo_envio_default_centavos=500000,
            tramos=[Obj(precio_desde_centavos=0, precio_hasta_centavos=3300000, cargo_fijo_centavos=100000)],
        ),
        "minimo": {"precio_final_centavos": 1222300, "piso_liquidacion_centavos": 1000000},
        "objetivo": {"precio_final_centavos": 1444500, "piso_liquidacion_centavos": 1200000},
    }


def test_descuento_se_calcula_desde_precios_observados():
    assert str(calcular_descuento_pct(110000, 100000)) == "9.090909"


def test_registro_es_append_only_y_auditable():
    sesion = Sesion()
    registro = registrar_observacion(
        organizacion_id=1, unidad_negocio_id=2, lista_precio_id=3,
        catalogo_producto_id=11, referencia_externa="PROMO-1", nombre="Oferta",
        precio_base_centavos=110000, precio_promocional_centavos=100000,
        estado_observado="activa", origen="manual", observacion="Control",
        usuario=Obj(id=9, username="admin"), PromocionCanalObservacion=Obj,
        db_session=sesion,
    )
    assert str(registro.descuento_pct) == "9.090909"
    assert registro.creado_por_username == "admin"
    assert sesion.agregados == [registro] and sesion.commits == 1


def test_ultima_observacion_define_si_la_promocion_sigue_activa():
    ahora = datetime(2026, 9, 4)
    activa = Obj(lista_precio_id=3, catalogo_producto_id=11, estado_observado="activa", fecha_observacion=ahora)
    inactiva = Obj(lista_precio_id=3, catalogo_producto_id=11, estado_observado="inactiva", fecha_observacion=ahora + timedelta(minutes=1))
    assert observaciones_actuales([inactiva, activa])[(3, 11)] is inactiva


def test_promocion_bajo_objetivo_exige_cancelar_antes_de_actualizar():
    promo = Obj(
        lista_precio_id=3, catalogo_producto_id=11, estado_observado="activa",
        precio_base_centavos=1500000, precio_promocional_centavos=1100000,
        descuento_pct=26.666667, fecha_observacion=datetime(2026, 9, 4),
    )
    item = Obj(vigente=True, lista_precio_id=3, catalogo_producto_id=11, numero_version=1, precio_final_centavos=1500000)
    filas, _ = construir_bandeja([simulacion()], [item], [promo])
    assert filas[0]["actual"]["precio_final_centavos"] == 1100000
    assert filas[0]["estado_control"] == "debajo_del_piso"
    assert filas[0]["accion_recomendada"] == "cancelar_promocion_antes_de_actualizar"


def test_promocion_rentable_puede_mantenerse():
    promo = Obj(estado_observado="activa")
    fila = evaluar_control(simulacion(), 1500000, promocion=promo, precio_base_centavos=1600000)
    assert fila["accion_recomendada"] == "mantener_promocion"


def test_modelo_y_panel_son_genericos_y_permanecen_desconectados():
    modelo = Path("models/promocion_canal.py").read_text(encoding="utf-8")
    servicio = Path("services/promociones_canal.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")
    assert "class PromocionCanalObservacion" in modelo
    assert 'value="registrar_promocion_canal"' in panel
    assert "No crean ni cancelan promociones" in panel
    assert "cancelar_promocion_antes_de_actualizar" in Path("services/control_comercial_masivo.py").read_text(encoding="utf-8")
    assert '"PromocionCanalObservacion"' in app
    for prohibido in ("requests", "OAuth", "Webhook", "MercadoLibre"):
        assert prohibido not in servicio
