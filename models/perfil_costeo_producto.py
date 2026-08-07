"""Clasificacion tenant de productos y composicion de combos."""

from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text

from extensions import db
from services.fechas import ahora_utc_naive


class PerfilCosteoProducto(db.Model):
    __tablename__ = "perfil_costeo_producto"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('simple', 'produccion', 'combo')",
            name="ck_perfil_costeo_tipo",
        ),
        Index(
            "uq_perfil_costeo_general", "organizacion_id", "producto_id",
            unique=True,
            postgresql_where=text("unidad_negocio_id IS NULL"),
            sqlite_where=text("unidad_negocio_id IS NULL"),
        ),
        Index(
            "uq_perfil_costeo_unidad", "organizacion_id", "unidad_negocio_id",
            "producto_id", unique=True,
            postgresql_where=text("unidad_negocio_id IS NOT NULL"),
            sqlite_where=text("unidad_negocio_id IS NOT NULL"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True,
    )
    unidad_negocio_id = db.Column(
        db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=True, index=True,
    )
    producto_id = db.Column(
        db.Integer, db.ForeignKey("producto.id"), nullable=False, index=True,
    )
    tipo = db.Column(db.String(20), nullable=False, index=True)
    activo = db.Column(db.Boolean, default=True, nullable=False, index=True)
    observacion = db.Column(db.String(500))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_actualizacion = db.Column(
        db.DateTime, default=ahora_utc_naive, onupdate=ahora_utc_naive,
        nullable=False,
    )

    unidad_negocio = db.relationship("UnidadNegocio")
    producto = db.relationship("Producto")


class ComboProductoComponente(db.Model):
    __tablename__ = "combo_producto_componente"
    __table_args__ = (
        UniqueConstraint(
            "combo_perfil_id", "componente_perfil_id",
            name="uq_combo_producto_componente",
        ),
        CheckConstraint("cantidad > 0", name="ck_combo_componente_cantidad"),
        CheckConstraint(
            "combo_perfil_id != componente_perfil_id",
            name="ck_combo_no_autorreferencia",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    combo_perfil_id = db.Column(
        db.Integer, db.ForeignKey("perfil_costeo_producto.id"),
        nullable=False, index=True,
    )
    componente_perfil_id = db.Column(
        db.Integer, db.ForeignKey("perfil_costeo_producto.id"),
        nullable=False, index=True,
    )
    cantidad = db.Column(db.Numeric(18, 6), nullable=False)
    observacion = db.Column(db.String(500))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)

    combo = db.relationship(
        "PerfilCosteoProducto", foreign_keys=[combo_perfil_id],
        backref="componentes_combo",
    )
    componente = db.relationship(
        "PerfilCosteoProducto", foreign_keys=[componente_perfil_id],
    )
