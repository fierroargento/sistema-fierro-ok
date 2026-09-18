from decimal import Decimal
from pathlib import Path

from services.compras_nucleo import agregar_item_orden, quitar_item_orden


class Obj:
    def __init__(self, **datos):
        self.__dict__.update(datos)


class Item(Obj):
    pass


class Session:
    def __init__(self):
        self.eliminados = []
        self.commits = 0

    def delete(self, item):
        self.eliminados.append(item)

    def commit(self):
        self.commits += 1


def orden():
    return Obj(
        organizacion_id=7, estado="borrador", total_centavos=100000,
        items=[Obj(id=1, subtotal_centavos=100000)],
    )


def test_agrega_multiples_items_y_recalcula_total():
    compra = orden()
    agregar_item_orden(
        compra,
        {"cantidad": "2,5", "precio_unitario": "2.000",
         "descripcion": "Chapa", "unidad_medida": "kg"},
        organizacion_id=7, insumo=Obj(id=8, organizacion_id=7),
        OrdenCompraItem=Item, db_session=Session(),
    )
    assert len(compra.items) == 2
    assert compra.items[1].cantidad == Decimal("2.500000")
    assert compra.items[1].subtotal_centavos == 500000
    assert compra.total_centavos == 600000


def test_quita_item_de_borrador_y_recalcula_sin_borrar_ultimo():
    primero = Obj(id=1, subtotal_centavos=100000)
    segundo = Obj(id=2, subtotal_centavos=250000)
    compra = Obj(organizacion_id=7, estado="borrador", items=[primero, segundo])
    sesion = Session()
    quitar_item_orden(
        compra, primero, organizacion_id=7, db_session=sesion,
    )
    assert compra.items == [segundo]
    assert compra.total_centavos == 250000
    assert sesion.eliminados == [primero]
    try:
        quitar_item_orden(
            compra, segundo, organizacion_id=7, db_session=sesion,
        )
    except ValueError as error:
        assert "al menos un ítem" in str(error)
    else:
        raise AssertionError("Se eliminó el último ítem de la orden.")


def test_orden_aprobada_no_admite_edicion_de_items():
    compra = orden()
    compra.estado = "aprobada"
    try:
        agregar_item_orden(
            compra,
            {"cantidad": "1", "precio_unitario": "1",
             "descripcion": "X", "unidad_medida": "u"},
            organizacion_id=7, insumo=None,
            OrdenCompraItem=Item, db_session=Session(),
        )
    except ValueError as error:
        assert "borrador" in str(error)
    else:
        raise AssertionError("Se editó una orden aprobada.")


def test_ruta_y_panel_exponen_edicion_y_recepcion_parcial():
    rutas = Path("modules/admin/compras/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_compras.html").read_text(encoding="utf-8")
    modelo = Path("models/compras.py").read_text(encoding="utf-8")
    assert 'accion in {"agregar_item", "quitar_item"}' in rutas
    assert 'value="agregar_item"' in panel and 'value="quitar_item"' in panel
    assert "Preparar recepción parcial" in panel
    assert "uq_recepcion_compra_orden" not in modelo
