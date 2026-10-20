"""Domicilio del maestro CRM, sin tocar pedidos ni direcciones de envío."""
from extensions import db


class ClienteDomicilioFiscal(db.Model):
    __tablename__ = 'cliente_domicilio_fiscal'
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente_crm.id'), primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey('organizacion.id'), nullable=False, index=True)
    domicilio = db.Column(db.String(250), nullable=False, default='')
    codigo_postal = db.Column(db.String(20), nullable=False, default='')


class ProveedorContacto(db.Model):
    __tablename__ = 'proveedor_contacto'
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedor_compra.id'), primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey('organizacion.id'), nullable=False, index=True)
    telefono_contacto = db.Column(db.String(80), nullable=False, default='')
