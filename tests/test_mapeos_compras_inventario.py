import json
from pathlib import Path

from services.mapeos_compras_inventario import (
    crear_mapeo,
    habilitar_propuestas_stock,
)
from services.propuestas_impacto_compra import preparar_propuestas


class Obj:
    def __init__(self, **datos):
        self.__dict__.update(datos)


class Query:
    def filter_by(self, **_filtros):
        return self

    def all(self):
        return []


class Mapeo(Obj):
    pass


class Propuesta(Obj):
    query = Query()


class Session:
    def __init__(self):
        self.agregados = []
        self.commits = 0

    def add(self, item):
        self.agregados.append(item)

    def commit(self):
        self.commits += 1


def test_crea_mapeo_solo_con_insumo_y_existencia_del_tenant():
    sesion = Session()
    mapeo = crear_mapeo(
        organizacion_id=7, unidad_negocio_id=9,
        insumo=Obj(id=2, organizacion_id=7),
        existencia=Obj(id=3, organizacion_id=7),
        MapeoInsumoInventario=Mapeo, db_session=sesion, usuario_id=4,
    )
    assert mapeo.insumo_id == 2 and mapeo.existencia_sucursal_id == 3
    assert mapeo.organizacion_id == 7 and mapeo.unidad_negocio_id == 9
    assert mapeo.activo is True and sesion.commits == 1


def test_rechaza_mapeo_cruzado_entre_tenants():
    try:
        crear_mapeo(
            organizacion_id=7, unidad_negocio_id=9,
            insumo=Obj(id=2, organizacion_id=7),
            existencia=Obj(id=3, organizacion_id=8),
            MapeoInsumoInventario=Mapeo, db_session=Session(),
        )
    except ValueError as error:
        assert "tenant" in str(error)
    else:
        raise AssertionError("Se aceptó una existencia de otro tenant.")


def test_mapeo_habilita_propuesta_bloqueada_sin_ejecutarla():
    propuesta = Obj(
        tipo="stock", estado="bloqueada", ejecutada=False,
        detalle_json=json.dumps({
            "insumo_id": 2, "requiere_mapeo_item_inventario": True,
            "movimiento_creado": False,
        }),
    )
    mapeo = Obj(id=5, insumo_id=2, existencia_sucursal_id=8, activo=True)
    habilitadas = habilitar_propuestas_stock(
        [propuesta], [mapeo], db_session=Session(),
    )
    detalle = json.loads(propuesta.detalle_json)
    assert habilitadas == [propuesta] and propuesta.estado == "preparada"
    assert propuesta.ejecutada is False
    assert detalle["existencia_sucursal_id"] == 8
    assert detalle["movimiento_creado"] is False


def test_preparacion_nueva_usa_mapeo_existente_desde_el_inicio():
    recibido = Obj(
        id=30, cantidad_recibida="2",
        orden_item=Obj(insumo_id=2, precio_unitario_centavos=100),
    )
    recepcion = Obj(
        id=10, organizacion_id=7, unidad_negocio_id=9,
        estado="preparatoria", items=[recibido],
        orden=Obj(proveedor_id=4, total_centavos=200),
        comprobante_referencia="FC",
    )
    mapeo = Obj(id=5, insumo_id=2, existencia_sucursal_id=8, activo=True)
    creadas = preparar_propuestas(
        recepcion, organizacion_id=7, unidad_negocio_id=9,
        PropuestaImpactoCompra=Propuesta, db_session=Session(), mapeos=[mapeo],
    )
    stock = next(item for item in creadas if item.tipo == "stock")
    assert stock.estado == "preparada"
    assert json.loads(stock.detalle_json)["existencia_sucursal_id"] == 8
    assert stock.ejecutada is False


def test_modelo_mantiene_un_mapeo_activo_por_insumo_y_unidad():
    modelo = Path("models/compras.py").read_text(encoding="utf-8")
    assert "class MapeoInsumoInventario" in modelo
    assert "uq_mapeo_insumo_inventario_tenant_unidad" in modelo
    assert "existencia_sucursal_id" in modelo


def test_panel_registra_mapeo_pero_no_movimientos():
    rutas = Path("modules/admin/compras/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_compras.html").read_text(encoding="utf-8")
    servicio = Path("services/mapeos_compras_inventario.py").read_text(encoding="utf-8")
    assert 'accion == "crear_mapeo_inventario"' in rutas
    assert "Mapeo de insumos a inventario" in panel
    assert "no mueve existencias" in panel
    for prohibido in ("MovimientoInventario", "stock_actual", "db.session", "requests."):
        assert prohibido not in servicio
