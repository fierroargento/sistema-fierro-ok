import csv
from io import BytesIO, StringIO
import pytest
from sqlalchemy import event
from werkzeug.datastructures import FileStorage
from extensions import db
from models.producto import Producto
from models.producto_ficha_maestra import ProductoFichaMaestra
from services import importacion_logistica_tn as s
from test_producto_ficha_maestra import entorno, crear, configurar_rutas
from test_producto_datos_generales import completo


def csv_tn(filas, encoding='utf-8-sig'):
    out=StringIO(newline='')
    w=csv.writer(out,delimiter=';')
    w.writerow(['SKU','Peso (kg)','Alto (cm)','Ancho (cm)','Profundidad (cm)','Nombre','Stock','Precio','Descripción'])
    for r in filas:w.writerow(list(r)+['Nombre ignorado',999,'12345','=contenido ignorado'])
    return FileStorage(BytesIO(out.getvalue().encode(encoding)),filename='tn.csv')


def revisar(c,filas):
    return s.previsualizar(s.leer(csv_tn(filas)),Producto=Producto,session=db.session,organizacion_id=c[1].id)


def guardar(c,v):
    return s.aplicar(s.firmar(v,c[1].id,1,'clave'),Producto=Producto,session=db.session,organizacion_id=c[1].id,usuario_id=1,secreto='clave')


def test_solo_cuatro_columnas_sin_alta_de_ficha_anterior(completo):
    p=Producto(organizacion_id=completo[1].id,sku='ANTERIOR',descripcion='Nombre conservado',peso_gr=700,alto_cm=1,ancho_cm=2,largo_cm=3,permite_correo=False,permite_via_cargo=True,observacion_logistica='Conservar')
    db.session.add(p);db.session.commit()
    antes={c.name:getattr(p,c.name) for c in Producto.__table__.columns}
    v=revisar(completo,[['anterior','0.30','2','62','28']])
    assert v[0]['accion']=='actualizar' and v[0]['datos']['peso_gr']==300
    assert p.peso_gr==700 # preview no escribe
    assert guardar(completo,v)==1
    db.session.expire_all()
    despues={c.name:getattr(p,c.name) for c in Producto.__table__.columns}
    assert {c for c in antes if antes[c]!=despues[c]}==set(s.COLUMNAS)
    assert ProductoFichaMaestra.query.count()==0 and Producto.query.count()==1


def test_ceros_vacios_conservan_y_kg_decimal(completo):
    p=crear(completo[1])
    v=revisar(completo,[[p.sku,'0','','0','36.5']])
    assert v[0]['datos']=={'largo_cm':36.5}
    assert len(v[0]['avisos'])==3
    guardar(completo,v)
    assert p.peso_gr==3200 and p.alto_cm==5 and p.ancho_cm==42 and p.largo_cm==36.5
    assert revisar(completo,[[p.sku,'0','','0','36.5']])[0]['accion']=='sin_cambios'
    assert revisar(completo,[[p.sku,'0','','0','0']])[0]['accion']=='omitido'


def test_duplicados_identicos_y_conflictos(completo):
    p=crear(completo[1]);fila=[p.sku,'0.2','2','30','30']
    v=revisar(completo,[fila,fila]);assert len(v)==1 and v[0]['accion']=='actualizar'
    assert 'una sola vez' in v[0]['avisos'][0]
    v=revisar(completo,[fila,[p.sku,'0.4','2','30','30']])
    assert v[0]['accion']=='omitido' and 'diferentes' in v[0]['motivo']
    with pytest.raises(ValueError,match='No hay'):guardar(completo,v)
    assert p.peso_gr==3200


@pytest.mark.parametrize('valor',['-1','NaN','Infinity','=1+2','texto','100000000000'])
def test_medidas_invalidas_no_se_escriben(completo,valor):
    p=crear(completo[1])
    v=revisar(completo,[[p.sku,valor,'2','3','4']])
    assert v[0]['accion']=='omitido' and 'Peso (kg)' in v[0]['motivo']
    with pytest.raises(ValueError):guardar(completo,v)


def test_no_coincidentes_no_stockeables_y_otra_org(completo):
    p=crear(completo[1]);ajeno=crear(completo[2],sku='AJENO')
    servicio=crear(completo[1],sku='SERV',no_stockeable=True,permite_correo=False,permite_via_cargo=False)
    v=revisar(completo,[[p.sku,'1','2','3','4'],['AJENO','1','2','3','4'],['NUEVO','1','2','3','4'],['SERV','1','2','3','4']])
    assert [f['accion'] for f in v]==['actualizar','omitido','omitido','omitido']
    assert guardar(completo,v)==1
    assert ajeno.peso_gr==3200 and servicio.peso_gr==3200 and Producto.query.count()==3


def test_concurrencia_antes_de_escribir_cualquier_fila(completo):
    p=crear(completo[1],sku='A');q=crear(completo[1],sku='B')
    v=revisar(completo,[['A','1','2','3','4'],['B','1','2','3','4']])
    q.peso_gr=800;db.session.commit()
    with pytest.raises(ValueError,match='cambiaron'):guardar(completo,v)
    assert p.peso_gr==3200 and q.peso_gr==800


def test_firma_usuario_org_y_rollback(completo):
    p=crear(completo[1]);v=revisar(completo,[[p.sku,'1','2','3','4']])
    for org,user,token in [(completo[2].id,1,s.firmar(v,completo[1].id,1,'clave')),(completo[1].id,2,s.firmar(v,completo[1].id,1,'clave')),(completo[1].id,1,'alterado')]:
        with pytest.raises(ValueError):s.aplicar(token,Producto=Producto,session=db.session,organizacion_id=org,usuario_id=user,secreto='clave')
    def falla(*args):raise ValueError('Fallo final')
    event.listen(db.session(),'before_commit',falla)
    try:
        with pytest.raises(ValueError,match='Fallo final'):guardar(completo,v)
    finally:event.remove(db.session(),'before_commit',falla)
    assert p.peso_gr==3200


def test_utf8_cp1252_y_limites():
    for enc in ['utf-8-sig','cp1252']:
        assert s.leer(csv_tn([['Ñ-1','0,2','2','3','4']],enc))[0]['sku']=='Ñ-1'
    with pytest.raises(ValueError,match='500'):s.leer(csv_tn([['P','1','2','3','4']]*501))
    with pytest.raises(ValueError,match='columna'):s.leer(FileStorage(BytesIO(b'SKU;Peso\nP;1'),filename='tn.csv'))


def test_ruta_preview_y_confirmacion_conserva_estado(completo):
    crear(completo[1]);configurar_rutas(completo[0],completo[1]);c=completo[0].test_client()
    a=csv_tn([['UAT-1','1','2','3','4']])
    r=c.post('/admin/productos',data={'accion':'previsualizar_logistica_tn','_csrf_token':'csrf-test','archivo_logistica_tn':(a.stream,'tn.csv')})
    assert r.status_code==200 and '1 para actualizar' in r.text
    assert 'Confirmar peso y dimensiones' in r.text and Producto.query.one().peso_gr==3200
    from html import unescape
    import re
    token=unescape(re.search(r'name="logistica_token" value="([^"]+)"',r.text)[1])
    r=c.post('/admin/productos',data={'accion':'confirmar_logistica_tn','_csrf_token':'csrf-test','logistica_token':token})
    assert r.status_code==302 and Producto.query.one().peso_gr==1000
    assert c.post('/admin/productos',data={'accion':'confirmar_logistica_tn','logistica_token':token}).status_code==400
