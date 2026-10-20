"""Medidas y tareas del mismo perfil de fabricación; no guarda precios."""
from extensions import db


class ProductoDespieceCosteo(db.Model):
    __tablename__='producto_despiece_costeo'
    perfil_costeo_id=db.Column(db.Integer,db.ForeignKey('perfil_costeo_producto.id'),primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey('organizacion.id'),nullable=False,index=True)
    contenido=db.Column(db.Text,nullable=False)
    huella_composicion=db.Column(db.String(64),nullable=False)
    revision=db.Column(db.Integer,nullable=False,default=1)
