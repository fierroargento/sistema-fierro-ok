from types import SimpleNamespace
from pathlib import Path
from flask import Flask
import pytest

from extensions import db
from models.organizacion import Organizacion
from models.unidad_negocio import UnidadNegocio
from models.producto import Producto
from models.sucursal_operativa import SucursalOperativa
from models.existencia_sucursal import ExistenciaSucursal
from models.inventario_saas import ItemInventario
from models.fuentes_costo_productivo import InsumoProductivo
from models.compras import ProveedorCompra
from models.cliente_crm import ClienteCRM
from models.entidad_fiscal import EntidadFiscal
from models.configuracion_fiscal import ConfiguracionFiscal
from models.maestros_contacto import ClienteDomicilioFiscal, ProveedorContacto
from services import maestros_contacto as contacto
from services.compras_nucleo import crear_proveedor
from scripts.preparar_maestros_contacto import preparar
from services.consulta_padron_arca import configuracion_tenant, ErrorPadron


@pytest.fixture()
def entorno_contactos():
    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://', SECRET_KEY='prueba', TESTING=True)
    db.init_app(app)
    with app.app_context():
        tablas = [Organizacion.__table__, UnidadNegocio.__table__, ClienteCRM.__table__, ProveedorCompra.__table__, EntidadFiscal.__table__, ConfiguracionFiscal.__table__]
        db.metadata.create_all(db.engine, tables=tablas)
        org = Organizacion(nombre='Uno', slug='uno'); otro = Organizacion(nombre='Dos', slug='dos')
        db.session.add_all([org, otro]); db.session.commit()
        yield app, org, otro
        db.session.remove()
        db.metadata.drop_all(db.engine, tables=[ClienteDomicilioFiscal.__table__, ProveedorContacto.__table__] + list(reversed(tablas)))


def test_antes_de_preparar_no_rompe_listados_ni_pierde_datos(entorno_contactos):
    _, org, _ = entorno_contactos
    assert contacto.consultar(db.session, org.id) == {}
    assert contacto.consultar_contactos(db.session, org.id) == {}
    with pytest.raises(ValueError, match='Falta preparar'):
        crear_proveedor({'codigo':'uno','razon_social':'Uno','telefono_contacto':'291 1234'}, organizacion_id=org.id, ProveedorCompra=ProveedorCompra, db_session=db.session)
    db.session.rollback()
    assert ProveedorCompra.query.count() == 0


def test_crear_editar_borrar_telefono_separado_y_rollback_atomico(entorno_contactos):
    _, org, otro = entorno_contactos
    preparar(db.engine); preparar(db.engine)
    proveedor = crear_proveedor({'codigo':'uno','razon_social':'Uno','telefono':'GENERAL','persona_contacto':'Persona','telefono_contacto':'+54 291 1234'}, organizacion_id=org.id, ProveedorCompra=ProveedorCompra, db_session=db.session)
    assert contacto.consultar_contactos(db.session, org.id)[proveedor.id] == '+54 291 1234'
    assert contacto.consultar_contactos(db.session, otro.id) == {}
    assert proveedor.telefono == 'GENERAL' and proveedor.persona_contacto == 'Persona'
    contacto.guardar_contacto(db.session, proveedor, '291 5678'); db.session.commit()
    assert contacto.consultar_contactos(db.session, org.id)[proveedor.id] == '291 5678'
    contacto.guardar_contacto(db.session, proveedor, ''); db.session.commit()
    assert contacto.consultar_contactos(db.session, org.id)[proveedor.id] == ''
    with pytest.raises(ValueError):
        crear_proveedor({'codigo':'fallo','razon_social':'No guardar','telefono_contacto':'1'*81}, organizacion_id=org.id, ProveedorCompra=ProveedorCompra, db_session=db.session)
    db.session.rollback()
    assert ProveedorCompra.query.count() == 1


def test_domicilio_cliente_pertenece_al_maestro_y_conserva_tenant(entorno_contactos):
    _, org, otro = entorno_contactos
    preparar(db.engine)
    cliente = ClienteCRM(organizacion_id=org.id, codigo='c1', nombre='Cliente', localidad='Viedma', provincia='Río Negro')
    db.session.add(cliente)
    contacto.guardar(db.session, cliente, 'Calle 123', '8500'); db.session.commit()
    assert contacto.consultar(db.session, org.id)[cliente.id] == {'domicilio':'Calle 123','codigo_postal':'8500'}
    assert contacto.consultar(db.session, otro.id) == {}
    assert cliente.activo is False
    contacto.guardar(db.session, cliente, 'No persistir', '1234'); db.session.rollback()
    assert contacto.consultar(db.session, org.id)[cliente.id]['domicilio'] == 'Calle 123'


def test_configuracion_de_otra_organizacion_no_se_utiliza(entorno_contactos, monkeypatch):
    _, org, otro = entorno_contactos
    entidad = EntidadFiscal(organizacion_id=otro.id, codigo='otra', razon_social='Otra', cuit='20224107030')
    db.session.add(entidad); db.session.flush()
    cfg = ConfiguracionFiscal(organizacion_id=otro.id, entidad_fiscal_id=entidad.id, ambiente='homologacion', proveedor='arca', token_env='TICKET_ARCA_UAT')
    db.session.add(cfg); db.session.commit()
    monkeypatch.setenv(f'ARCA_PADRON_ENTIDAD_{org.id}', str(entidad.id))
    with pytest.raises(ErrorPadron): configuracion_tenant(org.id)
    monkeypatch.setenv(f'ARCA_PADRON_ENTIDAD_{otro.id}', str(entidad.id)); monkeypatch.setenv('TICKET_ARCA_UAT', '<ticket-prueba/>')
    endpoint, cuit, ticket = configuracion_tenant(otro.id)
    assert endpoint.startswith('https://awshomo.arca.gov.ar/') and ticket == '<ticket-prueba/>'


def test_alta_cliente_real_guarda_domicilio_sin_activar(entorno_contactos):
    from services.crm_admin import procesar_accion_crm_admin
    _, org, _ = entorno_contactos
    preparar(db.engine)
    modelos = {'ClienteCRM':ClienteCRM, 'UnidadNegocio':UnidadNegocio,
        'ClienteIdentidadCanal':None, 'EtapaCRM':None, 'OportunidadCRM':None, 'ActividadCRM':None}
    procesar_accion_crm_admin('crear_cliente', {'codigo':'c1','nombre':'Cliente', 'documento':'20224107030', 'localidad':'Viedma','domicilio':'Calle 123','codigo_postal':'8500'}, organizacion=org, modelos=modelos, db_session=db.session)
    cliente = ClienteCRM.query.filter_by(organizacion_id=org.id).one()
    assert cliente.activo is False
    assert contacto.consultar(db.session, org.id)[cliente.id]['domicilio'] == 'Calle 123'


def test_edicion_proveedor_y_telefono_comparten_transaccion(entorno_contactos):
    from services.importacion_proveedores_compra import previsualizar_proveedores, aplicar_proveedores
    _, org, _ = entorno_contactos
    preparar(db.engine)
    proveedor = crear_proveedor({'codigo':'uno','razon_social':'Original','telefono_contacto':'111'}, organizacion_id=org.id, ProveedorCompra=ProveedorCompra, db_session=db.session)
    vista = previsualizar_proveedores([{'numero':1,'valores':['UNO','No persistir']}], {'0':'codigo','1':'razon_social'}, proveedores=[proveedor])
    aplicar_proveedores(vista, organizacion_id=org.id, ProveedorCompra=ProveedorCompra, db_session=db.session, commit=False)
    with pytest.raises(ValueError): contacto.guardar_contacto(db.session, proveedor, 'x'*81)
    db.session.rollback()
    assert ProveedorCompra.query.one().razon_social == 'Original'
    assert contacto.consultar_contactos(db.session, org.id)[proveedor.id] == '111'
