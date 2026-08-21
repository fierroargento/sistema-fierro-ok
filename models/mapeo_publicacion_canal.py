"""Identidad externa de publicaciones por cuenta comercial exacta."""

from sqlalchemy import UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class MapeoPublicacionCanal(db.Model):
    __tablename__ = "mapeo_publicacion_canal"
    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "vinculo_canal_comercial_id",
            "catalogo_producto_id",
            name="uq_mapeo_publicacion_cuenta_producto",
        ),
        UniqueConstraint(
            "organizacion_id", "vinculo_canal_comercial_id",
            "publicacion_externa_id", "variante_externa_id",
            name="uq_mapeo_publicacion_cuenta_identidad_externa",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True,
    )
    vinculo_canal_comercial_id = db.Column(
        db.Integer, db.ForeignKey("vinculo_canal_comercial.id"),
        nullable=False, index=True,
    )
    catalogo_producto_id = db.Column(
        db.Integer, db.ForeignKey("catalogo_producto.id"), nullable=False,
        index=True,
    )
    canal = db.Column(db.String(30), nullable=False, index=True)
    publicacion_externa_id = db.Column(db.String(160), nullable=False, index=True)
    variante_externa_id = db.Column(db.String(160), default="", nullable=False)
    sku_externo = db.Column(db.String(160), index=True)
    estado = db.Column(
        db.String(40), default="preparado_sin_conexion",
        nullable=False, index=True,
    )
    identidad_verificada = db.Column(db.Boolean, default=False, nullable=False)
    permite_sincronizar = db.Column(db.Boolean, default=False, nullable=False)
    diagnostico = db.Column(db.Text)
    metadatos_json = db.Column(db.Text, default="{}", nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_actualizacion = db.Column(
        db.DateTime, default=ahora_utc_naive, onupdate=ahora_utc_naive,
    )

    vinculo_canal = db.relationship("VinculoCanalComercial")
    catalogo_producto = db.relationship("CatalogoProducto")
