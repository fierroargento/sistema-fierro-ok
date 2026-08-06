"""Cabeceras de listas de precios por tenant."""

from sqlalchemy import CheckConstraint, UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class ListaPrecio(db.Model):
    """Lista comercial general o especifica de una unidad."""

    __tablename__ = "lista_precio"
    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "codigo",
            name="uq_lista_precio_organizacion_codigo",
        ),
        CheckConstraint(
            "tipo IN ('mostrador', 'tiendanube', 'mercadolibre', 'mayorista')",
            name="ck_lista_precio_tipo",
        ),
        CheckConstraint(
            "estado IN ('preparatorio', 'activo', 'archivado', 'cancelado')",
            name="ck_lista_precio_estado",
        ),
        CheckConstraint(
            "vigente_hasta IS NULL OR vigente_desde IS NULL "
            "OR vigente_hasta >= vigente_desde",
            name="ck_lista_precio_vigencia",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"),
        nullable=False, index=True,
    )
    unidad_negocio_id = db.Column(
        db.Integer, db.ForeignKey("unidad_negocio.id"),
        nullable=True, index=True,
    )
    codigo = db.Column(db.String(80), nullable=False, index=True)
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.String(500))
    tipo = db.Column(db.String(20), nullable=False, index=True)
    moneda = db.Column(db.String(3), default="ARS", nullable=False)
    estado = db.Column(
        db.String(20), default="preparatorio", nullable=False, index=True,
    )
    vigente_desde = db.Column(db.DateTime)
    vigente_hasta = db.Column(db.DateTime)
    creado_por_usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuario_sistema.id"),
        nullable=True, index=True,
    )
    creado_por_username = db.Column(db.String(80))
    fecha_creacion = db.Column(
        db.DateTime, default=ahora_utc_naive, nullable=False,
    )
    fecha_actualizacion = db.Column(
        db.DateTime, default=ahora_utc_naive,
        onupdate=ahora_utc_naive, nullable=False,
    )

    organizacion = db.relationship("Organizacion", backref="listas_precio")
    unidad_negocio = db.relationship("UnidadNegocio", backref="listas_precio")
    creado_por_usuario = db.relationship(
        "UsuarioSistema", backref="listas_precio_creadas",
    )
