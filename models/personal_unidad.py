"""Vinculación explícita del mismo legajo con varias unidades, sin duplicar sueldo."""
from extensions import db


class PersonalUnidad(db.Model):
    __tablename__='personal_unidad'
    __table_args__=(db.UniqueConstraint('empleado_id','unidad_negocio_id',name='uq_personal_unidad'),)
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey('organizacion.id'),nullable=False,index=True)
    empleado_id=db.Column(db.Integer,db.ForeignKey('empleado_productivo.id'),nullable=False,index=True)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey('unidad_negocio.id'),nullable=False,index=True)
