"""
Modelo de usuarios internos del sistema.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class UsuarioSistema(db.Model):
    """Usuario autenticable con rol operativo."""

    __tablename__ = "usuario_sistema"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash = db.Column(
        db.String(255),
        nullable=False,
    )
    nombre = db.Column(
        db.String(120),
        nullable=False,
    )
    rol = db.Column(
        db.String(30),
        nullable=False,
        default="carga",
    )
    activo = db.Column(
        db.Boolean,
        default=True,
    )
    fecha_creacion = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
    )
    creado_por = db.Column(db.String(80))
    actualizado_at = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        onupdate=ahora_utc_naive,
    )
