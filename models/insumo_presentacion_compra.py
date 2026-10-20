"""Presentación y cotización de compra vinculadas al insumo y precio existentes."""
from extensions import db


class InsumoPresentacionCompra(db.Model):
    __tablename__ = 'insumo_presentacion_compra'
    insumo_id = db.Column(db.Integer, db.ForeignKey('insumo_productivo.id'), primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey('organizacion.id'), nullable=False, index=True)
    cantidad_bulto = db.Column(db.Numeric(18, 6))
    medidas_origen = db.Column(db.String(120))
    __table_args__ = (db.CheckConstraint('cantidad_bulto IS NULL OR cantidad_bulto > 0', name='ck_insumo_bulto_positivo'),)


class InsumoPrecioBultoVersion(db.Model):
    """Base de cotización y bulto de la misma versión histórica de precio."""
    __tablename__ = 'insumo_precio_bulto_version'
    precio_version_id = db.Column(db.Integer, db.ForeignKey('insumo_precio_version.id'), primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey('organizacion.id'), nullable=False, index=True)
    cantidad_bulto = db.Column(db.Numeric(18, 6), nullable=False)
    precio_bulto_centavos = db.Column(db.BigInteger, nullable=False)
    base_precio = db.Column(db.String(12), nullable=False)
    __table_args__ = (
        db.CheckConstraint('cantidad_bulto > 0', name='ck_precio_bulto_cantidad'),
        db.CheckConstraint('precio_bulto_centavos >= 0', name='ck_precio_bulto_importe'),
        db.CheckConstraint("base_precio IN ('unitario','bulto')", name='ck_precio_bulto_base'),
    )
