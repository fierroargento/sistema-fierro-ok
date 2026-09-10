"""Cola tenant de tareas ML para gestion humana; nunca ejecuta el canal."""

from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class TareaManualML(db.Model):
    __tablename__ = "tarea_manual_ml"
    __table_args__ = (
        UniqueConstraint("organizacion_id", "clave_idempotencia", name="uq_tarea_manual_ml_tenant"),
        CheckConstraint("tipo_accion IN ('cancelar_promocion', 'actualizar_precio')", name="ck_tarea_manual_ml_tipo"),
        CheckConstraint("estado IN ('preparada', 'aprobada', 'rechazada', 'completada_manual', 'obsoleta', 'archivada')", name="ck_tarea_manual_ml_estado"),
        CheckConstraint("puede_ejecutar = false", name="ck_tarea_manual_ml_sin_ejecucion"),
        Index("ix_tarea_manual_ml_bandeja", "organizacion_id", "unidad_negocio_id", "estado"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    lote_diagnostico_id = db.Column(db.Integer, db.ForeignKey("lote_diagnostico_ml.id"), nullable=False, index=True)
    depende_de_id = db.Column(db.Integer, db.ForeignKey("tarea_manual_ml.id"), index=True)
    publicacion_id = db.Column(db.String(120), nullable=False, index=True)
    sku = db.Column(db.String(120))
    tipo_accion = db.Column(db.String(30), nullable=False)
    orden = db.Column(db.Integer, nullable=False)
    precio_actual_centavos = db.Column(db.BigInteger)
    precio_propuesto_centavos = db.Column(db.BigInteger)
    clave_idempotencia = db.Column(db.String(64), nullable=False)
    huella_origen = db.Column(db.String(64), nullable=False, index=True)
    snapshot_json = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(24), default="preparada", nullable=False, index=True)
    puede_ejecutar = db.Column(db.Boolean, default=False, nullable=False)
    comprobante_manual = db.Column(db.String(500))
    creado_por_username = db.Column(db.String(80))
    decidido_por_username = db.Column(db.String(80))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_decision = db.Column(db.DateTime)
    depende_de = db.relationship("TareaManualML", remote_side=[id])
    lote = db.relationship("LoteDiagnosticoML", backref="tareas_manuales")


class EventoTareaManualML(db.Model):
    __tablename__ = "evento_tarea_manual_ml"
    __table_args__ = (
        Index("ix_evento_tarea_manual_ml_historial", "tarea_manual_id", "fecha_evento"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    tarea_manual_id = db.Column(db.Integer, db.ForeignKey("tarea_manual_ml.id"), nullable=False, index=True)
    estado_anterior = db.Column(db.String(24))
    estado_nuevo = db.Column(db.String(24), nullable=False)
    comprobante = db.Column(db.String(500))
    username = db.Column(db.String(80))
    fecha_evento = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    tarea = db.relationship("TareaManualML", backref="eventos")
