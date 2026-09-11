"""Lotes internos de diagnostico Tienda Nube, sin ejecucion externa."""

from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class LoteDiagnosticoTiendaNube(db.Model):
    __tablename__ = "lote_diagnostico_tienda_nube"
    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "unidad_negocio_id", "tienda_nube_cuenta_id",
            "huella_documento", name="uq_lote_diagnostico_tn_documento",
        ),
        CheckConstraint(
            "estado IN ('preparado','revision','aprobado','rechazado','archivado')",
            name="ck_lote_diagnostico_tn_estado",
        ),
        CheckConstraint(
            "puede_ejecutar = false", name="ck_lote_diagnostico_tn_sin_ejecucion",
        ),
        Index(
            "ix_lote_diagnostico_tn_bandeja",
            "organizacion_id", "unidad_negocio_id", "estado", "fecha_creacion",
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    vinculo_canal_id = db.Column(db.Integer, db.ForeignKey("vinculo_canal_comercial.id"), nullable=False, index=True)
    tienda_nube_cuenta_id = db.Column(db.Integer, db.ForeignKey("tienda_nube_cuenta.id"), nullable=False, index=True)
    store_id_snapshot = db.Column(db.String(50), nullable=False, index=True)
    nombre_archivo = db.Column(db.String(255), nullable=False)
    huella_documento = db.Column(db.String(64), nullable=False, index=True)
    evidencia_json = db.Column(db.Text, nullable=False)
    filas = db.Column(db.Integer, nullable=False)
    aptas = db.Column(db.Integer, nullable=False)
    bloqueadas = db.Column(db.Integer, nullable=False)
    errores = db.Column(db.Integer, nullable=False)
    estado = db.Column(db.String(20), default="preparado", nullable=False, index=True)
    puede_ejecutar = db.Column(db.Boolean, default=False, nullable=False)
    motivo_decision = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    creado_por_username = db.Column(db.String(80))
    revisado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    revisado_por_username = db.Column(db.String(80))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_revision = db.Column(db.DateTime)


class EventoLoteDiagnosticoTiendaNube(db.Model):
    __tablename__ = "evento_lote_diagnostico_tienda_nube"
    __table_args__ = (
        Index("ix_evento_lote_tn_historial", "lote_diagnostico_id", "fecha_evento"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    lote_diagnostico_id = db.Column(db.Integer, db.ForeignKey("lote_diagnostico_tienda_nube.id"), nullable=False, index=True)
    estado_anterior = db.Column(db.String(20))
    estado_nuevo = db.Column(db.String(20), nullable=False)
    motivo = db.Column(db.String(500))
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    username = db.Column(db.String(80))
    fecha_evento = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    lote = db.relationship("LoteDiagnosticoTiendaNube", backref="eventos")
