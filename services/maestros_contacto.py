"""Extensión aditiva del maestro. Ausencia de preparación no rompe el CRM."""
from sqlalchemy import inspect
from models.maestros_contacto import ClienteDomicilioFiscal, ProveedorContacto


def preparado(db_session):
    inspector = inspect(db_session.connection())
    return inspector.has_table('cliente_domicilio_fiscal') and {'cliente_id', 'organizacion_id', 'domicilio', 'codigo_postal'} <= {c['name'] for c in inspector.get_columns('cliente_domicilio_fiscal')}


def guardar(db_session, cliente, domicilio='', codigo_postal=''):
    domicilio, codigo_postal = str(domicilio or '').strip(), str(codigo_postal or '').strip()
    if not domicilio and not codigo_postal:
        return
    if len(domicilio) > 250 or len(codigo_postal) > 20:
        raise ValueError('El domicilio o código postal supera el largo permitido.')
    if not preparado(db_session):
        raise ValueError('Falta preparar los domicilios de clientes en staging. No se guardó el cliente.')
    db_session.flush()
    fila = ClienteDomicilioFiscal.query.filter_by(cliente_id=cliente.id, organizacion_id=cliente.organizacion_id).first()
    if fila is None:
        fila = ClienteDomicilioFiscal(cliente_id=cliente.id, organizacion_id=cliente.organizacion_id)
        db_session.add(fila)
    fila.domicilio, fila.codigo_postal = domicilio, codigo_postal


def consultar(db_session, organizacion_id):
    if not preparado(db_session):
        return {}
    return {fila.cliente_id: {'domicilio': fila.domicilio, 'codigo_postal': fila.codigo_postal}
        for fila in ClienteDomicilioFiscal.query.filter_by(organizacion_id=organizacion_id).all()}


def contactos_preparados(db_session):
    i = inspect(db_session.connection())
    return i.has_table('proveedor_contacto') and {'proveedor_id', 'organizacion_id', 'telefono_contacto'} <= {c['name'] for c in i.get_columns('proveedor_contacto')}


def guardar_contacto(db_session, proveedor, telefono):
    telefono = str(telefono or '').strip()
    if len(telefono) > 80:
        raise ValueError('El teléfono de contacto supera 80 caracteres.')
    if not contactos_preparados(db_session):
        if telefono:
            raise ValueError('Falta preparar los contactos de proveedores. No se guardaron los cambios.')
        return
    db_session.flush()
    fila = ProveedorContacto.query.filter_by(proveedor_id=proveedor.id, organizacion_id=proveedor.organizacion_id).first()
    if fila is None:
        if not telefono:
            return
        fila = ProveedorContacto(proveedor_id=proveedor.id, organizacion_id=proveedor.organizacion_id)
        db_session.add(fila)
    fila.telefono_contacto = telefono


def consultar_contactos(db_session, organizacion_id):
    if not contactos_preparados(db_session):
        return {}
    return {fila.proveedor_id: fila.telefono_contacto for fila in ProveedorContacto.query.filter_by(organizacion_id=organizacion_id).all()}
