"""Asignaciones reales en SQLite: aislamiento, concurrencia e historial fiscal."""
import pytest
from werkzeug.datastructures import MultiDict
from extensions import db
from test_producto_ficha_maestra import entorno
from models.sucursal_operativa import SucursalOperativa
from models.entidad_fiscal import EntidadFiscal
from models.configuracion_fiscal import ConfiguracionFiscal
from models.punto_venta_fiscal import PuntoVentaFiscal
from models.borrador_comprobante_fiscal import BorradorComprobanteFiscal
from models.tipo_comprobante_fiscal import TipoComprobanteFiscal
from models.borrador_item_fiscal import BorradorItemFiscal
from models.evento_fiscal import EventoFiscal
from models.cliente_crm import ClienteCRM
from models.sucursal_fiscal import SucursalFiscal, ContextoFiscalBorrador, TABLAS_SUCURSAL_FISCAL
from services.sucursales_fiscales import guardar, huella, validar_seleccion, guardar_contexto
from scripts.preparar_sucursales_fiscales import preparar, preparado


@pytest.fixture()
def fiscal(entorno):
    app, org, otra, unidad = entorno
    tablas = [SucursalOperativa.__table__, EntidadFiscal.__table__, ConfiguracionFiscal.__table__, PuntoVentaFiscal.__table__, TipoComprobanteFiscal.__table__, ClienteCRM.__table__, BorradorComprobanteFiscal.__table__, BorradorItemFiscal.__table__, EventoFiscal.__table__]
    db.metadata.create_all(db.engine, tables=tablas)
    preparar(db.engine); preparar(db.engine)
    sucursales = [SucursalOperativa(organizacion_id=o.id,codigo=str(i),nombre='Sucursal '+str(i)) for i,o in enumerate([org,org,otra])]
    entidades = [EntidadFiscal(organizacion_id=o.id,codigo=str(i),razon_social='Emisor '+str(i),cuit='CUIT-'+str(i)) for i,o in enumerate([org,org,otra])]
    db.session.add_all(sucursales+entidades);db.session.flush()
    puntos=[]
    for e in entidades:
        conf=ConfiguracionFiscal(organizacion_id=e.organizacion_id,entidad_fiscal_id=e.id)
        db.session.add(conf);db.session.flush()
        p=PuntoVentaFiscal(organizacion_id=e.organizacion_id,entidad_fiscal_id=e.id,configuracion_fiscal_id=conf.id,numero=1,nombre='PV')
        db.session.add(p);puntos.append(p)
    db.session.commit()
    modelos=dict(SucursalOperativa=SucursalOperativa,PuntoVentaFiscal=PuntoVentaFiscal)
    yield app,org,otra,sucursales,entidades,puntos,modelos
    db.session.rollback()
    db.metadata.drop_all(db.engine,tables=list(reversed(TABLAS_SUCURSAL_FISCAL))+list(reversed(tablas)))


def formulario(sucursal,puntos,predeterminado=None,**cambios):
    f=MultiDict(dict(sucursal_id=str(sucursal.id), huella=huella(sucursal,db.session),predeterminado=str((predeterminado or puntos[0]).id) if puntos else ''))
    f.setlist('punto_id',[str(p.id) for p in puntos])
    f.update(cambios)
    return f


def test_varios_cuit_y_misma_entidad_en_dos_sucursales(fiscal):
    _,org,_,ss,es,ps,modelos=fiscal
    guardar(formulario(ss[0],ps[:2]),organizacion_id=org.id,modelos=modelos,session=db.session)
    guardar(formulario(ss[1],[ps[0]]),organizacion_id=org.id,modelos=modelos,session=db.session)
    db.session.commit()
    assert SucursalFiscal.query.count()==3
    assert SucursalFiscal.query.filter_by(sucursal_id=ss[0].id,predeterminado=True).count()==1
    assert all(not e.facturacion_habilitada for e in es)
    assert all(not p.emision_real_habilitada for p in ps)
    assert preparado(db.engine)


def test_rechaza_cruces_y_doble_punto_mismo_cuit(fiscal):
    _,org,_,ss,es,ps,modelos=fiscal
    with pytest.raises(ValueError,match='sucursal'):
        guardar(formulario(ss[2],[ps[0]]),organizacion_id=org.id,modelos=modelos,session=db.session)
    with pytest.raises(ValueError,match='empresa'):
        guardar(formulario(ss[0],[ps[2]]),organizacion_id=org.id,modelos=modelos,session=db.session)
    with pytest.raises(ValueError,match='un solo'):
        guardar(formulario(ss[0],[ps[0],ps[0]]),organizacion_id=org.id,modelos=modelos,session=db.session)
    with pytest.raises(ValueError,match='predeterminado'):
        guardar(formulario(ss[0],[ps[0]],predeterminado=ps[1]),organizacion_id=org.id,modelos=modelos,session=db.session)
    assert SucursalFiscal.query.count()==0


def test_concurrencia_y_emisor_de_sucursal(fiscal):
    _,org,_,ss,es,ps,modelos=fiscal
    f=formulario(ss[0],[ps[0]])
    guardar(f,organizacion_id=org.id,modelos=modelos,session=db.session)
    with pytest.raises(ValueError,match='cambió'):
        guardar(f,organizacion_id=org.id,modelos=modelos,session=db.session)
    with pytest.raises(ValueError,match='asignados'):
        validar_seleccion({'sucursal_id':ss[0].id},organizacion_id=org.id,entidad=es[1],punto=ps[1],modelos=modelos,session=db.session)
    with pytest.raises(ValueError,match='Elegí'):
        validar_seleccion({},organizacion_id=org.id,entidad=es[0],punto=ps[0],modelos=modelos,session=db.session)
    assert validar_seleccion({'sucursal_id':ss[0].id},organizacion_id=org.id,entidad=es[0],punto=ps[0],modelos=modelos,session=db.session)==ss[0]


def test_snapshot_no_cambia_al_reasignar(fiscal):
    _,org,_,ss,es,ps,modelos=fiscal
    guardar(formulario(ss[0],[ps[0]]),organizacion_id=org.id,modelos=modelos,session=db.session)
    tipo=TipoComprobanteFiscal(punto_venta_fiscal_id=ps[0].id,codigo_arca=1,nombre='Factura A',letra='A')
    db.session.add(tipo);db.session.flush()
    b=BorradorComprobanteFiscal(organizacion_id=org.id,entidad_fiscal_id=es[0].id,punto_venta_fiscal_id=ps[0].id,tipo_comprobante_fiscal_id=tipo.id,receptor_nombre='Prueba')
    db.session.add(b);db.session.flush()
    guardar_contexto(b,ss[0],es[0],ps[0],db.session)
    guardar(formulario(ss[0],[ps[1]]),organizacion_id=org.id,modelos=modelos,session=db.session)
    es[0].razon_social='Nombre modificado';ss[0].nombre='Otro local'
    db.session.commit()
    contexto=db.session.get(ContextoFiscalBorrador,b.id)
    assert contexto.razon_social=='Emisor 0' and contexto.sucursal_nombre=='Sucursal 0'
    assert b.entidad_fiscal_id==es[0].id


def test_ruta_fiscal_render_guardar_cancel_y_tenant(fiscal,monkeypatch):
    from types import SimpleNamespace
    import modules.admin.estructura.routes as rutas
    app,org,_,ss,es,ps,modelos=fiscal
    miembro=SimpleNamespace(organizacion_id=org.id,organizacion=org,rol='admin')
    monkeypatch.setattr(rutas,'resolver_tenant_usuario',lambda *a,**k:miembro)
    app.register_blueprint(rutas.crear_blueprint_estructura(dependencias=dict(db=db,modelos=modelos,
        usuario_actual=lambda:SimpleNamespace(id=1), UsuarioOrganizacion=object,
        login_required=lambda f:f,registrar_auditoria=lambda *a,**k:None)))
    app.add_url_rule('/',endpoint='inicio',view_func=lambda:'inicio')
    app.url_build_error_handlers.append(lambda e, endpoint, values: '/sin-uso/'+endpoint)
    app.context_processor(lambda:dict(rol_actual='admin',csrf_token_value='test',csp_nonce='test'))
    app.jinja_env.globals.update(puede_crear_pedido=lambda:False,puede_ver_historico=lambda:False,alertas_operativas=lambda:[])
    c=app.test_client()
    respuesta=c.get('/admin/empresa/datos-fiscales')
    assert respuesta.status_code==200,respuesta.text
    assert 'Emisor 0' in respuesta.text and 'Emisor 2' not in respuesta.text
    assert 'type="button" data-fiscal-cancel' in respuesta.text
    assert SucursalFiscal.query.count()==0
    r=c.post('/admin/empresa/datos-fiscales',data=formulario(ss[0],ps[:2]))
    assert r.status_code==302 and '#sucursal-' in r.location
    assert SucursalFiscal.query.count()==2
    miembro.rol='carga'
    r=c.get('/admin/empresa/datos-fiscales')
    assert r.status_code==302 and SucursalFiscal.query.count()==2


def test_alta_borrador_con_validador_y_snapshot(fiscal):
    from services.facturacion_admin import procesar_accion_facturacion_admin
    _,org,_,ss,es,ps,modelos=fiscal
    guardar(formulario(ss[0],[ps[0]]),organizacion_id=org.id,modelos=modelos,session=db.session)
    tipo=TipoComprobanteFiscal(punto_venta_fiscal_id=ps[0].id,codigo_arca=1,nombre='A',letra='A')
    db.session.add(tipo);db.session.commit()
    modelos.update(ConfiguracionFiscal=ConfiguracionFiscal,TipoComprobanteFiscal=TipoComprobanteFiscal,
        BorradorComprobanteFiscal=BorradorComprobanteFiscal,BorradorItemFiscal=BorradorItemFiscal,
        EventoFiscal=EventoFiscal,EntidadFiscal=EntidadFiscal,ClienteCRM=ClienteCRM)
    form=dict(sucursal_id=str(ss[0].id),entidad_fiscal_id=str(es[0].id),punto_venta_fiscal_id=str(ps[0].id),
        tipo_comprobante_fiscal_id=str(tipo.id),receptor_nombre='Prueba')
    procesar_accion_facturacion_admin('crear_borrador',form,organizacion=org,modelos=modelos,db_session=db.session)
    b=BorradorComprobanteFiscal.query.one()
    assert db.session.get(ContextoFiscalBorrador,b.id).cuit==es[0].cuit
    assert EventoFiscal.query.filter_by(borrador_comprobante_fiscal_id=b.id).count()==1
    with pytest.raises(ValueError,match='asignados'):
        procesar_accion_facturacion_admin('crear_borrador',form|dict(sucursal_id=str(ss[1].id)),organizacion=org,modelos=modelos,db_session=db.session)
    assert BorradorComprobanteFiscal.query.count()==1
