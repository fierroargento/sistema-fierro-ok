from pathlib import Path

from services.conciliacion_facturas_compra import registrar_factura_preparatoria


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


class Factura(Obj):
    pass


class Session:
    def __init__(self): self.items = []; self.commits = 0
    def add(self, item): self.items.append(item)
    def commit(self): self.commits += 1


def recepcion(subtotal=100000):
    return Obj(
        id=3, organizacion_id=7, unidad_negocio_id=9, estado="preparatoria",
        subtotal_centavos=subtotal, orden_compra_id=2,
        orden=Obj(proveedor_id=4),
    )


def registrar(total, recepcion_obj=None):
    return registrar_factura_preparatoria(
        {"tipo_comprobante": "A", "punto_venta": "12", "numero": "345", "total": total},
        recepcion=recepcion_obj or recepcion(), organizacion_id=7, unidad_negocio_id=9,
        FacturaProveedorCompra=Factura, db_session=Session(), usuario_id=5,
    )


def test_factura_igual_a_recepcion_queda_conciliada_sin_impactos():
    factura = registrar("1.000,00")
    assert factura.estado == "conciliada" and factura.diferencia_centavos == 0
    assert factura.impacta_fiscal is False and factura.obligacion_creada is False


def test_diferencia_de_importe_queda_observada():
    factura = registrar("1.100,00")
    assert factura.estado == "observada" and factura.diferencia_centavos == 10000
    assert "Diferencia" in factura.motivo_observacion


def test_aislamiento_tenant_y_recepcion_anulada():
    for rec, esperado in ((Obj(**{**recepcion().__dict__, "organizacion_id": 8}), "tenant"),
                          (Obj(**{**recepcion().__dict__, "estado": "anulada"}), "anulada")):
        try:
            registrar("1.000,00", rec)
        except ValueError as error:
            assert esperado in str(error)
        else:
            raise AssertionError("Se aceptó una factura fuera de frontera.")


def test_identidad_documental_es_unica_por_tenant_y_proveedor():
    modelo = Path("models/compras.py").read_text(encoding="utf-8")
    assert "uq_factura_proveedor_compra_tenant" in modelo
    assert "impacta_fiscal = false AND obligacion_creada = false" in modelo


def test_panel_y_ruta_no_ofrecen_ejecucion_productiva():
    panel = Path("templates/admin_compras.html").read_text(encoding="utf-8")
    rutas = Path("modules/admin/compras/routes.py").read_text(encoding="utf-8")
    servicio = Path("services/conciliacion_facturas_compra.py").read_text(encoding="utf-8")
    assert "Conciliar factura" in panel and 'accion == "registrar_factura"' in rutas
    for prohibido in ("requests.", "MovimientoInventario", "ObligacionCostoProductivo", "EventoFiscal"):
        assert prohibido not in servicio
