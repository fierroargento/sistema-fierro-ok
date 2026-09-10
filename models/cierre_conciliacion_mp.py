"""Cierres internos de conciliacion MP, inmutables y sin movimiento de dinero."""

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from extensions import db
from services.fechas import ahora_utc_naive


class CierreConciliacionMP(db.Model):
    __tablename__="cierre_conciliacion_mp"
    __table_args__=(
        UniqueConstraint("organizacion_id","unidad_negocio_id","huella_origen",name="uq_cierre_conciliacion_mp_huella"),
        CheckConstraint("estado IN ('preparado','revision','aprobado','obsoleto','cerrado','archivado')",name="ck_cierre_conciliacion_mp_estado"),
        CheckConstraint("puede_ejecutar = false",name="ck_cierre_conciliacion_mp_sin_ejecucion"),
        Index("ix_cierre_conciliacion_mp_bandeja","organizacion_id","unidad_negocio_id","estado"),
    )
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey("organizacion.id"),nullable=False,index=True)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey("unidad_negocio.id"),nullable=False,index=True)
    huella_origen=db.Column(db.String(64),nullable=False,index=True)
    snapshot_json=db.Column(db.Text,nullable=False)
    certificacion_json=db.Column(db.Text,nullable=False)
    estado=db.Column(db.String(20),default="preparado",nullable=False,index=True)
    puede_ejecutar=db.Column(db.Boolean,default=False,nullable=False)
    motivo=db.Column(db.String(500))
    creado_por_username=db.Column(db.String(80))
    decidido_por_username=db.Column(db.String(80))
    fecha_creacion=db.Column(db.DateTime,default=ahora_utc_naive,nullable=False)
    fecha_decision=db.Column(db.DateTime)


class EventoCierreConciliacionMP(db.Model):
    __tablename__="evento_cierre_conciliacion_mp"
    __table_args__=(Index("ix_evento_cierre_mp_historial","cierre_id","fecha_evento"),)
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey("organizacion.id"),nullable=False,index=True)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey("unidad_negocio.id"),nullable=False,index=True)
    cierre_id=db.Column(db.Integer,db.ForeignKey("cierre_conciliacion_mp.id"),nullable=False,index=True)
    estado_anterior=db.Column(db.String(20))
    estado_nuevo=db.Column(db.String(20),nullable=False)
    motivo=db.Column(db.String(500))
    username=db.Column(db.String(80))
    fecha_evento=db.Column(db.DateTime,default=ahora_utc_naive,nullable=False)
    cierre=db.relationship("CierreConciliacionMP",backref="eventos")
