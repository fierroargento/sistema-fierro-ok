"""
Modelo de auditoría de acciones operativas.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class Auditoria(db.Model):
    """Registro de una acción realizada dentro del sistema."""

    __tablename__ = "auditoria"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer)
    username = db.Column(db.String(80))
    nombre = db.Column(db.String(120))
    rol = db.Column(db.String(30))
    accion = db.Column(
        db.String(120),
        nullable=False,
    )
    entidad = db.Column(db.String(80))
    entidad_id = db.Column(db.String(80))
    detalle = db.Column(db.Text)
    fecha = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        index=True,
    )
    ip = db.Column(db.String(80))
    metodo = db.Column(db.String(10))
    path = db.Column(db.String(300))
