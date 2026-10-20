"""Importación completa aislada: sin stock, conexiones ni archivos privados."""
from io import BytesIO
from types import SimpleNamespace
from decimal import Decimal
import pytest
from werkzeug.datastructures import FileStorage
from openpyxl import Workbook
from extensions import db
from models.producto import Producto
from models.producto_despiece_costeo import ProductoDespieceCosteo
from models.producto_datos_generales import ProductoDatosGenerales
from models.costo_producto_version import CostoProductoVersion
from models.fuentes_costo_productivo import InsumoPrecioVersion
from services import importacion_fabricacion_productos as servicio
from test_producto_ficha_maestra import entorno,crear
from test_producto_datos_generales import completo
from test_producto_fabricacion_maestro import fabricacion
from test_producto_despiece import despiece


def lote(skus=('NUEVO',),laser=False):
    tablas={k:[] for k in ('Productos','Componentes','Tareas','Resumen Producto')}
    for n,sku in enumerate(skus,2):
        tablas['Productos'].append({'numero':n,'valores':[sku,'Producto '+sku,'Laser' if laser else 'Herrería','Descripción opcional','Sí']})
        tablas['Componentes'].append({'numero':n,'valores':[sku,'MDF',None,None,'Pieza',40,2,'metro',None,None,None,None] if not laser else [sku,'MDF',None,None,'Corte',None,2,'unidad',None,8,10,None]})
        if not laser:tablas['Tareas'].append({'numero':n,'valores':[sku,'Soldar',60]})
        tablas['Resumen Producto'].append({'numero':n,'valores':[sku,None,None,None,None,None,0.9,None,0.21,None,0.035]})
    return {'tablas':tablas,'archivo_sha256':'abc'}


def opciones(d):
    f,_=d
    return {'tarifa_herreria':str(f[5].id),'tarifa_laser':str(f[5].id),'maquina_laser':str(f[6].id),'habilita_venta':'1'}


def preview(d,datos=None,opts=None):
    return servicio.previsualizar(datos or lote(),opciones=opts or opciones(d),Producto=Producto,session=db.session,organizacion_id=d[0][1].id)


def aplicar(d,v,**kw):
    return servicio.aplicar(servicio.firmar(v,d[0][1].id,1,'clave'),organizacion_id=d[0][1].id,usuario=SimpleNamespace(id=1,nombre='UAT'),secreto='clave',Producto=Producto,session=db.session,**kw)


def libro(datos=None):
    w=Workbook();w.remove(w.active)
    headers={'Productos':['ID Producto','Nombre','Línea','Descripción','Activo (Sí/No)'],
        'Componentes':['ID Producto','Codigo Proveedor','Nombre Producto','Componente','Descripcion','Medida Cm','Cantidad','Unidad','Total','Cantidad Placa Entera','Tiempo 1/4 placa','Cantidad x Carton'],
        'Tareas':['ID Producto','Tarea','Segundos'],
        'Resumen Producto':['ID Producto','Nombre Producto','Minutos Totales','Mano obra Neto','Insumos Neto','Costo Neto','Margen %','Sugerido Neto','IVA (21%)','IVA ($)','IIBB (%)']}
    for nombre,columnas in headers.items():
        ws=w.create_sheet(nombre);ws.append(columnas)
        for r in (datos or lote())['tablas'][nombre]:ws.append(r['valores'])
    b=BytesIO();w.save(b);b.seek(0);return b


def test_lectura_y_formulas_solo_en_columnas_calculadas():
    d=lote();d['tablas']['Componentes'][0]['valores'][2]='=FORMULA.NO.EJECUTAR()'
    leido=servicio.leer(FileStorage(libro(d),filename='general.xlsm'))
    assert len(leido['tablas']['Productos'])==1
    assert leido['tablas']['Componentes'][0]['valores'][2].startswith('=')
    with pytest.raises(ValueError,match='XLSX'):servicio.leer(FileStorage(libro(),filename='general.csv'))
    with pytest.raises(ValueError,match='válido'):servicio.leer(FileStorage(BytesIO(b'roto'),filename='general.xlsx'))
    d['tablas']['Tareas'][0]['valores'][0]='HUERFANO'
    with pytest.raises(ValueError,match='sin ficha'):servicio.leer(FileStorage(libro(d),filename='general.xlsx'))


def test_preview_sin_escrituras_y_aplicacion_completa(despiece):
    from sqlalchemy import event
    sentencias=[]
    def registrar(conn,cursor,statement,*args):sentencias.append(statement)
    event.listen(db.engine,'before_cursor_execute',registrar)
    try:v=preview(despiece)
    finally:event.remove(db.engine,'before_cursor_execute',registrar)
    f=v['filas'][0];assert f['errores']==[],f
    assert not any(s.lstrip().split()[0].upper() in ('INSERT','UPDATE','DELETE') for s in sentencias)
    assert f['costo_centavos']==8050
    assert Producto.query.count()==0
    assert aplicar(despiece,v)=={'creados':1,'conservados':0,'excluidos':0}
    p=Producto.query.one();assert p.sku=='NUEVO'
    assert ProductoDespieceCosteo.query.count()==1
    a=ProductoDatosGenerales.query.one();assert (a.utilidad_pct,a.iva_pct,a.iibb_pct)==(90,21,Decimal('3.5'))
    assert not CostoProductoVersion.query.one().vigente
    with pytest.raises(ValueError,match='ya existe'):aplicar(despiece,v)
    assert Producto.query.count()==1


def test_conserva_sku_existente_y_excluye_cinco_llaveros(despiece):
    org=despiece[0][1];p=crear(org,sku='PP6040H',nombre='Manual validado')
    v=preview(despiece,lote(('PP6040H',*sorted(servicio.EXCLUIDOS),'NUEVO')))
    assert [f['accion'] for f in v['filas']]==['conservar']+['excluido']*5+['crear']
    assert aplicar(despiece,v)=={'creados':1,'conservados':1,'excluidos':5}
    from models.producto_ficha_maestra import ProductoFichaMaestra
    assert ProductoFichaMaestra.query.filter_by(producto_id=p.id).one().nombre=='Manual validado'


def test_laser_rendimiento_cantidad_tiempo_maquina_y_mano_obra(despiece):
    v=preview(despiece,lote(laser=True));f=v['filas'][0]
    assert not f['errores'],f
    assert f['produccion']['tareas'][0]['segundos']=='600.000000'
    assert f['produccion']['maquinas'][0]['minutos']=='10.0000'
    assert f['avisos']
    # Material 2/8 * 10000 + 10 min * (50 MO +20 máquina)
    assert f['costo_centavos']==3200
    aplicar(despiece,v)
    assert ProductoDespieceCosteo.query.count()==1


@pytest.mark.parametrize('fallo',['material','tarifa','precio','unidad','duplicado','formula','linea','componente_vacio','doble_tiempo'])
def test_rechazos_no_guardan_nada(despiece,fallo):
    d=lote();opts=opciones(despiece)
    if fallo=='material':d['tablas']['Componentes'][0]['valores'][1]='NO-EXISTE'
    if fallo=='tarifa':opts['tarifa_herreria']=''
    if fallo=='precio':db.session.query(InsumoPrecioVersion).update({'vigente':False});db.session.commit()
    if fallo=='unidad':opts['unidad_id']='999999'
    if fallo=='duplicado':d=lote(('NUEVO','NUEVO'))
    if fallo=='formula':d['tablas']['Tareas'][0]['valores'][2]='=60'
    if fallo=='linea':d['tablas']['Productos'][0]['valores'][2]='Otro'
    if fallo=='componente_vacio':d['tablas']['Componentes']=[]
    if fallo=='doble_tiempo':d=lote(laser=True);d['tablas']['Tareas']=[{'numero':2,'valores':['NUEVO','Corte',60]}]
    if fallo=='unidad':
        with pytest.raises(ValueError):preview(despiece,d,opts)
    else:
        v=preview(despiece,d,opts)
        assert v['filas'][0]['errores'],v
        with pytest.raises(ValueError):aplicar(despiece,v)
    assert Producto.query.count()==0


def test_cambio_de_precio_y_alta_concurrente_rechazan_atomico(despiece):
    v=preview(despiece,lote(('UNO','DOS')))
    db.session.query(InsumoPrecioVersion).update({'precio_unitario_centavos':20000});db.session.commit()
    with pytest.raises(ValueError,match='Cambiaron los costos'):aplicar(despiece,v)
    assert Producto.query.count()==0
    v=preview(despiece,lote(('UNO','DOS')));crear(despiece[0][1],sku='DOS')
    with pytest.raises(ValueError,match='ya existe'):aplicar(despiece,v)
    assert Producto.query.count()==1


def test_fallo_segunda_ficha_revierte_todo(despiece,monkeypatch):
    import services.productos_produccion_maestro as motor
    v=preview(despiece,lote(('UNO','DOS')));real=motor.guardar;veces=[]
    def falla(*a,**kw):
        real(*a,**kw);veces.append(1)
        if len(veces)==2:raise ValueError('Fallo final de prueba')
    monkeypatch.setattr(motor,'guardar',falla)
    with pytest.raises(ValueError,match='Fallo final'):aplicar(despiece,v)
    assert Producto.query.count()==ProductoDespieceCosteo.query.count()==CostoProductoVersion.query.count()==0


def test_token_usuario_firma_y_vencimiento(despiece,monkeypatch):
    from itsdangerous import TimestampSigner
    v=preview(despiece);token=servicio.firmar(v,despiece[0][1].id,2,'clave')
    kwargs=dict(organizacion_id=despiece[0][1].id,usuario=SimpleNamespace(id=1),secreto='clave',Producto=Producto,session=db.session)
    with pytest.raises(ValueError,match='usuario y organización'):servicio.aplicar(token,**kwargs)
    with pytest.raises(ValueError,match='venció'):servicio.aplicar(token+'x',**kwargs)
    monkeypatch.setattr(TimestampSigner,'get_timestamp',lambda self:1)
    token=servicio.firmar(v,despiece[0][1].id,1,'clave')
    monkeypatch.undo()
    with pytest.raises(ValueError,match='venció'):servicio.aplicar(token,**kwargs)


def test_ruta_real_preview_confirmacion_csrf_y_cancelar(despiece):
    app=despiece[0][0];cliente=app.test_client()
    datos=opciones(despiece)|{'accion':'previsualizar_fabricacion','_csrf_token':'csrf-test','archivo_fabricacion':(libro(),'general.xlsx')}
    r=cliente.post('/admin/productos',data=datos)
    assert r.status_code==200,r.text
    assert '1 para crear' in r.text and 'Confirmar fabricación' in r.text
    assert Producto.query.count()==0
    import re
    token=re.search(r'name="fabricacion_token" value="([^"]+)"',r.text).group(1)
    assert cliente.get('/admin/productos').status_code==200 and Producto.query.count()==0
    assert cliente.post('/admin/productos',data={'accion':'confirmar_fabricacion','fabricacion_token':token}).status_code==400
    r=cliente.post('/admin/productos',data={'accion':'confirmar_fabricacion','fabricacion_token':token,'_csrf_token':'csrf-test'})
    assert r.status_code==302 and Producto.query.count()==1


def test_utilidad_vacia_pendiente_y_cero_explicito(despiece):
    datos=lote(('SIN-UTILIDAD','CERO'))
    datos['tablas']['Resumen Producto'][0]['valores'][6]=None
    datos['tablas']['Resumen Producto'][1]['valores'][6]=0
    v=preview(despiece,datos)
    assert not any(f['errores'] for f in v['filas'])
    assert v['filas'][0]['adicionales']['utilidad_pct']=='' and v['filas'][0]['avisos']
    assert v['filas'][1]['adicionales']['utilidad_pct']=='0.000000'
    aplicar(despiece,v)
    assert {r.utilidad_pct for r in ProductoDatosGenerales.query.all()}=={None,Decimal(0)}


def test_sku_otro_tenant_no_conserva_y_recurso_ajeno_no_se_resuelve(despiece):
    f,_=despiece;crear(f[2],sku='NUEVO')
    v=preview(despiece)
    assert v['filas'][0]['accion']=='crear'
    aplicar(despiece,v)
    assert Producto.query.count()==2
    datos=lote(('OTRO',));datos['tablas']['Componentes'][0]['valores'][1]='AJENO'
    assert preview(despiece,datos)['filas'][0]['accion']=='rechazado'


def test_codigo_proveedor_y_ambiguedad_no_elige_arbitrario(despiece):
    import json
    from services.productos_datos_generales import guardar_datos_generales,leer_formulario_completo
    from test_producto_datos_generales import formulario
    f,fuentes=despiece
    from models.compras import ProveedorCompra
    proveedor=ProveedorCompra.query.filter_by(organizacion_id=f[1].id).first()
    p=crear(f[1],sku='BASE-INSUMO',insumo_id=fuentes[0].id,habilita_insumo=True,unidad_medida='metro')
    form=formulario(proveedores_json=json.dumps([{'proveedor_id':proveedor.id,'codigo':'EXTERNO-123'}]))
    guardar_datos_generales(p,leer_formulario_completo(form,[]),db.session);db.session.commit()
    datos=lote();datos['tablas']['Componentes'][0]['valores'][1]='externo-123'
    assert preview(despiece,datos)['filas'][0]['accion']=='crear'
    # Un código interno y un alias de otro material coinciden: requiere revisión.
    fuentes[1].codigo='EXTERNO-123';db.session.commit()
    assert preview(despiece,datos)['filas'][0]['accion']=='rechazado'


def test_rendimiento_carton_no_divide_nuevamente_por_bulto(despiece):
    d=lote();r=d['tablas']['Componentes'][0]['valores'];r[5]=None;r[7]='unidad';r[11]=10
    v=preview(despiece,d);f=v['filas'][0]
    assert not f['errores'],f
    assert f['produccion']['piezas'][0]['modo']=='rendimiento'
    assert f['costo_centavos']==2050 # 2/10 unidades de insumo + 1 min MO
