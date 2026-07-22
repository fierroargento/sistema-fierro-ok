"""
Configuración operativa persistida del sistema.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class ConfiguracionSistema(db.Model):
    """Configuraciones simples sin hardcodes dispersos."""

    __tablename__ = "configuracion_sistema"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    clave = db.Column(
        db.String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    valor = db.Column(db.String(300))
    descripcion = db.Column(db.Text)
    actualizado_at = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        onupdate=ahora_utc_naive,
    )
