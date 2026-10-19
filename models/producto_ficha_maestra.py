"""Datos generales y habilitaciones de la identidad Producto existente."""
from extensions import db


class ProductoFichaMaestra(db.Model):
    """Extensión 1:1 de Producto; nunca crea una segunda identidad/SKU.

    Se consulta por separado para que un deploy previo a preparar el esquema
    no cambie los SELECT del maestro operativo.
    """
    __tablename__ = "producto_ficha_maestra"
    __table_args__ = (
        db.CheckConstraint("tipo IN ('simple','produccion','combo')", name="ck_producto_ficha_tipo"),
        db.CheckConstraint("revision > 0", name="ck_producto_ficha_revision"),
        db.UniqueConstraint("insumo_id", name="uq_producto_ficha_insumo"),
    )
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id", ondelete="CASCADE"), primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    nombre = db.Column(db.String(200), nullable=False)
    linea = db.Column(db.String(120), nullable=False, default="")
    unidad_medida = db.Column(db.String(30), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    activo = db.Column(db.Boolean, nullable=False)
    habilita_compra = db.Column(db.Boolean, nullable=False)
    habilita_venta = db.Column(db.Boolean, nullable=False)
    habilita_insumo = db.Column(db.Boolean, nullable=False)
    habilita_componente = db.Column(db.Boolean, nullable=False)
    # Referencia a la fuente productiva, no copia de su precio o stock.
    insumo_id = db.Column(db.Integer, db.ForeignKey("insumo_productivo.id"), nullable=True)
    revision = db.Column(db.Integer, nullable=False, default=1)
