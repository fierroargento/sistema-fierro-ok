from pathlib import Path

import services.control_comercial_masivo as modulo_control
from services.control_comercial_masivo import (
    construir_bandeja,
    evaluar_control,
    exportar_bandeja_excel,
)


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


def simulacion():
    producto = Obj(sku="SAAS-001")
    costo = Obj(producto_id=7, producto=producto)
    lista = Obj(nombre="Canal principal")
    regla = Obj(
        lista_precio_id=3, lista_precio=lista, comision_pct=10,
        umbral_envio_centavos=3300000, costo_envio_default_centavos=500000,
        tramos=[Obj(precio_desde_centavos=0, precio_hasta_centavos=3300000, cargo_fijo_centavos=100000)],
    )
    return {
        "costo": costo, "inclusion": Obj(id=11), "regla_canal": regla,
        "minimo": {"precio_final_centavos": 1222300, "piso_liquidacion_centavos": 1000000},
        "objetivo": {"precio_final_centavos": 1444500, "piso_liquidacion_centavos": 1200000},
    }


def test_clasifica_precio_segun_liquidacion_minima_y_objetivo():
    assert evaluar_control(simulacion(), 1500000)["estado_control"] == "rentable"
    assert evaluar_control(simulacion(), 1300000)["estado_control"] == "al_limite"
    assert evaluar_control(simulacion(), 1100000)["estado_control"] == "debajo_del_piso"
    assert evaluar_control(simulacion())["estado_control"] == "sin_precio"


def test_propuesta_nunca_reduce_precio_y_detecta_saltos_de_canal():
    propuesta = simulacion()
    propuesta["objetivo"] = {"precio_final_centavos": 3888900, "piso_liquidacion_centavos": 3000000}
    fila = evaluar_control(propuesta, 3200000)
    assert fila["propuesto"]["precio_final_centavos"] == 3888900
    assert fila["cambia_cargo"] is True
    assert fila["cambia_envio"] is True
    assert evaluar_control(simulacion(), 1600000)["propuesto"]["precio_final_centavos"] == 1600000


def test_bandeja_toma_version_vigente_de_la_lista_interna():
    items = [
        Obj(vigente=True, lista_precio_id=3, catalogo_producto_id=11, numero_version=1, precio_final_centavos=1100000),
        Obj(vigente=True, lista_precio_id=3, catalogo_producto_id=11, numero_version=2, precio_final_centavos=1500000),
    ]
    filas, resumen = construir_bandeja([simulacion()], items)
    assert filas[0]["actual"]["precio_final_centavos"] == 1500000
    assert filas[0]["fuente_precio"] == "lista_interna"
    assert resumen == {"total": 1, "rentable": 1, "al_limite": 0, "debajo_del_piso": 0, "sin_precio": 0}


def test_exportacion_es_operable_sin_crear_acciones(monkeypatch):
    class Hoja:
        def __init__(self): self.filas = []
        def append(self, fila): self.filas.append(fila)

    class Libro:
        ultimo = None
        def __init__(self):
            self.active = Hoja()
            Libro.ultimo = self
        def save(self, salida): salida.write(b"xlsx-diagnostico")

    monkeypatch.setattr(modulo_control, "Workbook", Libro)
    archivo = exportar_bandeja_excel([evaluar_control(simulacion(), 1100000)])
    assert archivo.read() == b"xlsx-diagnostico"
    assert Libro.ultimo.active.filas[0][0] == "SKU"
    assert Libro.ultimo.active.filas[1][0] == "SAAS-001"
    assert Libro.ultimo.active.filas[1][2] == "debajo_del_piso"


def test_contrato_es_diagnostico_saas_y_permanece_desconectado():
    servicio = Path("services/control_comercial_masivo.py").read_text(encoding="utf-8")
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    assert "/admin/comercial/control-comercial/exportar" in rutas
    assert "No se crea ninguna acción de publicación" in panel
    assert "Exportar seleccionados" in panel
    for prohibido in ("requests", "OAuth", "Webhook", "MercadoLibre", "Pedido.query"):
        assert prohibido not in servicio
