"""Codimat: descuento sucesivo, neto IVA, reglas y revisión con aislamiento."""
from io import BytesIO
from decimal import Decimal
import pytest
from openpyxl import Workbook
from werkzeug.datastructures import FileStorage,MultiDict
from extensions import db
from services import listas_codimat as s
from models.listas_proveedores_compra import ConfiguracionListaProveedor as Config,CalculoCotizacionProveedor as Calculo,CotizacionProveedorCompra as C
from models.fuentes_costo_productivo import InsumoPrecioVersion as V
from test_listas_proveedores_compra import listas,personal,entorno,vinculo,aplicar,form


def archivo(codigo='1955',precio=26420.0244,iva=1.21,bonif=0,extra=None):
    w=Workbook();h=w.active;h.title='Lista de Precios'
    h.append(['CODIMAT SOCIEDAD ANÓNIMA']);h.append(s.ENCABEZADOS)
    h.append(['UNI','5.5',codigo,'BARRA ANGULO',iva,24570.622692,precio,bonif,'=(100-H3)/100*G3','=I3/1.21'])
    if extra:h.append(extra)
    b=BytesIO();w.save(b);b.seek(0)
    return FileStorage(stream=b,filename='Codimat.xlsx')


def reglas(cantidad='6',descuento='40'):
    return s.reglas(['1955'],[descuento],[cantidad])


def revisar(d,entrada=None,regla=None):
    _,org,_,a,_,ps,*_=d
    return s.revisar(entrada or archivo(),regla if regla is not None else reglas(),ps[0],org.id,a.id,db.session)


def test_descuento_adicional_sin_iva_y_snapshot(listas):
    vinculo(listas,codigo='1955');v=revisar(listas)
    assert Config.query.count()==C.query.count()==Calculo.query.count()==V.query.count()==0
    f=v['filas'][0];assert not f['errores']
    assert f['plan']['precio_bulto_centavos']==1310084
    assert f['plan']['precio_unitario_centavos']==218347
    assert f['valores']['_codimat']['bulto_con_iva']=='15852.01'
    assert aplicar(listas,v)[0]==1
    assert Config.query.one().reglas==reglas()
    assert Calculo.query.one().datos['bonificacion']=='40'
    assert C.query.one().precio_bulto_centavos==1310084 and V.query.count()==0
    assert aplicar(listas,revisar(listas))[0]==0
    assert C.query.count()==1 and Calculo.query.count()==1
    from services import listas_proveedores_compra as comunes
    _,org,_,a,_,ps,*_=listas
    fuente=comunes.usar_en_costo(C.query.one().id,ps[0],org.id,a.id,'',db.session,None)
    db.session.commit()
    assert fuente.precio_unitario_centavos==218347 and V.query.count()==1


def test_reemplaza_bonif_archivo_y_no_ejecuta_formulas(listas):
    vinculo(listas,codigo='1955')
    v=revisar(listas,archivo(bonif=40))
    assert v['filas'][0]['plan']['precio_bulto_centavos']==1310084
    assert v['filas'][0]['valores']['_codimat']['bonificacion_archivo']=='40'
    for kw in [dict(precio='=1+1'),dict(iva='=1.21'),dict(bonif='=0'),dict(precio='NaN'),dict(precio=-1),dict(iva=0),dict(bonif=101)]:
        assert revisar(listas,archivo(**kw))['filas'][0]['errores']


def test_cantidad_no_es_peso_archivo_y_reutiliza_presentacion(listas):
    vinculo(listas,codigo='1955')
    assert 'cantidad' in revisar(listas,regla=reglas(''))['filas'][0]['errores'][0].lower()
    from models.insumo_presentacion_compra import InsumoPresentacionCompra as IP
    _,org,_,_,_,_,items,*_=listas
    db.session.add(IP(insumo_id=items[0].id,organizacion_id=org.id,cantidad_bulto=6,medidas_origen='Barra'));db.session.commit()
    assert Decimal(revisar(listas,regla=reglas(''))['filas'][0]['plan']['cantidad_bulto'])==6


def test_bonificaciones_obligatorias_ignorados_duplicados(listas):
    vinculo(listas,codigo='1955')
    assert revisar(listas,regla=s.reglas(['OTRO'],['0'],['1']))['filas'][0]['errores']
    v=revisar(listas,archivo(extra=['UNI',1,'999','NO COMPRAMOS',1.21,1,'=mal',0,'=mal','=mal']))
    assert len(v['filas'])==1 and v['ignoradas']==1 and not v['filas'][0]['errores']
    v=revisar(listas,archivo(extra=['UNI',1,'1955','DUPLICADO',1.21,1,10,0,'=mal','=mal']))
    assert v['filas'][1]['errores']
    for cod,d,q in [(['1955','1955'],['40','40'],['6','6']),(['1955'],['101'],['6']),(['1955'],['NaN'],['6']),(['1955'],['40'],['0']),(['1955'],[''],['6'])]:
        with pytest.raises(ValueError):s.reglas(cod,d,q)
    assert s.reglas(['1955'],['0%'],['1'])[0]['descuento']=='0'


def test_configuracion_concurrente_y_unidad_independiente(listas):
    vinculo(listas,codigo='1955');v=revisar(listas)
    _,org,_,a,b,ps,*_=listas
    db.session.add(Config(organizacion_id=org.id,unidad_negocio_id=a.id,proveedor_id=ps[0].id,reglas=reglas(descuento='38')));db.session.commit()
    with pytest.raises(ValueError,match='bonificaciones cambiaron'):aplicar(listas,v)
    assert C.query.count()==0
    assert s.reglas_actuales(org.id,b.id,ps[0].id,db.session)!=reglas(descuento='38')


def test_ruta_revision_confirmacion_historial_y_cancelar(listas):
    l=vinculo(listas,codigo='1955');cliente,org,_,a,_,ps,*_=listas
    data=MultiDict(form(listas,'revisar_codimat'))
    for k,v in [('codimat_codigo','1955'),('codimat_descuento','40'),('codimat_cantidad','6')]:data.add(k,v)
    data.add('archivo_lista',archivo())
    r=cliente.post('/admin/compras/listas-proveedores',data=data,content_type='multipart/form-data')
    assert r.status_code==200
    assert b'13.100,84' in r.data and b'bonificaci' in r.data.lower()
    assert C.query.count()==Config.query.count()==0
    import re
    token=re.search(rb'name="token_lista" value="([^"]+)"',r.data).group(1).decode()
    r=cliente.post('/admin/compras/listas-proveedores',data=form(listas,'confirmar_lista',token_lista=token))
    assert r.status_code==302 and C.query.count()==1 and Config.query.count()==1
    r=cliente.get(f'/admin/compras/listas-proveedores?proveedor_id={ps[0].id}&ver={l.id}')
    assert r.status_code==200 and b'BonifC original' in r.data


def test_formato_modificado_y_limite_archivo(listas):
    vinculo(listas,codigo='1955')
    x=FileStorage(stream=BytesIO(b'bad'),filename='Codimat.xlsx')
    with pytest.raises(ValueError,match='leer'):revisar(listas,x)
    x=FileStorage(stream=BytesIO(b'x'*(10*1024*1024+1)),filename='Codimat.xlsx')
    with pytest.raises(ValueError,match='10 MB'):revisar(listas,x)
    with pytest.raises(ValueError,match='XLSX'):revisar(listas,FileStorage(stream=BytesIO(),filename='lista.csv'))


def test_trece_reglas_iniciales_y_cantidades_confirmadas(listas):
    _,org,_,a,_,ps,*_=listas
    rr=s.reglas_actuales(org.id,a.id,ps[0].id,db.session)
    assert len(rr)==13 and {r['codigo']:int(r['cantidad']) for r in rr}=={c:12 if c=='1867' else 2 if c=='2393' else 6 for c in s.DESCUENTOS}
    assert {r['codigo']:int(r['descuento']) for r in rr}==s.DESCUENTOS
    assert Config.query.count()==0


def test_dimension_a1_incorrecta_del_excel_original(listas):
    from zipfile import ZipFile,ZIP_DEFLATED
    import re
    original=archivo();salida=BytesIO()
    with ZipFile(original.stream) as origen,ZipFile(salida,'w',ZIP_DEFLATED) as destino:
        for nombre in origen.namelist():
            contenido=origen.read(nombre)
            if nombre=='xl/worksheets/sheet1.xml':contenido=re.sub(rb'<dimension ref="[^"]+"/>',b'<dimension ref="A1"/>',contenido)
            destino.writestr(nombre,contenido)
    salida.seek(0);vinculo(listas,codigo='1955')
    vista=revisar(listas,FileStorage(stream=salida,filename='Codimat.xlsx'))
    assert vista['filas'][0]['plan']['precio_bulto_centavos']==1310084


def test_pendientes_con_descripcion_vinculacion_atomica_y_reutilizacion(listas):
    from models.listas_proveedores_compra import MaterialProveedorCompra as L
    _,org,_,a,_,ps,items,*_=listas
    vista=revisar(listas)
    assert vista['filas']==[] and len(vista['pendientes'])==1
    assert vista['pendientes'][0]['descripcion']=='BARRA ANGULO'
    assert vista['codimat']['codigos_ausentes']==[] and vista['ignoradas']==0
    with pytest.raises(ValueError,match='pendientes'):aplicar(listas,vista)
    nueva=s.resolver_vinculos(vista,[str(items[0].id)],ps[0],org.id,a.id,db.session)
    assert L.query.count()==C.query.count()==Config.query.count()==0
    assert nueva['filas'][0]['material']==items[0].nombre
    assert nueva['filas'][0]['plan']['precio_bulto_centavos']==1310084
    assert aplicar(listas,nueva)[0]==1
    assert L.query.one().codigo=='1955' and L.query.one().insumo_id==items[0].id
    assert C.query.count()==1 and Calculo.query.count()==1 and V.query.count()==0
    siguiente=revisar(listas)
    assert not siguiente['pendientes'] and len(siguiente['filas'])==1
    assert aplicar(listas,siguiente)[0]==0


def test_pendientes_omitir_y_aislamiento(listas):
    from models.listas_proveedores_compra import MaterialProveedorCompra as L
    _,org,_,a,_,ps,items,*_=listas
    vista=revisar(listas)
    for ident in ['',str(items[2].id),str(items[3].id),str(items[4].id),'99999']:
        with pytest.raises(ValueError):s.resolver_vinculos(vista,[ident],ps[0],org.id,a.id,db.session)
    nueva=s.resolver_vinculos(vista,['omitir'],ps[0],org.id,a.id,db.session)
    assert nueva['filas']==[] and nueva['ignoradas']==1 and nueva['vinculos_propuestos']==[]
    assert L.query.count()==C.query.count()==Config.query.count()==0


def test_pendientes_no_duplicar_material_y_conflicto_concurrente(listas):
    from models.listas_proveedores_compra import MaterialProveedorCompra as L
    _,org,_,a,_,ps,items,*_=listas
    entrada=archivo(extra=['UNI',1,'1957','OTRA BARRA',1.21,1,100,0,'=1','=1'])
    vista=revisar(listas,entrada,reglas()+[dict(codigo='1957',descuento='40',cantidad='6')])
    with pytest.raises(ValueError,match='vínculo'):s.resolver_vinculos(vista,[str(items[0].id)]*2,ps[0],org.id,a.id,db.session)
    nueva=s.resolver_vinculos(vista,[str(items[0].id),str(items[1].id)],ps[0],org.id,a.id,db.session)
    vinculo(listas,codigo='OTRO')
    with pytest.raises(ValueError,match='vínculo'):aplicar(listas,nueva)
    assert L.query.count()==1 and C.query.count()==Config.query.count()==0


def test_borrador_firmado_contexto_y_manipulacion(listas):
    _,org,_,a,b,ps,*_=listas
    vista=revisar(listas)
    token=s.firmar_borrador(vista,ps[0].id,org.id,a.id,1,'secreto')
    assert s.leer_borrador(token,ps[0].id,org.id,a.id,1,'secreto')==vista
    for p,u,usuario in [(ps[1].id,a.id,1),(ps[0].id,b.id,1),(ps[0].id,a.id,2)]:
        with pytest.raises(ValueError):s.leer_borrador(token,p,org.id,u,usuario,'secreto')
    with pytest.raises(ValueError):s.leer_borrador(token+'roto',ps[0].id,org.id,a.id,1,'secreto')


def test_ruta_sin_vinculos_revisa_sin_resubir_y_confirma(listas):
    from models.listas_proveedores_compra import MaterialProveedorCompra as L
    import re
    cliente,org,_,a,_,ps,items,*_=listas
    data=MultiDict(form(listas,'revisar_codimat'))
    for k,v in [('codimat_codigo','1955'),('codimat_descuento','40'),('codimat_cantidad','6')]:data.add(k,v)
    data.add('archivo_lista',archivo())
    r=cliente.post('/admin/compras/listas-proveedores',data=data,content_type='multipart/form-data')
    assert r.status_code==200 and b'Vincular art' in r.data and b'BARRA ANGULO' in r.data
    token=re.search(rb'name="token_vinculacion" value="([^"]+)"',r.data).group(1).decode()
    assert b'name="token_lista"' not in r.data
    r=cliente.post('/admin/compras/listas-proveedores',data=form(listas,'revisar_vinculos_codimat',token_vinculacion=token,material_0=''))
    assert r.status_code==400 and b'name="token_vinculacion"' in r.data
    r=cliente.post('/admin/compras/listas-proveedores',data=form(listas,'revisar_vinculos_codimat',token_vinculacion=token,material_0=str(items[0].id)))
    assert r.status_code==200 and b'13.100,84' in r.data and b'vinculos_propuestos' not in r.data
    assert L.query.count()==C.query.count()==Config.query.count()==0
    final=re.search(rb'name="token_lista" value="([^"]+)"',r.data).group(1).decode()
    r=cliente.post('/admin/compras/listas-proveedores',data=form(listas,'confirmar_lista',token_lista=final))
    assert r.status_code==302 and L.query.count()==C.query.count()==1
