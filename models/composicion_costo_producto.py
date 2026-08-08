"""Ficha tecnica vigente para calcular el costo productivo por unidad."""

from sqlalchemy import CheckConstraint, UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class ProductoInsumoCosteo(db.Model):
    __tablename__ = "producto_insumo_costeo"
    __table_args__ = (
        UniqueConstraint("perfil_costeo_id", "insumo_id", name="uq_producto_insumo_costeo"),
        CheckConstraint("cantidad > 0", name="ck_producto_insumo_cantidad"),
        CheckConstraint("porcentaje_merma >= 0 AND porcentaje_merma <= 100", name="ck_producto_insumo_merma"),
    )
    id = db.Column(db.Integer, primary_key=True)
    perfil_costeo_id = db.Column(db.Integer, db.ForeignKey("perfil_costeo_producto.id"), nullable=False, index=True)
    insumo_id = db.Column(db.Integer, db.ForeignKey("insumo_productivo.id"), nullable=False, index=True)
    cantidad = db.Column(db.Numeric(18, 6), nullable=False)
    porcentaje_merma = db.Column(db.Numeric(9, 6), default=0, nullable=False)
    observacion = db.Column(db.String(500))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    perfil = db.relationship("PerfilCosteoProducto", backref="insumos_costeo")
    insumo = db.relationship("InsumoProductivo")


class ProductoOperacionCosteo(db.Model):
    __tablename__ = "producto_operacion_costeo"
    __table_args__ = (
        CheckConstraint("minutos > 0", name="ck_producto_operacion_minutos"),
        CheckConstraint("orden >= 0", name="ck_producto_operacion_orden"),
    )
    id = db.Column(db.Integer, primary_key=True)
    perfil_costeo_id = db.Column(db.Integer, db.ForeignKey("perfil_costeo_producto.id"), nullable=False, index=True)
    empleado_id = db.Column(db.Integer, db.ForeignKey("empleado_productivo.id"), nullable=False, index=True)
    nombre = db.Column(db.String(160), nullable=False)
    minutos = db.Column(db.Numeric(12, 4), nullable=False)
    orden = db.Column(db.Integer, default=0, nullable=False)
    observacion = db.Column(db.String(500))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    perfil = db.relationship("PerfilCosteoProducto", backref="operaciones_costeo")
    empleado = db.relationship("EmpleadoProductivo")


class ProductoCostoFijoCosteo(db.Model):
    __tablename__ = "producto_costo_fijo_costeo"
    __table_args__ = (
        UniqueConstraint("perfil_costeo_id", "costo_fijo_id", name="uq_producto_costo_fijo_costeo"),
        CheckConstraint("porcentaje_asignacion > 0 AND porcentaje_asignacion <= 100", name="ck_producto_fijo_porcentaje"),
        CheckConstraint("unidades_mensuales > 0", name="ck_producto_fijo_unidades"),
    )
    id = db.Column(db.Integer, primary_key=True)
    perfil_costeo_id = db.Column(db.Integer, db.ForeignKey("perfil_costeo_producto.id"), nullable=False, index=True)
    costo_fijo_id = db.Column(db.Integer, db.ForeignKey("costo_fijo_productivo.id"), nullable=False, index=True)
    porcentaje_asignacion = db.Column(db.Numeric(9, 6), nullable=False)
    unidades_mensuales = db.Column(db.Numeric(18, 6), nullable=False)
    observacion = db.Column(db.String(500))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    perfil = db.relationship("PerfilCosteoProducto", backref="costos_fijos_costeo")
    costo_fijo = db.relationship("CostoFijoProductivo")
