"""
Membresia de un usuario dentro de una organizacion SaaS.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class UsuarioOrganizacion(db.Model):
    """
    Vincula usuarios con tenants y conserva el rol por organizacion.
    """

    __tablename__ = "usuario_organizacion"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuario_sistema.id"),
        nullable=False,
        index=True,
    )
    organizacion_id = db.Column(
        db.Integer,
        db.ForeignKey("organizacion.id"),
        nullable=False,
        index=True,
    )
    rol = db.Column(
        db.String(30),
        nullable=False,
        default="carga",
    )
    activa = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    predeterminada = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )
    fecha_creacion = db.Column(
        db.DateTime,
        nullable=False,
        default=ahora_utc_naive,
    )
    fecha_actualizacion = db.Column(
        db.DateTime,
        nullable=False,
        default=ahora_utc_naive,
        onupdate=ahora_utc_naive,
    )

    usuario = db.relationship(
        "UsuarioSistema",
        backref=db.backref(
            "membresias_organizacion",
            lazy=True,
        ),
    )
    organizacion = db.relationship(
        "Organizacion",
        backref=db.backref(
            "membresias_usuario",
            lazy=True,
        ),
    )

    __table_args__ = (
        db.UniqueConstraint(
            "usuario_id",
            "organizacion_id",
            name=(
                "uq_usuario_organizacion_"
                "usuario_organizacion"
            ),
        ),
    )
