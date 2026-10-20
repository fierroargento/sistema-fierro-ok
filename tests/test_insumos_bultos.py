"""Importación real con BD aislada; las dos acciones se cargan sin el monolito."""
import ast
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
import pytest
from extensions import db
from models.organizacion import Organizacion
from models.unidad_negocio import UnidadNegocio
from models.fuentes_costo_productivo import InsumoProductivo, InsumoPrecioVersion
from models.insumo_presentacion_compra import InsumoPresentacionCompra, InsumoPrecioBultoVersion
from services.fuentes_costo_productivo import crear_insumo, registrar_precio_insumo
from services.catalogos_comerciales import importe_a_centavos
from services.insumos_presentacion import preparar_precio, leer
from services.importacion_fuentes_costeo import previsualizar_fuentes, sugerir_mapeo_fuente, aplicar_fuentes
from scripts.preparar_bultos_insumos import preparar
from test_producto_ficha_maestra import entorno
from test_producto_datos_generales import completo
from test_producto_fabricacion_maestro import fabricacion


@pytest.fixture()
def bultos(fabricacion, monkeypatch):
    preparar(db.engine)
    app, org, otra, unidad, *_ = fabricacion
    # Se ejecuta el código de las acciones reales y los servicios reales de BD.
    # Se excluyen imports de módulos operativos ajenos que no están en este checkout.
    modulo = ModuleType('services.fuentes_costo_admin')
    tree = ast.parse(Path('services/fuentes_costo_admin.py').read_text())
    tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {'_id', '_registro_tenant', '_comunes', 'procesar_accion_fuente_costo'}]
    modulo.__dict__.update(crear_insumo=crear_insumo, registrar_precio_insumo=registrar_precio_insumo, importe_a_centavos=importe_a_centavos, Decimal=Decimal)
    exec(compile(tree, 'services/fuentes_costo_admin.py', 'exec'), modulo.__dict__)
    monkeypatch.setitem(sys.modules, 'services.fuentes_costo_admin', modulo)
    modelos = {'Organizacion': Organizacion, 'UnidadNegocio': UnidadNegocio, 'InsumoProductivo': InsumoProductivo, 'InsumoPrecioVersion': InsumoPrecioVersion}
    def aplicar(datos, accion='crear_insumo'):
        return modulo.procesar_accion_fuente_costo(accion, dict(datos, unidad_negocio_id=str(unidad.id)), organizacion=org,
            unidad_activa=unidad, modelos=modelos, db_session=db.session, usuario=SimpleNamespace(id=None))
    yield fabricacion, modelos, aplicar
    db.session.rollback()
    db.metadata.drop_all(db.engine, tables=[InsumoPrecioBultoVersion.__table__, InsumoPresentacionCompra.__table__])


def fila(**kw):
    return dict(codigo='BARRA-UAT', nombre='Barra UAT', tipo='materia_prima', unidad_medida='metro',
        precio_unitario='100', cantidad_bulto='6', medidas_origen='Barra de 6 m', proveedor_referencia='Proveedor UAT', **kw)


def test_unitario_no_se_divide_y_bulto_conserva_precio_real_y_historia(bultos):
    f, _, aplicar = bultos; aplicar(fila())
    i = InsumoProductivo.query.filter_by(codigo='barra-uat').one()
    v = InsumoPrecioVersion.query.filter_by(insumo_id=i.id, vigente=True).one()
    assert v.precio_unitario_centavos == 10000
    p = leer(db.session, f[1].id, f[3].id)[i.id]
    assert p['cantidad_bulto'] == 6 and p['precio_bulto_centavos'] == 60000 and p['base_precio'] == 'unitario'
    aplicar(dict(insumo_id=str(i.id), precio_unitario='', precio_bulto='100', cantidad_bulto='6', base_precio='bulto'), 'actualizar_precio_insumo')
    nuevo = InsumoPrecioVersion.query.filter_by(insumo_id=i.id, vigente=True).one()
    assert nuevo.precio_unitario_centavos == 1667  # 100/6 redondeado al centavo.
    p = leer(db.session, f[1].id, f[3].id)[i.id]
    assert p['precio_bulto_centavos'] == 10000  # Conserva 100, no reconstruye 100,02.
    assert p['historial'][v.id]['precio_bulto_centavos'] == 60000
    assert p['historial'][nuevo.id]['base_precio'] == 'bulto'


def test_importador_mapea_bulto_y_aplica_una_vez(bultos):
    f, modelos, _ = bultos
    h = ['Código', 'Nombre', 'Tipo', 'Unidad de medida', 'Precio unitario', 'Proveedor', 'Cantidad por bulto', 'Medidas en origen', 'Cotización', 'Precio por bulto']
    m = sugerir_mapeo_fuente('insumos', h)
    registros = [{'numero': 2, 'valores': ['CAJA-UAT', 'Caja UAT', 'materia_prima', 'unidad', '', 'Proveedor', '500', '', 'bulto', '12500']}]
    vista = previsualizar_fuentes('insumos', registros, m, organizacion_id=f[1].id, unidad_negocio_id=f[3].id, modelos=modelos)
    assert vista[0]['accion'] == 'crear' and not InsumoProductivo.query.filter_by(codigo='caja-uat').first()
    resultado = aplicar_fuentes('insumos', vista, organizacion=f[1], unidad_activa=f[3], modelos=modelos, db_session=db.session, usuario=None)
    assert resultado['creados'] == 1
    i = InsumoProductivo.query.filter_by(codigo='caja-uat').one()
    assert InsumoPrecioVersion.query.filter_by(insumo_id=i.id).one().precio_unitario_centavos == 2500
    assert leer(db.session, f[1].id, f[3].id)[i.id]['cantidad_bulto'] == 500


def test_formulario_anterior_y_blancos_conservan_bulto(bultos):
    f, _, aplicar = bultos; aplicar(fila())
    i = InsumoProductivo.query.filter_by(codigo='barra-uat').one()
    aplicar(dict(insumo_id=str(i.id), precio_unitario='120', cantidad_bulto='', medidas_origen=''), 'actualizar_precio_insumo')
    p = leer(db.session, f[1].id, f[3].id)[i.id]
    assert p['cantidad_bulto'] == 6 and p['medidas_origen'] == 'Barra de 6 m' and p['precio_bulto_centavos'] == 72000


@pytest.mark.parametrize('cantidad', ['0', '-1', 'NaN', 'Infinity', '1.1234567', '1,8*2,6', '1000000000000'])
def test_rechaza_bulto_invalido(cantidad):
    with pytest.raises(ValueError): preparar_precio(dict(precio_unitario='100', cantidad_bulto=cantidad))


@pytest.mark.parametrize('datos', [dict(base_precio='bulto', precio_bulto='600'), dict(base_precio='bulto', cantidad_bulto='6'),
    dict(base_precio='otro', precio_unitario='100'), dict(precio_unitario='100', precio_bulto='100', cantidad_bulto='6'),
    dict(precio_unitario='NaN'), dict(precio_bulto='-1', cantidad_bulto='6')])
def test_rechaza_precio_ambiguo_o_faltante(datos):
    with pytest.raises(ValueError): preparar_precio(datos)


def test_precio_cero_es_explicito_y_fracciones_son_validas():
    assert preparar_precio(dict(precio_unitario='0'))['unitario_centavos'] == 0
    assert preparar_precio(dict(precio_bulto='0', cantidad_bulto='6', base_precio='bulto'))['unitario_centavos'] == 0
    assert preparar_precio(dict(precio_bulto='50', cantidad_bulto='2,5', base_precio='bulto'))['unitario_centavos'] == 2000
    # Exportación y reimportación de un total redondeado no cambia la base unitaria.
    assert preparar_precio(dict(precio_unitario='.01', cantidad_bulto='.003', precio_bulto='0', base_precio='unitario'))['unitario_centavos'] == 1
    with pytest.raises(ValueError, match='fuera de rango'):
        preparar_precio(dict(precio_unitario='999999999999', cantidad_bulto='999999999999'))


def test_fallo_al_guardar_snapshot_revierte_insumo_presentacion_y_precio(bultos, monkeypatch):
    import services.insumos_presentacion as servicio
    _, _, aplicar = bultos
    real = servicio.guardar_precio
    def fallo(*args, **kwargs):
        real(*args, **kwargs); raise ValueError('Fallo de ensayo')
    monkeypatch.setattr(servicio, 'guardar_precio', fallo)
    with pytest.raises(ValueError): aplicar(fila())
    db.session.rollback()
    assert not InsumoProductivo.query.filter_by(codigo='barra-uat').first()
    assert InsumoPresentacionCompra.query.count() == 0 and InsumoPrecioBultoVersion.query.count() == 0


def test_sin_preparar_no_rompe_lectura_y_rechaza_sin_alta_parcial(bultos):
    f, _, aplicar = bultos
    db.metadata.drop_all(db.engine, tables=[InsumoPrecioBultoVersion.__table__, InsumoPresentacionCompra.__table__])
    assert leer(db.session, f[1].id, f[3].id) == {}
    with pytest.raises(ValueError, match='preparar'): aplicar(fila())
    db.session.rollback()
    assert not InsumoProductivo.query.filter_by(codigo='barra-uat').first()
    preparar(db.engine)


def test_importacion_sin_esquema_rechaza_antes_de_la_primera_fila(bultos):
    f, modelos, _ = bultos
    db.metadata.drop_all(db.engine, tables=[InsumoPrecioBultoVersion.__table__, InsumoPresentacionCompra.__table__])
    vista = [{'accion': 'crear', 'datos': dict(fila(), cantidad_bulto='')},
             {'accion': 'crear', 'datos': dict(fila(), codigo='OTRO-UAT')}]
    with pytest.raises(ValueError, match='preparar'):
        aplicar_fuentes('insumos', vista, organizacion=f[1], unidad_activa=f[3], modelos=modelos, db_session=db.session, usuario=None)
    assert not InsumoProductivo.query.filter_by(codigo='barra-uat').first()
    preparar(db.engine)


def test_tenant_y_unidad_no_cruzan_presentaciones(bultos):
    f, modelos, aplicar = bultos; aplicar(fila())
    assert leer(db.session, f[2].id, f[3].id) == {}
    i = InsumoProductivo.query.filter_by(codigo='barra-uat').one()
    with pytest.raises(ValueError, match='unidad no coincide'):
        aplicar(dict(insumo_id=str(i.id), precio_unitario='100', unidad_medida='kg'), 'actualizar_precio_insumo')
    db.session.rollback()
    assert i.unidad_medida == 'metro'


def test_script_idempotente_e_independiente_del_monolito(bultos, tmp_path):
    import sqlite3, subprocess, os
    f, _, aplicar = bultos; aplicar(fila())
    preparar(db.engine); preparar(db.engine)
    archivo = tmp_path / 'staging.sqlite'
    destino = sqlite3.connect(str(archivo)); origen = db.engine.raw_connection()
    origen.driver_connection.backup(destino); origen.close(); destino.close()
    env = dict(os.environ, DATABASE_URL='sqlite:///' + str(archivo), MODO_LABORATORIO_DESCONECTADO='true', RENDER_GIT_BRANCH='integracion-saas-2026-09', RENDER_EXTERNAL_URL='https://fierro-staging.onrender.com')
    orden = [sys.executable, '-m', 'scripts.preparar_bultos_insumos', '--staging']
    r = subprocess.run(orden, env=env, capture_output=True, text=True, timeout=20)
    assert r.returncode == 0, r.stderr
    env['RENDER_GIT_BRANCH'] = 'main'
    r = subprocess.run(orden, env=env, capture_output=True, text=True, timeout=20)
    assert r.returncode != 0 and 'no es integración' in r.stderr
