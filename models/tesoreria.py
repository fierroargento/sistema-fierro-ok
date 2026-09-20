"""Tesoreria tenant preparatoria sin conexiones ni movimientos reales."""

from sqlalchemy import CheckConstraint, UniqueConstraint
from extensions import db
from services.fechas import ahora_utc_naive


class CuentaTesoreria(db.Model):
    __tablename__ = "cuenta_tesoreria"
    __table_args__ = (
        UniqueConstraint("organizacion_id","unidad_negocio_id","codigo",name="uq_cuenta_tesoreria_tenant_unidad"),
        CheckConstraint("tipo IN ('caja','banco','billetera_virtual','compensacion')",name="ck_cuenta_tesoreria_tipo"),
        CheckConstraint("conexion_externa = false",name="ck_cuenta_tesoreria_offline"),
    )
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey("organizacion.id"),nullable=False,index=True)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey("unidad_negocio.id"),nullable=False,index=True)
    codigo=db.Column(db.String(80),nullable=False)
    nombre=db.Column(db.String(180),nullable=False)
    tipo=db.Column(db.String(30),nullable=False,index=True)
    moneda=db.Column(db.String(3),default="ARS",nullable=False)
    saldo_inicial_centavos=db.Column(db.BigInteger,default=0,nullable=False)
    activa=db.Column(db.Boolean,default=False,nullable=False,index=True)
    conexion_externa=db.Column(db.Boolean,default=False,nullable=False)
    observacion=db.Column(db.String(500))
    creado_por_usuario_id=db.Column(db.Integer,db.ForeignKey("usuario_sistema.id"))
    fecha_creacion=db.Column(db.DateTime,default=ahora_utc_naive,nullable=False)


class MovimientoTesoreriaProyectado(db.Model):
    __tablename__ = "movimiento_tesoreria_proyectado"
    __table_args__ = (
        UniqueConstraint("organizacion_id","clave_idempotencia",name="uq_movimiento_tesoreria_proyectado_clave"),
        CheckConstraint("tipo IN ('ingreso','egreso')",name="ck_movimiento_tesoreria_tipo"),
        CheckConstraint("importe_centavos > 0",name="ck_movimiento_tesoreria_importe"),
        CheckConstraint("estado IN ('proyectado','cancelado')",name="ck_movimiento_tesoreria_estado"),
        CheckConstraint("confirmado = false AND afecta_saldo = false",name="ck_movimiento_tesoreria_sin_impacto"),
    )
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey("organizacion.id"),nullable=False,index=True)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey("unidad_negocio.id"),nullable=False,index=True)
    cuenta_tesoreria_id=db.Column(db.Integer,db.ForeignKey("cuenta_tesoreria.id"),nullable=False,index=True)
    tipo=db.Column(db.String(10),nullable=False,index=True)
    concepto=db.Column(db.String(220),nullable=False)
    origen=db.Column(db.String(40),default="manual",nullable=False,index=True)
    referencia=db.Column(db.String(140))
    importe_centavos=db.Column(db.BigInteger,nullable=False)
    fecha_prevista=db.Column(db.Date,nullable=False,index=True)
    clave_idempotencia=db.Column(db.String(180),nullable=False)
    estado=db.Column(db.String(20),default="proyectado",nullable=False,index=True)
    confirmado=db.Column(db.Boolean,default=False,nullable=False)
    afecta_saldo=db.Column(db.Boolean,default=False,nullable=False)
    observacion=db.Column(db.String(500))
    creado_por_usuario_id=db.Column(db.Integer,db.ForeignKey("usuario_sistema.id"))
    fecha_creacion=db.Column(db.DateTime,default=ahora_utc_naive,nullable=False)
    cuenta=db.relationship("CuentaTesoreria",backref="movimientos_proyectados")
