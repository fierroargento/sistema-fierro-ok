"""
Configuración técnica de facturación por entidad fiscal.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class ConfiguracionFiscal(db.Model):
    """
    Configuración independiente por CUIT.

    Solo guarda nombres de variables de entorno.
    Nunca almacena certificados, claves ni contraseñas.
    """

    __tablename__ = "configuracion_fiscal"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    organizacion_id = db.Column(
        db.Integer,
        db.ForeignKey("organizacion.id"),
        nullable=False,
        index=True,
    )
    entidad_fiscal_id = db.Column(
        db.Integer,
        db.ForeignKey("entidad_fiscal.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    proveedor = db.Column(
        db.String(30),
        default="arca",
        nullable=False,
    )
    ambiente = db.Column(
        db.String(30),
        default="homologacion",
        nullable=False,
        index=True,
    )
    certificado_env = db.Column(db.String(120))
    clave_privada_env = db.Column(db.String(120))
    token_env = db.Column(db.String(120))
    estado = db.Column(
        db.String(30),
        default="desactivada",
        nullable=False,
        index=True,
    )
    detalle = db.Column(db.String(500))
    ultima_prueba_at = db.Column(db.DateTime)
    ultima_prueba_estado = db.Column(db.String(30))
    ultima_prueba_detalle = db.Column(db.String(500))
    fecha_creacion = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
    )
    fecha_actualizacion = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        onupdate=ahora_utc_naive,
    )

    organizacion = db.relationship(
        "Organizacion",
        backref="configuraciones_fiscales",
    )
    entidad_fiscal = db.relationship(
        "EntidadFiscal",
        backref="configuracion_fiscal",
    )
