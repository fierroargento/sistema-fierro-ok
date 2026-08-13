"""
Productos y condiciones comerciales de cada catálogo.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class CatalogoProducto(db.Model):
    """
    Inclusión de un producto existente en un catálogo comercial.

    Los importes se guardan en centavos para evitar errores
    de redondeo con números flotantes.
    """

    __tablename__ = "catalogo_producto"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    catalogo_id = db.Column(
        db.Integer,
        db.ForeignKey("catalogo.id"),
        nullable=False,
        index=True,
    )
    producto_id = db.Column(
        db.Integer,
        db.ForeignKey("producto.id"),
        nullable=False,
        index=True,
    )
    sku_comercial = db.Column(
        db.String(100),
        nullable=False,
        index=True,
    )
    nombre_comercial = db.Column(
        db.String(255),
        nullable=False,
    )
    marca = db.Column(db.String(120))
    categoria = db.Column(db.String(120))
    descripcion_corta = db.Column(db.String(300))
    descripcion_publica = db.Column(db.Text)
    estado_comercial = db.Column(
        db.String(20), default="borrador", nullable=False, index=True,
    )
    estado_disponibilidad = db.Column(
        db.String(20), default="no_disponible", nullable=False, index=True,
    )
    motivo_disponibilidad = db.Column(db.String(300))
    precio_centavos = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )
    precio_lista_centavos = db.Column(
        db.Integer,
        nullable=True,
    )
    disponible = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    activo = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    fecha_creacion = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
    )
    fecha_actualizacion = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        onupdate=ahora_utc_naive,
    )

    catalogo = db.relationship(
        "Catalogo",
        backref="productos_catalogo",
    )
    producto = db.relationship(
        "Producto",
        backref="inclusiones_catalogo",
    )
