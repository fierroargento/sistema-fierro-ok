"""Resultado idempotente de incorporar un expediente TN al maestro de pedidos."""

from sqlalchemy import CheckConstraint, UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class ResultadoIncorporacionTiendaNube(db.Model):
    __tablename__ = "resultado_incorporacion_tienda_nube"
    __table_args__ = (
        UniqueConstraint("lote_id", name="uq_resultado_incorporacion_tn_lote"),
        CheckConstraint("acciones_externas = 0", name="ck_resultado_incorporacion_tn_sin_externas"),
    )
    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.Integer, db.ForeignKey("lote_incorporacion_tienda_nube.id"), nullable=False, index=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    pedidos_creados = db.Column(db.Integer, nullable=False)
    items_creados = db.Column(db.Integer, nullable=False)
    acciones_externas = db.Column(db.Integer, nullable=False, default=0)
    pedido_ids_json = db.Column(db.Text, nullable=False)
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    creado_por_username = db.Column(db.String(80))
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=ahora_utc_naive)
    lote = db.relationship("LoteIncorporacionTiendaNube", backref="resultado_incorporacion", uselist=False)
