from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as Obj

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape
from services.historial_precios_observados import obtener_historial_precio


class Query:
    def __init__(self, rows): self.rows = rows
    def filter_by(self, **filters):
        return Query([r for r in self.rows if all(getattr(r, k) == v for k, v in filters.items())])
    def order_by(self, *fields):
        return Query(sorted(self.rows, key=lambda r: (r.fecha_observacion, r.id), reverse=True))
    def all(self): return self.rows[:]


@pytest.mark.parametrize('org,unit,lista,producto,expected', [(1,3,7,4,[2,1]),(2,3,7,4,[3]),(1,5,7,4,[4]),(1,3,8,4,[5]),(1,3,7,6,[6]),(1,3,7,9,[])])
def test_historial_aislado_y_ordenado(org, unit, lista, producto, expected):
    rows=[Obj(id=i,organizacion_id=o,unidad_negocio_id=u,lista_precio_id=l,catalogo_producto_id=p,tipo=t,fecha_observacion=datetime(2026,10,6)) for i,o,u,l,p,t in [(1,1,3,7,4,'precio'),(2,1,3,7,4,'precio'),(3,2,3,7,4,'precio'),(4,1,5,7,4,'precio'),(5,1,3,8,4,'precio'),(6,1,3,7,6,'precio'),(7,1,3,7,4,'cargo')]]
    model=Obj(query=Query(rows),fecha_observacion=Obj(desc=lambda:None),id=Obj(desc=lambda:None))
    result=obtener_historial_precio(org,unit,lista,producto,Observacion=model)
    assert [r.id for r in result]==expected
    assert len(rows)==7


@pytest.mark.parametrize('with_records',[False,True])
def test_popup_historial_escapado_y_fecha_argentina(with_records):
    record=Obj(catalogo_producto=Obj(sku_comercial='UAT-PROD-001'),lista_precio=Obj(nombre='Lista UAT'),fecha_observacion=datetime(2026,10,6,1,30),origen='manual',precio_publicado_centavos=720000,cuenta_codigo='<script>UAT</script>',referencia_publicacion='PUB-1',creado_por_username='Martín',lote_importacion_id=None)
    e=Environment(loader=FileSystemLoader('templates'),autoescape=select_autoescape())
    h=e.get_template('partials/precio_observado_historial.html').render(observaciones=[record] if with_records else [],unidad_activa=Obj(nombre='Ensayo UAT'),fecha_argentina=lambda d:d-timedelta(hours=3),formatear_centavos_ars=lambda n:f'{n/100:.2f}')
    if with_records:
        assert '05/10/2026 22:30' in h and '$ 7200.00' in h
        assert '&lt;script&gt;' in h and 'Martín' in h
    else: assert 'Todavía no hay precios observados' in h
    assert '<script>' not in h and '<form' not in h


def test_ruta_solo_lectura_y_guardia_unidad():
    s=Path('modules/admin/comercial/routes.py').read_text().split('def historial_precio_observado(',1)[1].split('@blueprint.route',1)[0]
    assert 'acceso()' in s and 'unidad_activa.id' in s and 'organizacion.id' in s
    assert '409' in s and 'request.args.get("unidad_negocio_id", type=int)' in s
    assert 'db.session' not in s and 'registrar_auditoria' not in s
