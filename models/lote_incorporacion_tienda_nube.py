"""Expedientes certificados previos a incorporar pedidos Tienda Nube."""

from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class LoteIncorporacionTiendaNube(db.Model):
    __tablename__ = "lote_incorporacion_tienda_nube"
    __table_args__ = (
        UniqueConstraint("organizacion_id", "unidad_negocio_id", "firma_contenido", name="uq_lote_incorporacion_tn_firma"),
        CheckConstraint("estado IN ('certificado','observado','archivado')", name="ck_lote_incorporacion_tn_estado"),
        CheckConstraint("puede_ejecutar = false", name="ck_lote_incorporacion_tn_sin_ejecucion"),
        Index("ix_lote_incorporacion_tn_bandeja", "organizacion_id", "unidad_negocio_id", "estado"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    tienda_nube_cuenta_id = db.Column(db.Integer, db.ForeignKey("tienda_nube_cuenta.id"), nullable=False, index=True)
    firma_contenido = db.Column(db.String(64), nullable=False, index=True)
    evidencia_json = db.Column(db.Text, nullable=False)
    propuestas = db.Column(db.Integer, nullable=False)
    total_centavos = db.Column(db.BigInteger, nullable=False, default=0)
    estado = db.Column(db.String(20), nullable=False, default="certificado", index=True)
    puede_ejecutar = db.Column(db.Boolean, nullable=False, default=False)
    observaciones = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    creado_por_username = db.Column(db.String(80))
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=ahora_utc_naive)


class ItemLoteIncorporacionTiendaNube(db.Model):
    __tablename__ = "item_lote_incorporacion_tienda_nube"
    __table_args__ = (UniqueConstraint("lote_id", "propuesta_id", name="uq_item_lote_incorporacion_tn"),)
    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.Integer, db.ForeignKey("lote_incorporacion_tienda_nube.id"), nullable=False, index=True)
    propuesta_id = db.Column(db.Integer, db.ForeignKey("propuesta_pedido_tienda_nube.id"), nullable=False, index=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    tn_order_id = db.Column(db.String(50), nullable=False, index=True)
    snapshot_json = db.Column(db.Text, nullable=False)
    lote = db.relationship("LoteIncorporacionTiendaNube", backref="items")


class EventoLoteIncorporacionTiendaNube(db.Model):
    __tablename__ = "evento_lote_incorporacion_tienda_nube"
    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.Integer, db.ForeignKey("lote_incorporacion_tienda_nube.id"), nullable=False, index=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    estado_nuevo = db.Column(db.String(20), nullable=False)
    detalle = db.Column(db.String(500))
    username = db.Column(db.String(80))
    fecha_evento = db.Column(db.DateTime, nullable=False, default=ahora_utc_naive)
