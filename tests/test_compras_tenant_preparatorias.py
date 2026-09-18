from decimal import Decimal
from pathlib import Path

from services.compras_nucleo import (
    cambiar_estado_orden,
    crear_orden,
    crear_proveedor,
    preparar_recepcion,
)


class Obj:
    def __init__(self, **datos):
        self.__dict__.update(datos)


class Session:
    def __init__(self):
        self.agregados = []
        self.commits = 0

    def add(self, item):
        self.agregados.append(item)

    def commit(self):
        self.commits += 1

    def delete(self, item):
        self.agregados.append(("eliminado", item))


class Proveedor(Obj):
    pass


class Item(Obj):
    pass


class Orden(Obj):
    def __init__(self, **datos):
        super().__init__(**datos)
        self.items = []


class Recepcion(Obj):
    def __init__(self, **datos):
        super().__init__(**datos)
        self.items = []


class RecepcionItem(Obj):
    pass


def test_proveedor_nace_dentro_del_tenant():
    sesion = Session()
    proveedor = crear_proveedor(
        {"codigo": " codimat ", "razon_social": "Codimat SRL", "cuit": "30-1"},
        organizacion_id=7, ProveedorCompra=Proveedor, db_session=sesion,
    )
    assert proveedor.organizacion_id == 7
    assert proveedor.codigo == "CODIMAT"
    assert sesion.agregados == [proveedor] and sesion.commits == 1


def test_orden_calcula_subtotal_y_nace_como_borrador():
    sesion = Session()
    proveedor = Obj(id=2, organizacion_id=7, estado="activo")
    insumo = Obj(id=3, organizacion_id=7)
    orden = crear_orden(
        {"numero": "oc-1", "cantidad": "2,5", "precio_unitario": "1.000,50",
         "descripcion": "Hierro", "unidad_medida": "kg"},
        organizacion_id=7, unidad_negocio_id=9, proveedor=proveedor, insumo=insumo,
        OrdenCompra=Orden, OrdenCompraItem=Item, db_session=sesion,
    )
    assert orden.estado == "borrador"
    assert orden.total_centavos == 250125
    assert orden.items[0].cantidad == Decimal("2.500000")
    assert orden.items[0].insumo_id == 3


def test_orden_rechaza_proveedor_de_otro_tenant():
    try:
        crear_orden(
            {"numero": "OC-1", "cantidad": "1", "precio_unitario": "1",
             "descripcion": "X", "unidad_medida": "u"},
            organizacion_id=7, unidad_negocio_id=9,
            proveedor=Obj(id=1, organizacion_id=8, estado="activo"), insumo=None,
            OrdenCompra=Orden, OrdenCompraItem=Item, db_session=Session(),
        )
    except ValueError as error:
        assert "tenant activo" in str(error)
    else:
        raise AssertionError("Se aceptó un proveedor de otro tenant.")


def test_flujo_de_aprobacion_no_permite_saltos():
    orden = Obj(organizacion_id=7, estado="borrador")
    sesion = Session()
    cambiar_estado_orden(orden, "en_revision", organizacion_id=7, db_session=sesion)
    cambiar_estado_orden(orden, "aprobada", organizacion_id=7, db_session=sesion)
    assert orden.estado == "aprobada"
    try:
        cambiar_estado_orden(orden, "borrador", organizacion_id=7, db_session=sesion)
    except ValueError as error:
        assert "no está permitida" in str(error)
    else:
        raise AssertionError("Se aceptó una transición inválida.")


def test_recepcion_preparatoria_copia_items_sin_impactar_stock_o_costos():
    orden = Obj(
        id=5, organizacion_id=7, unidad_negocio_id=9, estado="aprobada",
        items=[Obj(id=10, cantidad=Decimal("3.500000"))], recepciones=[],
    )
    recepcion = preparar_recepcion(
        {"numero": "RC-1", "comprobante_referencia": "FC-A"}, orden=orden,
        organizacion_id=7, unidad_negocio_id=9,
        RecepcionCompra=Recepcion, RecepcionCompraItem=RecepcionItem,
        db_session=Session(),
    )
    assert recepcion.estado == "preparatoria"
    assert recepcion.impacta_stock is False and recepcion.impacta_costos is False
    assert recepcion.items[0].cantidad_recibida == Decimal("3.500000")


def test_recepcion_parcial_respeta_el_saldo_pendiente_acumulado():
    orden = Obj(
        id=5, organizacion_id=7, unidad_negocio_id=9, estado="aprobada",
        items=[Obj(id=10, cantidad=Decimal("5"), descripcion="Hierro")],
        recepciones=[Obj(
            estado="preparatoria",
            items=[Obj(orden_compra_item_id=10, cantidad_recibida=Decimal("2"))],
        )],
    )
    nueva = preparar_recepcion(
        {"numero": "RC-2", "cantidad_10": "3"}, orden=orden,
        organizacion_id=7, unidad_negocio_id=9, RecepcionCompra=Recepcion,
        RecepcionCompraItem=RecepcionItem, db_session=Session(),
    )
    assert nueva.items[0].cantidad_recibida == Decimal("3.000000")
    try:
        preparar_recepcion(
            {"numero": "RC-3", "cantidad_10": "4"}, orden=orden,
            organizacion_id=7, unidad_negocio_id=9, RecepcionCompra=Recepcion,
            RecepcionCompraItem=RecepcionItem, db_session=Session(),
        )
    except ValueError as error:
        assert "supera" in str(error)
    else:
        raise AssertionError("Se recibió más que la cantidad pendiente.")


def test_modelo_impide_recepcion_con_impacto_automatico():
    modelo = Path("models/compras.py").read_text(encoding="utf-8")
    servicio = Path("services/compras_nucleo.py").read_text(encoding="utf-8")
    assert "impacta_stock = false AND impacta_costos = false" in modelo
    assert "impacta_stock=False, impacta_costos=False" in servicio
    for prohibido in ("MovimientoInventario", "InsumoPrecioVersion", "requests.", "http://", "https://"):
        assert prohibido not in servicio


def test_panel_y_rutas_son_tenant_y_administrativas():
    rutas = Path("modules/admin/compras/routes.py").read_text(encoding="utf-8")
    bootstrap = Path("services/bootstrap_modulos_web.py").read_text(encoding="utf-8")
    template = Path("templates/admin_compras.html").read_text(encoding="utf-8")
    fuentes = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")
    assert 'Blueprint("admin_compras"' in rutas
    assert 'membresia.rol != "admin"' in rutas
    assert "organizacion_id=organizacion.id" in rutas
    assert "crear_blueprint_compras" in bootstrap
    assert "no impactan stock ni costos" in template
    assert "admin_compras.panel" in fuentes


def test_tablas_nuevas_son_aditivas_y_registradas_en_app():
    app = Path("app.py").read_text(encoding="utf-8")
    modelo = Path("models/compras.py").read_text(encoding="utf-8")
    for nombre in (
        "ProveedorCompra", "OrdenCompra", "OrdenCompraItem",
        "RecepcionCompra", "RecepcionCompraItem",
    ):
        assert f'"{nombre}": {nombre}' in app
        assert f"class {nombre}" in modelo
