from io import BytesIO
from types import SimpleNamespace
from decimal import Decimal
import csv
import pytest
from openpyxl import load_workbook
from werkzeug.datastructures import FileStorage
from sqlalchemy import event
from extensions import db
from models.producto import Producto
from models.producto_ficha_maestra import ProductoFichaMaestra
from models.producto_datos_generales import ProductoDatosGenerales,ProductoProveedor
from models.fuentes_costo_productivo import InsumoPrecioVersion
from services import actualizacion_selectiva_productos as s
from test_producto_ficha_maestra import entorno,crear,configurar_rutas
from test_producto_datos_generales import completo,guardar as guardar_general,formulario
from test_producto_fabricacion_maestro import fabricacion
from test_producto_despiece import despiece


def archivo(filas,campos):
    from io import StringIO
    o=StringIO();w=csv.writer(o,delimiter=';')
    w.writerow([s.etiqueta(c) for c in campos])
    w.writerows(filas)
    return FileStorage(BytesIO(o.getvalue().encode('utf-8-sig')),filename='lista.csv')


def revisar(c,filas,campos,proveedor=None,columnas=None):
    datos,seleccion=s.leer(archivo(filas,columnas or ('sku',)+tuple(campos)),campos)
    return s.previsualizar(datos,seleccion,proveedor_id=proveedor,Producto=Producto,session=db.session,organizacion_id=c[1].id)


def aplicar(c,v):
    return s.aplicar(s.firmar(v,c[1].id,1,'clave'),Producto=Producto,session=db.session,organizacion_id=c[1].id,usuario=SimpleNamespace(id=1),secreto='clave')


def test_plantilla_vacia_columnas_y_ningun_producto():
    w=load_workbook(s.plantilla())
    assert w['Productos'].cell(1,1).value=='SKU'
    assert set(s.etiqueta(c) for c in s.CAMPOS)<=set(next(w['Productos'].values))
    assert not any(c.value is not None for row in w['Productos'].iter_rows(min_row=2) for c in row)
    assert w['Productos']['A2'].number_format=='@'


def test_solo_seleccion_vacios_cero_no_y_sin_escritura_previa(completo):
    p=crear(completo[1]);guardar_general(p,formulario(marca='Original',utilidad_pct='45'))
    v=revisar(completo,[[p.sku,'Corregida','',0,'No','Nombre que debe ignorarse']],['marca','utilidad_pct','iibb_pct','habilita_venta'],columnas=('sku','marca','utilidad_pct','iibb_pct','habilita_venta','nombre'))
    assert not v['filas'][0]['errores'],v
    assert ProductoDatosGenerales.query.one().marca=='Original'
    assert aplicar(completo,v)==1
    f=ProductoFichaMaestra.query.one();g=ProductoDatosGenerales.query.one()
    assert g.marca=='Corregida' and g.utilidad_pct==45 and g.iibb_pct==0
    assert not f.habilita_venta and f.nombre=='Artículo'
    v=revisar(completo,[[p.sku,'']],['marca']);assert v['filas'][0]['accion']=='sin_cambios'


def test_peso_en_legacy_sin_crear_ficha(completo):
    p=Producto(organizacion_id=completo[1].id,sku='ANTERIOR',descripcion='Nombre',peso_gr=600)
    db.session.add(p);db.session.commit()
    v=revisar(completo,[['ANTERIOR','750']],['peso_gr'])
    assert not v['filas'][0]['errores'],v
    aplicar(completo,v)
    assert p.peso_gr==750 and not ProductoFichaMaestra.query.count()


def test_proveedor_codigo_repetido_en_otro_proveedor_y_sku_discordante(completo):
    a=crear(completo[1],sku='A');b=crear(completo[1],sku='B')
    p,q=completo[4:6]
    for prod,prov in [(a,p),(b,q)]:
        guardar_general(prod,formulario(proveedores_json='[{"proveedor_id":'+str(prov.id)+',"codigo":"0007"}]'))
    v=revisar(completo,[['0007','Marca proveedor A']],['marca'],proveedor=p.id,columnas=('codigo_proveedor','marca'))
    assert v['filas'][0]['sku']=='A' and not v['filas'][0]['errores']
    aplicar(completo,v)
    assert ProductoDatosGenerales.query.filter_by(producto_id=a.id).one().marca=='Marca proveedor A'
    assert ProductoDatosGenerales.query.filter_by(producto_id=b.id).one().marca=='Fierro'
    v=revisar(completo,[['B','0007','X']],['marca'],proveedor=p.id,columnas=('sku','codigo_proveedor','marca'))
    assert v['filas'][0]['errores']


def test_identidad_permisos_duplicados_y_atomico(completo):
    p=crear(completo[1]);guardar_general(p)
    for filas in [[[p.sku,'X'],[p.sku,'Y']],[[p.sku,'X'],['AJENO','Y']]]:
        v=revisar(completo,filas,['marca']);assert any(f['errores'] for f in v['filas'])
        with pytest.raises(ValueError):aplicar(completo,v)
        assert ProductoDatosGenerales.query.one().marca=='Fierro'
    v=revisar(completo,[[p.sku,'combo']],['tipo']);assert v['filas'][0]['errores']


def test_formula_seleccionada_rechaza_y_otra_columna_ignora(completo):
    p=crear(completo[1])
    with pytest.raises(ValueError,match='fórmulas'):revisar(completo,[[p.sku,'=1+1']],['marca'])
    v=revisar(completo,[[p.sku,'Fierro','=1+1']],['marca'],columnas=('sku','marca','descripcion'))
    assert not v['filas'][0]['errores']


def test_lista_barras_y_ubicaciones_conserva_imagenes_y_proveedores(completo):
    p=crear(completo[1]);guardar_general(p)
    v=revisar(completo,[[p.sku,'000123|000456',completo[7].codigo,'Sí']],['codigos_barras','depositos','depositos_definidos'])
    assert not v['filas'][0]['errores'],v
    aplicar(completo,v)
    from models.producto_datos_generales import ProductoCodigoBarras,ProductoUbicacion
    assert {r.codigo for r in ProductoCodigoBarras.query.all()}=={'000123','000456'}
    assert ProductoUbicacion.query.one().sucursal_operativa_id==completo[7].id


def test_simple_precio_unitario_con_proveedor(completo):
    p=crear(completo[1]);prov=completo[4]
    guardar_general(p,formulario(proveedores_json='[{"proveedor_id":'+str(prov.id)+',"codigo":"0007"}]'))
    campos=['precio_proveedor','base_precio','cantidad_bulto','moneda_proveedor']
    v=revisar(completo,[[p.sku,'200','unitario','','ARS']],campos,prov.id)
    assert not v['filas'][0]['errores'],v
    aplicar(completo,v)
    from services.productos_datos_generales import cargar_datos_productos
    a=cargar_datos_productos([p],db.session,completo[1].id)[p.id]
    assert a['precio_costo']=='200.00'
    assert ProductoDatosGenerales.query.one().iva_pct is None


def test_fuente_precio_bulto_historial_y_no_duplica(fabricacion):
    from scripts.preparar_bultos_insumos import preparar
    preparar(db.engine)
    c=fabricacion;insumo=c[4];p=crear(c[1],insumo_id=insumo.id,unidad_medida=insumo.unidad_medida)
    prov=c[4] # Proveedor from base fixture accessed by query below.
    from models.compras import ProveedorCompra
    prov=ProveedorCompra.query.filter_by(organizacion_id=c[1].id,codigo='PROV-1').one()
    guardar_general(p,formulario(proveedores_json='[{"proveedor_id":'+str(prov.id)+',"codigo":"0007"}]'))
    campos=['precio_proveedor','base_precio','cantidad_bulto']
    v=revisar(c,[[p.sku,'1200','bulto','6']],campos,prov.id)
    assert not v['filas'][0]['errores'],v
    aplicar(c,v)
    assert InsumoPrecioVersion.query.filter_by(insumo_id=insumo.id).count()==2
    assert InsumoPrecioVersion.query.filter_by(insumo_id=insumo.id,vigente=True).one().precio_unitario_centavos==20000
    v=revisar(c,[[p.sku,'1200','bulto','6']],campos,prov.id)
    assert not v['filas'][0]['errores'],v
    assert v['filas'][0]['accion']=='sin_cambios',v['filas']
    aplicar(c,v)
    assert InsumoPrecioVersion.query.filter_by(insumo_id=insumo.id).count()==2


def test_ficha_cambiada_y_rollback_final(completo):
    p=crear(completo[1]);guardar_general(p)
    v=revisar(completo,[[p.sku,'Corregida']],['marca'])
    p.peso_gr=800;db.session.commit()
    with pytest.raises(ValueError,match='Cambió'):aplicar(completo,v)
    assert ProductoDatosGenerales.query.one().marca=='Fierro'
    v=revisar(completo,[[p.sku,'Corregida']],['marca'])
    def falla(*args):raise ValueError('Fallo final')
    event.listen(db.session(),'before_commit',falla)
    try:
        with pytest.raises(ValueError,match='Fallo final'):aplicar(completo,v)
    finally:event.remove(db.session(),'before_commit',falla)
    assert ProductoDatosGenerales.query.one().marca=='Fierro'


def test_ruta_plantilla_y_previsualizacion(completo):
    crear(completo[1]);configurar_rutas(completo[0],completo[1]);c=completo[0].test_client()
    r=c.get('/admin/productos/plantilla-vacia.xlsx');assert r.status_code==200
    w=load_workbook(BytesIO(r.data));w['Productos'].cell(2,1,'UAT-1')
    cols=list(next(w['Productos'].values));w['Productos'].cell(2,cols.index('Peso (g)')+1,800)
    b=BytesIO();w.save(b);b.seek(0)
    r=c.post('/admin/productos',data={'accion':'previsualizar_selectiva','_csrf_token':'csrf-test','campos_actualizar':['peso_gr'],'archivo_selectivo':(b,'lista.xlsx')})
    assert r.status_code==200 and '1 para actualizar' in r.text
    assert 'Confirmar campos seleccionados' in r.text
    assert Producto.query.one().peso_gr==3200


def test_seleccion_invalida_encabezado_y_sin_filas():
    with pytest.raises(ValueError):s.leer(archivo([['A',1]],('sku','peso_gr')),[])
    with pytest.raises(ValueError):s.leer(archivo([['A',1]],('sku','peso_gr')),['inventado'])
    with pytest.raises(ValueError,match='Faltan'):s.leer(archivo([['A',1]],('sku','peso_gr')),['marca'])


def test_precio_cambiado_despues_del_preview_y_bulto_sin_fuente(fabricacion):
    c=fabricacion;insumo=c[4];p=crear(c[1],insumo_id=insumo.id,unidad_medida=insumo.unidad_medida)
    from models.compras import ProveedorCompra
    prov=ProveedorCompra.query.filter_by(organizacion_id=c[1].id,codigo='PROV-1').one()
    guardar_general(p,formulario(proveedores_json='[{"proveedor_id":'+str(prov.id)+',"codigo":"0007"}]'))
    campos=['precio_proveedor','base_precio']
    v=revisar(c,[[p.sku,'200','unitario']],campos,prov.id)
    assert not v['filas'][0]['errores'],v
    InsumoPrecioVersion.query.filter_by(insumo_id=insumo.id,vigente=True).one().precio_unitario_centavos=17500
    db.session.commit()
    with pytest.raises(ValueError,match='precio o bulto'):aplicar(c,v)
    assert InsumoPrecioVersion.query.filter_by(insumo_id=insumo.id).count()==1
    simple=crear(c[1],sku='SIN-FUENTE')
    guardar_general(simple,formulario(proveedores_json='[{"proveedor_id":'+str(prov.id)+',"codigo":"0008"}]'))
    v=revisar(c,[[simple.sku,'1200','bulto','6']],['precio_proveedor','base_precio','cantidad_bulto'],prov.id)
    assert 'vinculá la fuente' in v['filas'][0]['errores'][0]


def test_costo_manual_produccion_rechazado_y_composicion_se_conserva(despiece):
    from test_importacion_fabricacion_productos import preview,aplicar as importar
    importar(despiece,preview(despiece))
    c=despiece[0];p=Producto.query.one()
    from models.costo_producto_version import CostoProductoVersion
    antes=CostoProductoVersion.query.count()
    v=revisar(c,[[p.sku,'999']],['precio_costo'])
    assert v['filas'][0]['errores']
    with pytest.raises(ValueError):aplicar(c,v)
    assert CostoProductoVersion.query.count()==antes
    v=revisar(c,[[p.sku,'Nueva marca']],['marca'])
    assert not v['filas'][0]['errores'],v
    aplicar(c,v)
    assert CostoProductoVersion.query.count()==antes
    from services.productos_ficha_maestra import construir_filas
    _,f=construir_filas([p],db.session,c[1].id)
    assert f[0]['producciones'][0]['despiece']['actual']


def test_firma_ajena_y_xlsx_no_ejecuta_formulas(completo):
    p=crear(completo[1])
    v=revisar(completo,[[p.sku,'X']],['marca'])
    for org,user,token in [(completo[2].id,1,s.firmar(v,completo[1].id,1,'clave')),(completo[1].id,2,s.firmar(v,completo[1].id,1,'clave')),(completo[1].id,1,'alterado')]:
        with pytest.raises(ValueError):s.aplicar(token,Producto=Producto,session=db.session,organizacion_id=org,usuario=SimpleNamespace(id=user),secreto='clave')
    w=load_workbook(s.plantilla());h=w['Productos'];cols=list(next(h.values))
    h.cell(2,1,p.sku);h.cell(2,cols.index('Marca')+1,'Fierro');h.cell(2,cols.index('Descripción')+1,'=1+1')
    b=BytesIO();w.save(b);b.seek(0)
    entrada,campos=s.leer(FileStorage(b,filename='a.xlsx'),['marca'])
    assert entrada[0]['valores']=={'sku':p.sku,'marca':'Fierro'}


def test_dos_precios_seleccionados_discordantes_no_pisan_sin_aviso(completo):
    p=crear(completo[1]);prov=completo[4]
    guardar_general(p,formulario(proveedores_json='[{"proveedor_id":'+str(prov.id)+',"codigo":"0007"}]'))
    v=revisar(completo,[[p.sku,'200','unitario','999']],['precio_proveedor','base_precio','precio_costo'],prov.id)
    assert 'no coinciden' in v['filas'][0]['errores'][0]
    with pytest.raises(ValueError):aplicar(completo,v)


def test_peso_legacy_no_exige_completar_campos_ajenos(completo):
    p=Producto(organizacion_id=completo[1].id,sku='ANTERIOR',descripcion='Anterior')
    db.session.add(p);db.session.commit()
    p.permite_correo=None;p.permite_via_cargo=None;p.requiere_revision_logistica=None;db.session.commit()
    v=revisar(completo,[['ANTERIOR','800']],['peso_gr'])
    assert not v['filas'][0]['errores'],v
    aplicar(completo,v)
    assert p.peso_gr==800 and p.permite_correo is None and p.permite_via_cargo is None
