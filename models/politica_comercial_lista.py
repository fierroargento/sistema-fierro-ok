"""Versiones historicas de politicas comerciales."""

from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text

from extensions import db
from services.fechas import ahora_utc_naive


class PoliticaComercialLista(db.Model):
    """Parametros comerciales usados para calcular precios."""

    __tablename__ = "politica_comercial_lista"
    __table_args__ = (
        UniqueConstraint(
            "lista_precio_id", "numero_version",
            name="uq_politica_lista_version",
        ),
        CheckConstraint("numero_version > 0", name="ck_politica_version"),
        CheckConstraint(
            "comision_pct >= 0 AND comision_pct < 100",
            name="ck_politica_comision",
        ),
        CheckConstraint(
            "margen_objetivo_pct >= 0 AND margen_objetivo_pct < 100",
            name="ck_politica_margen",
        ),
        CheckConstraint(
            "comision_pct + margen_objetivo_pct < 100",
            name="ck_politica_porcentajes",
        ),
        CheckConstraint(
            "cargo_fijo_centavos >= 0 AND flete_venta_centavos >= 0",
            name="ck_politica_fijos",
        ),
        CheckConstraint(
            "incremento_redondeo_centavos > 0",
            name="ck_politica_redondeo",
        ),
        CheckConstraint(
            "estado IN ('preparatorio', 'vigente', 'archivado', 'cancelado')",
            name="ck_politica_estado",
        ),
        CheckConstraint(
            "vigente = false OR estado = 'vigente'",
            name="ck_politica_vigente_estado",
        ),
        Index(
            "uq_politica_lista_vigente", "lista_precio_id", unique=True,
            postgresql_where=text("vigente IS TRUE"),
            sqlite_where=text("vigente IS TRUE"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    lista_precio_id = db.Column(
        db.Integer, db.ForeignKey("lista_precio.id"),
        nullable=False, index=True,
    )
    numero_version = db.Column(db.Integer, nullable=False)
    comision_pct = db.Column(db.Numeric(9, 6), default=0, nullable=False)
    cargo_fijo_centavos = db.Column(db.BigInteger, default=0, nullable=False)
    flete_venta_centavos = db.Column(db.BigInteger, default=0, nullable=False)
    margen_objetivo_pct = db.Column(db.Numeric(9, 6), default=0, nullable=False)
    incremento_redondeo_centavos = db.Column(
        db.BigInteger, default=1, nullable=False,
    )
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

    lista_precio = db.relationship("ListaPrecio", backref="politicas")
    creado_por_usuario = db.relationship(
        "UsuarioSistema", backref="politicas_comerciales_creadas",
    )
