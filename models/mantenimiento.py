"""Mantenimiento preparatorio tenant sin ejecucion sobre maquinaria."""
from sqlalchemy import CheckConstraint,UniqueConstraint
from extensions import db
from services.fechas import ahora_utc_naive

class PlanMantenimiento(db.Model):
    __tablename__="plan_mantenimiento"
    __table_args__=(UniqueConstraint("organizacion_id","unidad_negocio_id","codigo",name="uq_plan_mantenimiento_tenant"),
        CheckConstraint("frecuencia_dias > 0",name="ck_plan_mantenimiento_frecuencia"),)
    id=db.Column(db.Integer,primary_key=True);organizacion_id=db.Column(db.Integer,db.ForeignKey("organizacion.id"),nullable=False,index=True)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey("unidad_negocio.id"),nullable=False,index=True);maquina_id=db.Column(db.Integer,db.ForeignKey("maquina_productiva.id"),nullable=False,index=True)
    codigo=db.Column(db.String(80),nullable=False);nombre=db.Column(db.String(180),nullable=False);frecuencia_dias=db.Column(db.Integer,nullable=False)
    proxima_fecha=db.Column(db.Date,nullable=False,index=True);instrucciones=db.Column(db.String(1000));activo=db.Column(db.Boolean,default=False,nullable=False,index=True)
    ejecucion_habilitada=db.Column(db.Boolean,default=False,nullable=False);creado_por_usuario_id=db.Column(db.Integer,db.ForeignKey("usuario_sistema.id"));fecha_creacion=db.Column(db.DateTime,default=ahora_utc_naive,nullable=False)
    maquina=db.relationship("MaquinaProductiva")

class OrdenMantenimientoPreparatoria(db.Model):
    __tablename__="orden_mantenimiento_preparatoria"
    __table_args__=(UniqueConstraint("organizacion_id","clave_idempotencia",name="uq_orden_mantenimiento_clave"),
        CheckConstraint("tipo IN ('preventivo','correctivo','inspeccion')",name="ck_orden_mantenimiento_tipo"),
        CheckConstraint("estado IN ('planificada','cancelada')",name="ck_orden_mantenimiento_estado"),
        CheckConstraint("ejecutada = false AND afecta_stock = false",name="ck_orden_mantenimiento_sin_impacto"),)
    id=db.Column(db.Integer,primary_key=True);organizacion_id=db.Column(db.Integer,db.ForeignKey("organizacion.id"),nullable=False,index=True)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey("unidad_negocio.id"),nullable=False,index=True);maquina_id=db.Column(db.Integer,db.ForeignKey("maquina_productiva.id"),nullable=False,index=True)
    plan_id=db.Column(db.Integer,db.ForeignKey("plan_mantenimiento.id"),index=True);tipo=db.Column(db.String(20),nullable=False);fecha_prevista=db.Column(db.Date,nullable=False,index=True)
    descripcion=db.Column(db.String(500),nullable=False);costo_estimado_centavos=db.Column(db.BigInteger,default=0,nullable=False);clave_idempotencia=db.Column(db.String(180),nullable=False)
    estado=db.Column(db.String(20),default="planificada",nullable=False,index=True);ejecutada=db.Column(db.Boolean,default=False,nullable=False);afecta_stock=db.Column(db.Boolean,default=False,nullable=False)
    observacion=db.Column(db.String(500));creado_por_usuario_id=db.Column(db.Integer,db.ForeignKey("usuario_sistema.id"));fecha_creacion=db.Column(db.DateTime,default=ahora_utc_naive,nullable=False)
    maquina=db.relationship("MaquinaProductiva");plan=db.relationship("PlanMantenimiento")

class TareaPlanMantenimiento(db.Model):
    __tablename__="tarea_plan_mantenimiento"
    __table_args__=(UniqueConstraint("plan_id","orden",name="uq_tarea_plan_mantenimiento_orden"),CheckConstraint("completada = false",name="ck_tarea_plan_no_ejecutada"),)
    id=db.Column(db.Integer,primary_key=True);organizacion_id=db.Column(db.Integer,db.ForeignKey("organizacion.id"),nullable=False,index=True);unidad_negocio_id=db.Column(db.Integer,db.ForeignKey("unidad_negocio.id"),nullable=False,index=True)
    plan_id=db.Column(db.Integer,db.ForeignKey("plan_mantenimiento.id"),nullable=False,index=True);orden=db.Column(db.Integer,nullable=False);descripcion=db.Column(db.String(300),nullable=False);obligatoria=db.Column(db.Boolean,default=True,nullable=False);completada=db.Column(db.Boolean,default=False,nullable=False);plan=db.relationship("PlanMantenimiento",backref="tareas_preparatorias")

class PropuestaRepuestoMantenimiento(db.Model):
    __tablename__="propuesta_repuesto_mantenimiento"
    __table_args__=(UniqueConstraint("orden_mantenimiento_id","codigo_repuesto",name="uq_propuesta_repuesto_orden_codigo"),CheckConstraint("cantidad > 0 AND costo_estimado_centavos >= 0",name="ck_propuesta_repuesto_valores"),CheckConstraint("aprobada = false AND reservado = false AND afecta_stock = false",name="ck_propuesta_repuesto_sin_impacto"),)
    id=db.Column(db.Integer,primary_key=True);organizacion_id=db.Column(db.Integer,db.ForeignKey("organizacion.id"),nullable=False,index=True);unidad_negocio_id=db.Column(db.Integer,db.ForeignKey("unidad_negocio.id"),nullable=False,index=True)
    orden_mantenimiento_id=db.Column(db.Integer,db.ForeignKey("orden_mantenimiento_preparatoria.id"),nullable=False,index=True);codigo_repuesto=db.Column(db.String(100),nullable=False);descripcion=db.Column(db.String(240),nullable=False);cantidad=db.Column(db.Numeric(14,4),nullable=False);costo_estimado_centavos=db.Column(db.BigInteger,default=0,nullable=False)
    aprobada=db.Column(db.Boolean,default=False,nullable=False);reservado=db.Column(db.Boolean,default=False,nullable=False);afecta_stock=db.Column(db.Boolean,default=False,nullable=False);orden_mantenimiento=db.relationship("OrdenMantenimientoPreparatoria",backref="repuestos_propuestos")
