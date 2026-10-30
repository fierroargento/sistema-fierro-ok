"""Cotización manual general de empresa y desgaste láser versionado por unidad."""
from extensions import db
from sqlalchemy import text
from services.fechas import ahora_utc_naive

class CotizacionDolar(db.Model):
    __tablename__='cotizacion_dolar'
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey('organizacion.id'),nullable=False,index=True)
    numero_version=db.Column(db.Integer,nullable=False)
    valor_centavos=db.Column(db.BigInteger,nullable=False)
    fecha_cotizacion=db.Column(db.Date,nullable=False)
    referencia=db.Column(db.String(200),nullable=False)
    creado_por_usuario_id=db.Column(db.Integer)
    fecha_creacion=db.Column(db.DateTime,nullable=False,default=ahora_utc_naive)
    vigente=db.Column(db.Boolean,nullable=False,default=True)
    __table_args__=(db.UniqueConstraint('organizacion_id','numero_version',name='uq_cotizacion_dolar_version'),db.Index('uq_cotizacion_dolar_vigente','organizacion_id',unique=True,postgresql_where=text('vigente IS TRUE'),sqlite_where=text('vigente IS TRUE')),db.CheckConstraint('valor_centavos > 0 AND numero_version > 0',name='ck_cotizacion_dolar_positiva'))

class DesgasteLaserVersion(db.Model):
    __tablename__='desgaste_laser_version'
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey('organizacion.id'),nullable=False,index=True)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey('unidad_negocio.id'),nullable=False,index=True)
    maquina_id=db.Column(db.Integer,db.ForeignKey('maquina_productiva.id'),nullable=False,index=True)
    numero_version=db.Column(db.Integer,nullable=False)
    consumibles=db.Column(db.JSON,nullable=False)
    creado_por_usuario_id=db.Column(db.Integer)
    fecha_creacion=db.Column(db.DateTime,nullable=False,default=ahora_utc_naive)
    vigente=db.Column(db.Boolean,nullable=False,default=True)
    __table_args__=(db.UniqueConstraint('organizacion_id','unidad_negocio_id','numero_version',name='uq_desgaste_laser_version'),db.Index('uq_desgaste_laser_vigente','organizacion_id','unidad_negocio_id',unique=True,postgresql_where=text('vigente IS TRUE'),sqlite_where=text('vigente IS TRUE')),db.CheckConstraint('numero_version > 0',name='ck_desgaste_version_positiva'))
