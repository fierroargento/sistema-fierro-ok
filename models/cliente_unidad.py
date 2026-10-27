"""Disponibilidad y estado del cliente por unidad, con identidad compartida."""
from extensions import db


class ClienteUnidad(db.Model):
    __tablename__='cliente_unidad'
    __table_args__=(db.UniqueConstraint('cliente_id','unidad_negocio_id',name='uq_cliente_unidad'),)
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey('organizacion.id'),nullable=False,index=True)
    cliente_id=db.Column(db.Integer,db.ForeignKey('cliente_crm.id'),nullable=False,index=True)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey('unidad_negocio.id'),nullable=False,index=True)
    activo=db.Column(db.Boolean,nullable=False,default=False)
