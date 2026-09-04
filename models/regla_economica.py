"""Reglas historicas del piso economico interno por tenant."""

from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text

from extensions import db
from services.fechas import ahora_utc_naive


class ReglaEconomicaVersion(db.Model):
    __tablename__ = "regla_economica_version"
    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "clave_alcance", "numero_version",
            name="uq_regla_economica_version",
        ),
        CheckConstraint(
            "alcance IN ('organizacion', 'unidad', 'catalogo', 'producto')",
            name="ck_regla_economica_alcance",
        ),
        CheckConstraint(
            "metodo_utilidad IN ('sobre_costo', 'sobre_liquidacion')",
            name="ck_regla_economica_utilidad",
        ),
        CheckConstraint(
            "metodo_impuesto IN ('sobre_costo', 'sobre_liquidacion')",
            name="ck_regla_economica_impuesto",
        ),
        CheckConstraint(
            "impuesto_pct >= 0 AND impuesto_pct < 100 AND utilidad_minima_pct >= 0 "
            "AND utilidad_objetivo_pct >= utilidad_minima_pct "
            "AND utilidad_objetivo_pct < 100",
            name="ck_regla_economica_porcentajes",
        ),
        CheckConstraint(
            "estado IN ('preparatorio', 'vigente', 'archivado', 'cancelado')",
            name="ck_regla_economica_estado",
        ),
        CheckConstraint("incremento_redondeo_centavos > 0", name="ck_regla_economica_redondeo"),
        Index(
            "uq_regla_economica_vigente", "organizacion_id", "clave_alcance",
            unique=True, postgresql_where=text("vigente IS TRUE"),
            sqlite_where=text("vigente IS TRUE"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), index=True)
    catalogo_id = db.Column(db.Integer, db.ForeignKey("catalogo.id"), index=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"), index=True)
    alcance = db.Column(db.String(20), nullable=False, index=True)
    clave_alcance = db.Column(db.String(80), nullable=False, index=True)
    numero_version = db.Column(db.Integer, nullable=False)
    nombre = db.Column(db.String(160), nullable=False)
    impuesto_pct = db.Column(db.Numeric(9, 6), default=0, nullable=False)
    metodo_impuesto = db.Column(db.String(24), default="sobre_liquidacion", nullable=False)
    utilidad_minima_pct = db.Column(db.Numeric(9, 6), default=0, nullable=False)
    utilidad_objetivo_pct = db.Column(db.Numeric(9, 6), default=0, nullable=False)
    metodo_utilidad = db.Column(db.String(24), default="sobre_costo", nullable=False)
    incremento_redondeo_centavos = db.Column(db.BigInteger, default=1, nullable=False)
    estado = db.Column(db.String(20), default="preparatorio", nullable=False, index=True)
    vigente = db.Column(db.Boolean, default=False, nullable=False, index=True)
    vigente_desde = db.Column(db.DateTime)
    vigente_hasta = db.Column(db.DateTime)
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    creado_por_username = db.Column(db.String(80))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)

    organizacion = db.relationship("Organizacion")
    unidad_negocio = db.relationship("UnidadNegocio")
    catalogo = db.relationship("Catalogo")
    producto = db.relationship("Producto")
    creado_por_usuario = db.relationship("UsuarioSistema")
