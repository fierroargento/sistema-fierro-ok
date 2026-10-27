"""Una identidad de proveedor con disponibilidad explícita por unidad."""
from extensions import db


class ProveedorUnidad(db.Model):
    __tablename__ = 'proveedor_unidad'
    __table_args__ = (db.UniqueConstraint('proveedor_id', 'unidad_negocio_id', name='uq_proveedor_unidad'),)
    estado = db.Column(db.String(20), nullable=False, default='activo')
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey('organizacion.id'), nullable=False, index=True)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedor_compra.id'), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey('unidad_negocio.id'), nullable=False, index=True)
