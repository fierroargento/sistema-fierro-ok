"""
Modelo de configuración de una cuenta Tienda Nube.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class TiendaNubeCuenta(db.Model):
    """Estado de conexión y sincronización de Tienda Nube."""

    __tablename__ = "tienda_nube_cuenta"

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.String(50))
    estado_conexion = db.Column(
        db.String(30),
        default="configurada",
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
