"""Datos comerciales observados en publicaciones, desacoplados del canal externo."""

from sqlalchemy import CheckConstraint, Index

from extensions import db
from services.fechas import ahora_utc_naive


class ObservacionComercialCanal(db.Model):
    __tablename__ = "observacion_comercial_canal"
    __table_args__ = (
        CheckConstraint("tipo IN ('precio', 'cargo', 'envio')", name="ck_observacion_comercial_tipo"),
        CheckConstraint("origen IN ('manual', 'importacion', 'canal')", name="ck_observacion_comercial_origen"),
        CheckConstraint("precio_publicado_centavos IS NULL OR precio_publicado_centavos >= 0", name="ck_observacion_precio"),
        CheckConstraint("comision_pct IS NULL OR (comision_pct >= 0 AND comision_pct < 100)", name="ck_observacion_comision"),
        CheckConstraint("cargo_fijo_centavos IS NULL OR cargo_fijo_centavos >= 0", name="ck_observacion_cargo"),
        CheckConstraint("costo_envio_centavos IS NULL OR costo_envio_centavos >= 0", name="ck_observacion_envio"),
        Index("ix_observacion_comercial_publicacion", "organizacion_id", "cuenta_codigo", "referencia_publicacion", "fecha_observacion"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    lista_precio_id = db.Column(db.Integer, db.ForeignKey("lista_precio.id"), nullable=False, index=True)
    catalogo_producto_id = db.Column(db.Integer, db.ForeignKey("catalogo_producto.id"), nullable=False, index=True)
    tipo = db.Column(db.String(20), nullable=False, index=True)
    cuenta_codigo = db.Column(db.String(100), nullable=False, index=True)
    referencia_publicacion = db.Column(db.String(160), nullable=False, index=True)
    precio_publicado_centavos = db.Column(db.BigInteger)
    comision_pct = db.Column(db.Numeric(9, 6))
    cargo_fijo_centavos = db.Column(db.BigInteger)
    costo_envio_centavos = db.Column(db.BigInteger)
    origen = db.Column(db.String(20), default="importacion", nullable=False, index=True)
    fecha_observacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False, index=True)
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    creado_por_username = db.Column(db.String(80))
    lote_importacion_id = db.Column(db.Integer, db.ForeignKey("importacion_masiva_costo.id"), index=True)
    lista_precio = db.relationship("ListaPrecio")
    catalogo_producto = db.relationship("CatalogoProducto")
