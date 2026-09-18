import json
from pathlib import Path

from services.propuestas_impacto_compra import decidir_propuesta, preparar_propuestas


class Obj:
    def __init__(self, **datos):
        self.__dict__.update(datos)


class Query:
    def __init__(self, registros=None):
        self.registros = registros or []

    def filter_by(self, **_filtros):
        return self

    def all(self):
        return self.registros


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


def recepcion(insumo_id=20):
    orden_item = Obj(
        insumo_id=insumo_id, precio_unitario_centavos=150000,
    )
    recibido = Obj(id=30, cantidad_recibida="2.500000", orden_item=orden_item)
    orden = Obj(proveedor_id=40, total_centavos=375000)
    return Obj(
        id=10, organizacion_id=7, unidad_negocio_id=9,
        estado="preparatoria", items=[recibido], orden=orden,
        comprobante_referencia="FC-1",
    )


def test_recepcion_prepara_costo_stock_y_cuenta_pagar_sin_ejecutarlos():
    Propuesta.query = Query()
    sesion = Session()
    creadas = preparar_propuestas(
        recepcion(), organizacion_id=7, unidad_negocio_id=9,
        PropuestaImpactoCompra=Propuesta, db_session=sesion, usuario_id=4,
    )
    assert [item.tipo for item in creadas] == ["costo", "stock", "cuenta_pagar"]
    assert creadas[0].estado == "preparada"
    assert creadas[1].estado == "bloqueada"
    assert all(item.ejecutada is False for item in creadas)
    assert sesion.commits == 1


def test_propuesta_stock_declara_mapeo_pendiente_y_cero_movimientos():
    Propuesta.query = Query()
    creadas = preparar_propuestas(
        recepcion(), organizacion_id=7, unidad_negocio_id=9,
        PropuestaImpactoCompra=Propuesta, db_session=Session(),
    )
    stock = next(item for item in creadas if item.tipo == "stock")
    detalle = json.loads(stock.detalle_json)
    assert detalle["requiere_mapeo_item_inventario"] is True
    assert detalle["movimiento_creado"] is False


def test_insumo_sin_vinculo_bloquea_tambien_la_actualizacion_de_costo():
    Propuesta.query = Query()
    creadas = preparar_propuestas(
        recepcion(insumo_id=None), organizacion_id=7, unidad_negocio_id=9,
        PropuestaImpactoCompra=Propuesta, db_session=Session(),
    )
    costo = next(item for item in creadas if item.tipo == "costo")
    assert costo.estado == "bloqueada"


def test_claves_existentes_hacen_la_preparacion_idempotente():
    Propuesta.query = Query([
        Obj(clave_idempotencia="recepcion:10:costo:30"),
        Obj(clave_idempotencia="recepcion:10:stock:30"),
        Obj(clave_idempotencia="recepcion:10:cuenta_pagar:orden"),
    ])
    creadas = preparar_propuestas(
        recepcion(), organizacion_id=7, unidad_negocio_id=9,
        PropuestaImpactoCompra=Propuesta, db_session=Session(),
    )
    assert creadas == []


def test_aprobacion_interna_no_marca_propuesta_como_ejecutada():
    propuesta = Obj(organizacion_id=7, estado="preparada", ejecutada=False)
    decidir_propuesta(
        propuesta, "aprobar", "", organizacion_id=7,
        db_session=Session(), usuario_id=4,
    )
    assert propuesta.estado == "aprobada"
    assert propuesta.ejecutada is False
    assert propuesta.decidido_por_usuario_id == 4


def test_rechazo_exige_motivo_y_aislamiento_tenant():
    propuesta = Obj(organizacion_id=7, estado="preparada", ejecutada=False)
    for organizacion_id, motivo, esperado in ((8, "x", "tenant"), (7, "", "motivo")):
        try:
            decidir_propuesta(
                propuesta, "rechazar", motivo, organizacion_id=organizacion_id,
                db_session=Session(),
            )
        except ValueError as error:
            assert esperado in str(error).lower()
        else:
            raise AssertionError("Se aceptó una decisión inválida.")


def test_frontera_no_importa_consumidores_productivos():
    servicio = Path("services/propuestas_impacto_compra.py").read_text(encoding="utf-8")
    modelo = Path("models/compras.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_compras.html").read_text(encoding="utf-8")
    assert "ejecutada = false" in modelo
    assert "Nunca crea movimientos, costos u obligaciones" in panel
    for prohibido in (
        "MovimientoInventario", "InsumoPrecioVersion", "ObligacionCostoProductivo",
        "requests.", "http://", "https://",
    ):
        assert prohibido not in servicio


def test_modelo_y_blueprint_registran_propuestas_explicitamente():
    app = Path("app.py").read_text(encoding="utf-8")
    bootstrap = Path("services/bootstrap_modulos_web.py").read_text(encoding="utf-8")
    rutas = Path("modules/admin/compras/routes.py").read_text(encoding="utf-8")
    assert '"PropuestaImpactoCompra": PropuestaImpactoCompra' in app
    assert '"PropuestaImpactoCompra"' in bootstrap
    assert 'accion == "preparar_impactos"' in rutas
    assert 'accion == "decidir_impacto"' in rutas
