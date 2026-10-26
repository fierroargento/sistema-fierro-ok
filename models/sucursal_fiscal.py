"""CUIT disponibles por sucursal y contexto histórico de borradores nuevos."""
from extensions import db


class SucursalFiscal(db.Model):
    __tablename__ = 'sucursal_fiscal'
    __table_args__ = (db.UniqueConstraint('sucursal_id', 'entidad_fiscal_id'),)
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey('organizacion.id'), nullable=False, index=True)
    sucursal_id = db.Column(db.Integer, db.ForeignKey('sucursal_operativa.id'), nullable=False, index=True)
    entidad_fiscal_id = db.Column(db.Integer, db.ForeignKey('entidad_fiscal.id'), nullable=False)
    punto_venta_fiscal_id = db.Column(db.Integer, db.ForeignKey('punto_venta_fiscal.id'), nullable=False)
    predeterminado = db.Column(db.Boolean, nullable=False, default=False)


class ContextoFiscalBorrador(db.Model):
    __tablename__ = 'contexto_fiscal_borrador'
    borrador_id = db.Column(db.Integer, db.ForeignKey('borrador_comprobante_fiscal.id'), primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey('organizacion.id'), nullable=False, index=True)
    sucursal_id = db.Column(db.Integer, db.ForeignKey('sucursal_operativa.id'), nullable=False)
    sucursal_nombre = db.Column(db.String(150), nullable=False)
    razon_social = db.Column(db.String(200), nullable=False)
    cuit = db.Column(db.String(20))
    condicion_iva = db.Column(db.String(80))
    domicilio_fiscal = db.Column(db.String(300))
    punto_venta_numero = db.Column(db.Integer, nullable=False)


TABLAS_SUCURSAL_FISCAL = [SucursalFiscal.__table__, ContextoFiscalBorrador.__table__]
