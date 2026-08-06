"""Versiones historicas de precios por producto y lista."""

from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text

from extensions import db
from services.fechas import ahora_utc_naive


class ListaPrecioItem(db.Model):
    """Precio trazable a catalogo, costo y politica."""

    __tablename__ = "lista_precio_item"
    __table_args__ = (
        UniqueConstraint(
            "lista_precio_id", "catalogo_producto_id", "numero_version",
            name="uq_lista_item_producto_version",
        ),
        CheckConstraint("numero_version > 0", name="ck_lista_item_version"),
        CheckConstraint(
            "costo_base_centavos >= 0 AND precio_neto_sugerido_centavos >= 0 "
            "AND precio_elegido_centavos >= 0 AND impuestos_centavos >= 0 "
            "AND precio_final_centavos >= 0",
            name="ck_lista_item_importes",
        ),
        CheckConstraint(
            "estado IN ('preparatorio', 'vigente', 'archivado', 'cancelado')",
            name="ck_lista_item_estado",
        ),
        CheckConstraint(
            "vigente = false OR estado = 'vigente'",
            name="ck_lista_item_vigente_estado",
        ),
        Index(
            "uq_lista_item_vigente", "lista_precio_id",
            "catalogo_producto_id", unique=True,
            postgresql_where=text("vigente IS TRUE"),
            sqlite_where=text("vigente IS TRUE"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    lista_precio_id = db.Column(
        db.Integer, db.ForeignKey("lista_precio.id"), nullable=False, index=True,
    )
    catalogo_producto_id = db.Column(
        db.Integer, db.ForeignKey("catalogo_producto.id"),
        nullable=False, index=True,
    )
    costo_producto_version_id = db.Column(
        db.Integer, db.ForeignKey("costo_producto_version.id"),
        nullable=False, index=True,
    )
    politica_comercial_lista_id = db.Column(
        db.Integer, db.ForeignKey("politica_comercial_lista.id"),
        nullable=False, index=True,
    )
    numero_version = db.Column(db.Integer, nullable=False)
    costo_base_centavos = db.Column(db.BigInteger, nullable=False)
    precio_neto_sugerido_centavos = db.Column(db.BigInteger, nullable=False)
    precio_elegido_centavos = db.Column(db.BigInteger, nullable=False)
    impuestos_centavos = db.Column(db.BigInteger, default=0, nullable=False)
    precio_final_centavos = db.Column(db.BigInteger, nullable=False)
    margen_centavos = db.Column(db.BigInteger, nullable=False)
    margen_pct = db.Column(db.Numeric(9, 6), nullable=False)
    impuesto_pct = db.Column(db.Numeric(9, 6), default=0, nullable=False)
    estado = db.Column(
        db.String(20), default="preparatorio", nullable=False, index=True,
    )
    vigente = db.Column(db.Boolean, default=False, nullable=False, index=True)
    vigente_desde = db.Column(db.DateTime)
    vigente_hasta = db.Column(db.DateTime)
    creado_por_usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuario_sistema.id"), nullable=True,
    )
    creado_por_username = db.Column(db.String(80))
    fecha_creacion = db.Column(
        db.DateTime, default=ahora_utc_naive, nullable=False,
    )

    lista_precio = db.relationship("ListaPrecio", backref="items")
    catalogo_producto = db.relationship("CatalogoProducto", backref="precios_lista")
    costo_producto_version = db.relationship(
        "CostoProductoVersion", backref="precios_calculados",
    )
    politica_comercial = db.relationship(
        "PoliticaComercialLista", backref="precios_calculados",
    )
    creado_por_usuario = db.relationship(
        "UsuarioSistema", backref="precios_lista_creados",
    )
