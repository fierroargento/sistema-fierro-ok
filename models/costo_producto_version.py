"""
Versiones historicas del costo productivo.
"""

from sqlalchemy import CheckConstraint
from sqlalchemy import Index
from sqlalchemy import text

from extensions import db
from services.fechas import ahora_utc_naive


class CostoProductoVersion(db.Model):
    """
    Snapshot historico del costo de un producto por tenant.

    El producto continua siendo global. El costo pertenece siempre
    a una organizacion y puede ser general o especifico de una unidad.
    """

    __tablename__ = "costo_producto_version"

    __table_args__ = (
        CheckConstraint(
            "numero_version > 0",
            name="ck_costo_version_numero_positivo",
        ),
        CheckConstraint(
            "costo_total_centavos >= 0",
            name="ck_costo_version_total_no_negativo",
        ),
        CheckConstraint(
            "tipo IN ('manual', 'calculado')",
            name="ck_costo_version_tipo",
        ),
        CheckConstraint(
            "estado IN ("
            "'preparatorio', 'vigente', "
            "'archivado', 'cancelado'"
            ")",
            name="ck_costo_version_estado",
        ),
        CheckConstraint(
            "vigente_hasta IS NULL "
            "OR vigente_desde IS NULL "
            "OR vigente_hasta >= vigente_desde",
            name="ck_costo_version_vigencia_fechas",
        ),
        CheckConstraint(
            "vigente = false OR estado = 'vigente'",
            name="ck_costo_version_vigente_estado",
        ),
        Index(
            "uq_costo_version_num_general",
            "organizacion_id",
            "producto_id",
            "moneda",
            "numero_version",
            unique=True,
            postgresql_where=text(
                "unidad_negocio_id IS NULL"
            ),
            sqlite_where=text(
                "unidad_negocio_id IS NULL"
            ),
        ),
        Index(
            "uq_costo_version_num_unidad",
            "organizacion_id",
            "unidad_negocio_id",
            "producto_id",
            "moneda",
            "numero_version",
            unique=True,
            postgresql_where=text(
                "unidad_negocio_id IS NOT NULL"
            ),
            sqlite_where=text(
                "unidad_negocio_id IS NOT NULL"
            ),
        ),
        Index(
            "uq_costo_version_vigente_general",
            "organizacion_id",
            "producto_id",
            "moneda",
            unique=True,
            postgresql_where=text(
                "unidad_negocio_id IS NULL "
                "AND vigente IS TRUE"
            ),
            sqlite_where=text(
                "unidad_negocio_id IS NULL "
                "AND vigente IS TRUE"
            ),
        ),
        Index(
            "uq_costo_version_vigente_unidad",
            "organizacion_id",
            "unidad_negocio_id",
            "producto_id",
            "moneda",
            unique=True,
            postgresql_where=text(
                "unidad_negocio_id IS NOT NULL "
                "AND vigente IS TRUE"
            ),
            sqlite_where=text(
                "unidad_negocio_id IS NOT NULL "
                "AND vigente IS TRUE"
            ),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer,
        db.ForeignKey("organizacion.id"),
        nullable=False,
        index=True,
    )
    unidad_negocio_id = db.Column(
        db.Integer,
        db.ForeignKey("unidad_negocio.id"),
        nullable=True,
        index=True,
    )
    producto_id = db.Column(
        db.Integer,
        db.ForeignKey("producto.id"),
        nullable=False,
        index=True,
    )
    moneda = db.Column(
        db.String(3),
        default="ARS",
        nullable=False,
        index=True,
    )
    tipo = db.Column(
        db.String(20),
        default="calculado",
        nullable=False,
        index=True,
    )
    numero_version = db.Column(
        db.Integer,
        nullable=False,
    )
    costo_total_centavos = db.Column(
        db.BigInteger,
        nullable=False,
    )
    estado = db.Column(
        db.String(20),
        default="preparatorio",
        nullable=False,
        index=True,
    )
    vigente = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    vigente_desde = db.Column(db.DateTime)
    vigente_hasta = db.Column(db.DateTime)
    creado_por_usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuario_sistema.id"),
        nullable=True,
        index=True,
    )
    creado_por_username = db.Column(db.String(80))
    observacion = db.Column(db.String(500))
    fecha_creacion = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        nullable=False,
        index=True,
    )

    organizacion = db.relationship(
        "Organizacion",
        backref="versiones_costo_producto",
    )
    unidad_negocio = db.relationship(
        "UnidadNegocio",
        backref="versiones_costo_producto",
    )
    producto = db.relationship(
        "Producto",
        backref="versiones_costo",
    )
    creado_por_usuario = db.relationship(
        "UsuarioSistema",
        backref="versiones_costo_creadas",
    )
    detalles = db.relationship(
        "CostoProductoDetalle",
        back_populates="version",
        order_by="CostoProductoDetalle.orden",
    )
