from datetime import datetime
from types import SimpleNamespace as Obj
from jinja2 import Environment, FileSystemLoader, select_autoescape
import pytest
from services.historial_costos_productos import obtener_historial_costo_producto


class Query:
    def __init__(self, rows):
        self.rows = rows
    def filter_by(self, **filters):
        self.filters = filters
        return self
    def order_by(self, order):
        return self
    def all(self):
        return sorted([r for r in self.rows if all(getattr(r, k) == v for k, v in self.filters.items())], key=lambda r: r.numero_version, reverse=True)


@pytest.mark.parametrize('org,unit,product,expected', [(1,3,7,[2,1]),(2,3,7,[8]),(1,4,7,[9]),(1,3,8,[])])
def test_historial_respeta_organizacion_unidad_y_producto(org, unit, product, expected):
    rows = [Obj(organizacion_id=o, unidad_negocio_id=u, producto_id=7, numero_version=n) for o,u,n in [(1,3,1),(1,3,2),(2,3,8),(1,4,9)]]
    model = Obj(query=Query(rows), numero_version=Obj(desc=lambda: None))
    result = obtener_historial_costo_producto(org, unit, product, Costo=model)
    assert [r.numero_version for r in result] == expected


@pytest.mark.parametrize('con_detalle', [True,False])
def test_popup_muestra_snapshot_escapado_sin_acciones_de_escritura(con_detalle):
    env = Environment(loader=FileSystemLoader('templates'), autoescape=select_autoescape())
    detail=Obj(concepto='<script>UAT</script>', tipo='insumo', codigo='MP-1', cantidad=2, unidad_medida='kg', costo_unitario_centavos=1000, porcentaje_merma=5, subtotal_centavos=2100, observacion='Original')
    version=Obj(numero_version=1, estado='vigente', fecha_creacion=datetime(2026,9,29), tipo='calculado', moneda='ARS', costo_total_centavos=2100, vigente_desde=None, observacion=None, detalles=[detail] if con_detalle else [])
    html=env.get_template('partials/costo_producto_historial.html').render(producto=Obj(sku='UAT-001',descripcion='Prueba'), unidad_activa=Obj(nombre='Ensayo UAT'), versiones=[version],formatear_centavos_ars=lambda n:f'{n/100:.2f}')
    assert 'Historial de costos (1)' in html
    assert '$ 21.00' in html
    if con_detalle:
        assert '&lt;script&gt;UAT&lt;/script&gt;' in html
    else:
        assert 'Esta versión no tiene desglose guardado.' in html
    assert '<script>' not in html
    assert '<form' not in html
    assert detail.subtotal_centavos == 2100
