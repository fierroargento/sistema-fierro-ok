"""Lotes auditables de extractos Mercado Pago importados offline."""
from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from extensions import db
from services.fechas import ahora_utc_naive

class LoteImportacionMP(db.Model):
    __tablename__="lote_importacion_mp"
    __table_args__=(UniqueConstraint("organizacion_id","unidad_negocio_id","huella_documento",name="uq_lote_importacion_mp_huella"),CheckConstraint("estado IN ('confirmado','anulado')",name="ck_lote_importacion_mp_estado"),CheckConstraint("puede_ejecutar = false",name="ck_lote_importacion_mp_sin_ejecucion"),Index("ix_lote_importacion_mp_historial","organizacion_id","unidad_negocio_id","fecha_creacion"))
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey("organizacion.id"),nullable=False,index=True)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey("unidad_negocio.id"),nullable=False,index=True)
    cuenta_codigo=db.Column(db.String(100),nullable=False,index=True)
    nombre_archivo=db.Column(db.String(255),nullable=False)
    huella_documento=db.Column(db.String(64),nullable=False,index=True)
    estado=db.Column(db.String(20),default="confirmado",nullable=False,index=True)
    total_filas=db.Column(db.Integer,nullable=False)
    movimientos_creados=db.Column(db.Integer,nullable=False)
    rechazados=db.Column(db.Integer,default=0,nullable=False)
    evidencia_json=db.Column(db.Text,nullable=False)
    puede_ejecutar=db.Column(db.Boolean,default=False,nullable=False)
    creado_por_usuario_id=db.Column(db.Integer,db.ForeignKey("usuario_sistema.id"),index=True)
    creado_por_username=db.Column(db.String(80))
    fecha_creacion=db.Column(db.DateTime,default=ahora_utc_naive,nullable=False)
