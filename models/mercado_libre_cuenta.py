"""
Modelo de cuenta conectada a Mercado Libre.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class MercadoLibreCuenta(db.Model):
    """Credenciales y estado operativo de una cuenta Mercado Libre."""

    __tablename__ = "mercado_libre_cuenta"

    id = db.Column(db.Integer, primary_key=True)
    user_id_ml = db.Column(db.String(50))
    nickname = db.Column(db.String(120))
    access_token = db.Column(db.Text)
    refresh_token = db.Column(db.Text)
    token_expires_at = db.Column(db.DateTime)
    scope = db.Column(db.Text)
    estado_conexion = db.Column(
        db.String(30),
        default="desconectada",
    )
    last_sync_at = db.Column(db.DateTime)
    last_sync_status = db.Column(db.String(30))
    last_sync_detail = db.Column(db.Text)
    created_at = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
    )
    updated_at = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        onupdate=ahora_utc_naive,
    )
