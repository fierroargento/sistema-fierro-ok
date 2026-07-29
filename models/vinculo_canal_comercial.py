"""
Vinculación empresarial de cuentas de canales comerciales.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class VinculoCanalComercial(db.Model):
    """
    Asocia una cuenta externa con la estructura empresarial.

    La cuenta original no se modifica y el vínculo nuevo
    nace desactivado.
    """

    __tablename__ = "vinculo_canal_comercial"

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
    unidad_negocio_id = db.Column(
        db.Integer,
        db.ForeignKey("unidad_negocio.id"),
        nullable=False,
        index=True,
    )
    catalogo_id = db.Column(
        db.Integer,
        db.ForeignKey("catalogo.id"),
        nullable=True,
        index=True,
    )
    sucursal_operativa_id = db.Column(
        db.Integer,
        db.ForeignKey("sucursal_operativa.id"),
        nullable=True,
        index=True,
    )
    entidad_fiscal_id = db.Column(
        db.Integer,
        db.ForeignKey("entidad_fiscal.id"),
        nullable=True,
        index=True,
    )

    canal = db.Column(
        db.String(30),
        nullable=False,
        index=True,
    )
    mercado_libre_cuenta_id = db.Column(
        db.Integer,
        db.ForeignKey("mercado_libre_cuenta.id"),
        nullable=True,
        unique=True,
        index=True,
    )
    tienda_nube_cuenta_id = db.Column(
        db.Integer,
        db.ForeignKey("tienda_nube_cuenta.id"),
        nullable=True,
        unique=True,
        index=True,
    )

    nombre = db.Column(
        db.String(150),
        nullable=False,
    )
    estado = db.Column(
        db.String(20),
        default="desactivado",
        nullable=False,
        index=True,
    )
    detalle = db.Column(db.String(500))

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
        backref="vinculos_canales",
    )
    unidad_negocio = db.relationship(
        "UnidadNegocio",
        backref="vinculos_canales",
    )
    catalogo = db.relationship(
        "Catalogo",
        backref="vinculos_canales",
    )
    sucursal_operativa = db.relationship(
        "SucursalOperativa",
        backref="vinculos_canales",
    )
    entidad_fiscal = db.relationship(
        "EntidadFiscal",
        backref="vinculos_canales",
    )
    mercado_libre_cuenta = db.relationship(
        "MercadoLibreCuenta",
        backref="vinculo_comercial",
    )
    tienda_nube_cuenta = db.relationship(
        "TiendaNubeCuenta",
        backref="vinculo_comercial",
    )
