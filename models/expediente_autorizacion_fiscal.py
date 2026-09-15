"""Expediente certificado para una futura autorización fiscal."""
from sqlalchemy import CheckConstraint, UniqueConstraint
from extensions import db
from services.fechas import ahora_utc_naive

class ExpedienteAutorizacionFiscal(db.Model):
    __tablename__="expediente_autorizacion_fiscal"
    __table_args__=(UniqueConstraint("organizacion_id","borrador_comprobante_fiscal_id",name="uq_expediente_fiscal_borrador"),CheckConstraint("puede_emitir = false",name="ck_expediente_fiscal_sin_emision"),CheckConstraint("estado IN ('certificado','revocado')",name="ck_expediente_fiscal_estado"))
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey("organizacion.id"),nullable=False,index=True)
    borrador_comprobante_fiscal_id=db.Column(db.Integer,db.ForeignKey("borrador_comprobante_fiscal.id"),nullable=False,index=True)
    estado=db.Column(db.String(20),default="certificado",nullable=False,index=True)
    huella=db.Column(db.String(64),nullable=False,index=True)
    evidencia_json=db.Column(db.Text,nullable=False)
    puede_emitir=db.Column(db.Boolean,default=False,nullable=False)
    creado_por=db.Column(db.String(100))
    fecha_creacion=db.Column(db.DateTime,default=ahora_utc_naive,nullable=False)
    borrador=db.relationship("BorradorComprobanteFiscal",backref="expediente_autorizacion")
