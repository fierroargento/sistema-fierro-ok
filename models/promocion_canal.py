"""Observaciones inmutables de promociones comerciales por tenant y canal."""

from sqlalchemy import CheckConstraint, Index

from extensions import db
from services.fechas import ahora_utc_naive


class PromocionCanalObservacion(db.Model):
    __tablename__ = "promocion_canal_observacion"
    __table_args__ = (
        CheckConstraint(
            "estado_observado IN ('activa', 'inactiva')",
            name="ck_promocion_canal_estado",
        ),
        CheckConstraint(
            "origen IN ('manual', 'importacion', 'canal')",
            name="ck_promocion_canal_origen",
        ),
        CheckConstraint(
            "precio_base_centavos >= 0 AND precio_promocional_centavos >= 0 "
            "AND precio_promocional_centavos <= precio_base_centavos",
            name="ck_promocion_canal_precios",
        ),
        CheckConstraint(
            "descuento_pct >= 0 AND descuento_pct <= 100",
            name="ck_promocion_canal_descuento",
        ),
        Index(
            "ix_promocion_canal_producto_fecha", "lista_precio_id",
            "catalogo_producto_id", "fecha_observacion",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    lista_precio_id = db.Column(db.Integer, db.ForeignKey("lista_precio.id"), nullable=False, index=True)
    catalogo_producto_id = db.Column(db.Integer, db.ForeignKey("catalogo_producto.id"), nullable=False, index=True)
    referencia_externa = db.Column(db.String(160), index=True)
    nombre = db.Column(db.String(160))
    precio_base_centavos = db.Column(db.BigInteger, nullable=False)
    precio_promocional_centavos = db.Column(db.BigInteger, nullable=False)
    descuento_pct = db.Column(db.Numeric(9, 6), nullable=False)
    estado_observado = db.Column(db.String(20), nullable=False, index=True)
    origen = db.Column(db.String(20), default="manual", nullable=False, index=True)
    fecha_observacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False, index=True)
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    creado_por_username = db.Column(db.String(80))
    observacion = db.Column(db.String(500))

    organizacion = db.relationship("Organizacion")
    unidad_negocio = db.relationship("UnidadNegocio")
    lista_precio = db.relationship("ListaPrecio")
    catalogo_producto = db.relationship("CatalogoProducto")
    creado_por_usuario = db.relationship("UsuarioSistema")
