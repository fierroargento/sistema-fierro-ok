import json
from decimal import Decimal
from pathlib import Path

from services.compras_nucleo import preparar_recepcion
from services.migraciones_saas import asegurar_subtotal_recepciones_compra
from services.propuestas_impacto_compra import preparar_propuestas


class Obj:
    def __init__(self, **datos):
        self.__dict__.update(datos)


class Recepcion(Obj):
    def __init__(self, **datos):
        super().__init__(**datos)
        self.items = []


class RecepcionItem(Obj):
    pass


class Session:
    def __init__(self):
        self.agregados = []
        self.ejecutado = []

    def add(self, item):
        self.agregados.append(item)

    def commit(self):
        pass

    def execute(self, sentencia):
        self.ejecutado.append(str(sentencia))


class Query:
    def filter_by(self, **_filtros):
        return self

    def all(self):
        return []


class Propuesta(Obj):
    query = Query()


def _orden():
    return Obj(
        id=5, organizacion_id=7, unidad_negocio_id=9, estado="aprobada",
        proveedor_id=40, total_centavos=100000,
        items=[Obj(
            id=10, cantidad=Decimal("10"), descripcion="Hierro",
            precio_unitario_centavos=10000, insumo_id=20,
        )],
        recepciones=[],
    )


def _preparar(orden, numero, cantidad):
    recepcion = preparar_recepcion(
        {"numero": numero, "cantidad_10": cantidad}, orden=orden,
        organizacion_id=7, unidad_negocio_id=9,
        RecepcionCompra=Recepcion, RecepcionCompraItem=RecepcionItem,
        db_session=Session(),
    )
    recepcion.id = len(orden.recepciones) + 1
    recepcion.orden = orden
    recepcion.comprobante_referencia = numero
    for indice, item in enumerate(recepcion.items, 1):
        item.id = recepcion.id * 10 + indice
        item.orden_item = orden.items[0]
    orden.recepciones.append(recepcion)
    return recepcion


def test_dos_recepciones_parciales_distribuyen_el_total_sin_duplicarlo():
    orden = _orden()
    primera = _preparar(orden, "RC-1", "4")
    segunda = _preparar(orden, "RC-2", "6")
    assert primera.subtotal_centavos == 40000
    assert segunda.subtotal_centavos == 60000
    assert sum(item.subtotal_centavos for item in orden.recepciones) == orden.total_centavos


def test_cuenta_pagar_toma_solo_el_importe_de_la_recepcion():
    orden = _orden()
    recepcion = _preparar(orden, "RC-1", "4")
    propuestas = preparar_propuestas(
        recepcion, organizacion_id=7, unidad_negocio_id=9,
        PropuestaImpactoCompra=Propuesta, db_session=Session(),
    )
    pagar = next(item for item in propuestas if item.tipo == "cuenta_pagar")
    assert json.loads(pagar.detalle_json)["importe_centavos"] == 40000
    assert pagar.ejecutada is False


def test_objeto_legacy_sin_subtotal_calcula_el_importe_en_memoria():
    orden = _orden()
    recepcion = _preparar(orden, "RC-1", "4")
    del recepcion.subtotal_centavos
    propuestas = preparar_propuestas(
        recepcion, organizacion_id=7, unidad_negocio_id=9,
        PropuestaImpactoCompra=Propuesta, db_session=Session(),
    )
    pagar = next(item for item in propuestas if item.tipo == "cuenta_pagar")
    assert json.loads(pagar.detalle_json)["importe_centavos"] == 40000


def test_redondeo_economico_es_por_linea_recibida():
    orden = _orden()
    orden.items[0].precio_unitario_centavos = 333
    recepcion = _preparar(orden, "RC-1", "1.5")
    assert recepcion.subtotal_centavos == 500


def test_migracion_es_aditiva_y_no_hace_backfill():
    sesion = Session()
    db = Obj(engine=object(), session=sesion)
    inspector = Obj(
        get_table_names=lambda: ["recepcion_compra"],
        get_columns=lambda _tabla: [{"name": "id"}],
    )
    resultado = asegurar_subtotal_recepciones_compra(
        db=db, inspect_fn=lambda _engine: inspector,
        text_fn=lambda texto: texto, logger_fn=None,
    )
    assert resultado == {"columna_creada": True}
    assert len(sesion.ejecutado) == 1
    assert "ADD COLUMN subtotal_centavos" in sesion.ejecutado[0]
    assert "UPDATE" not in sesion.ejecutado[0]


def test_frontera_no_ejecuta_stock_costos_pagos_o_conexiones():
    servicio = Path("services/compras_nucleo.py").read_text(encoding="utf-8")
    propuestas = Path("services/propuestas_impacto_compra.py").read_text(encoding="utf-8")
    assert "requests." not in servicio + propuestas
    assert "movimiento_creado\": False" in propuestas
    assert "obligacion_creada\": False" in propuestas
    assert "ejecutada=False" in propuestas


def test_panel_muestra_importe_recibido_sin_ofrecer_ejecucion():
    panel = Path("templates/admin_compras.html").read_text(encoding="utf-8")
    assert "Importe recibido" in panel
    assert "recepcion.subtotal_centavos" in panel
    assert "Ejecutar impacto" not in panel
