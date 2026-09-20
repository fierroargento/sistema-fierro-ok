"""Modelos tenant de contabilidad preparatoria, sin registracion oficial."""

from sqlalchemy import CheckConstraint, UniqueConstraint
from extensions import db
from services.fechas import ahora_utc_naive


class CuentaContable(db.Model):
    __tablename__="cuenta_contable"
    __table_args__=(UniqueConstraint("organizacion_id","unidad_negocio_id","codigo",name="uq_cuenta_contable_tenant_unidad"),
        CheckConstraint("naturaleza IN ('activo','pasivo','patrimonio','ingreso','egreso','orden')",name="ck_cuenta_contable_naturaleza"),)
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey("organizacion.id"),nullable=False,index=True)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey("unidad_negocio.id"),nullable=False,index=True)
    codigo=db.Column(db.String(40),nullable=False)
    nombre=db.Column(db.String(180),nullable=False)
    naturaleza=db.Column(db.String(20),nullable=False,index=True)
    imputable=db.Column(db.Boolean,default=True,nullable=False)
    activa=db.Column(db.Boolean,default=False,nullable=False,index=True)
    creado_por_usuario_id=db.Column(db.Integer,db.ForeignKey("usuario_sistema.id"))
    fecha_creacion=db.Column(db.DateTime,default=ahora_utc_naive,nullable=False)


class AsientoContableBorrador(db.Model):
    __tablename__="asiento_contable_borrador"
    __table_args__=(UniqueConstraint("organizacion_id","clave_idempotencia",name="uq_asiento_borrador_clave"),
        CheckConstraint("estado IN ('borrador','anulado')",name="ck_asiento_borrador_estado"),
        CheckConstraint("total_debe_centavos = total_haber_centavos AND total_debe_centavos > 0",name="ck_asiento_borrador_balance"),
        CheckConstraint("contabilizado = false AND afecta_saldos = false",name="ck_asiento_borrador_sin_impacto"),)
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey("organizacion.id"),nullable=False,index=True)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey("unidad_negocio.id"),nullable=False,index=True)
    fecha=db.Column(db.Date,nullable=False,index=True)
    concepto=db.Column(db.String(220),nullable=False)
    cuenta_debe_id=db.Column(db.Integer,db.ForeignKey("cuenta_contable.id"),nullable=False,index=True)
    cuenta_haber_id=db.Column(db.Integer,db.ForeignKey("cuenta_contable.id"),nullable=False,index=True)
    total_debe_centavos=db.Column(db.BigInteger,nullable=False)
    total_haber_centavos=db.Column(db.BigInteger,nullable=False)
    referencia=db.Column(db.String(140))
    clave_idempotencia=db.Column(db.String(180),nullable=False)
    estado=db.Column(db.String(20),default="borrador",nullable=False,index=True)
    contabilizado=db.Column(db.Boolean,default=False,nullable=False)
    afecta_saldos=db.Column(db.Boolean,default=False,nullable=False)
    creado_por_usuario_id=db.Column(db.Integer,db.ForeignKey("usuario_sistema.id"))
    fecha_creacion=db.Column(db.DateTime,default=ahora_utc_naive,nullable=False)
    cuenta_debe=db.relationship("CuentaContable",foreign_keys=[cuenta_debe_id])
    cuenta_haber=db.relationship("CuentaContable",foreign_keys=[cuenta_haber_id])


class LineaAsientoContableBorrador(db.Model):
    __tablename__="linea_asiento_contable_borrador"
    __table_args__=(UniqueConstraint("asiento_borrador_id","renglon",name="uq_linea_asiento_borrador_renglon"),
        CheckConstraint("(debe_centavos > 0 AND haber_centavos = 0) OR (haber_centavos > 0 AND debe_centavos = 0)",name="ck_linea_borrador_partida"),
        CheckConstraint("afecta_saldos = false",name="ck_linea_borrador_sin_impacto"),)
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey("organizacion.id"),nullable=False,index=True)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey("unidad_negocio.id"),nullable=False,index=True)
    asiento_borrador_id=db.Column(db.Integer,db.ForeignKey("asiento_contable_borrador.id"),nullable=False,index=True)
    renglon=db.Column(db.Integer,nullable=False)
    cuenta_contable_id=db.Column(db.Integer,db.ForeignKey("cuenta_contable.id"),nullable=False,index=True)
    concepto=db.Column(db.String(220),nullable=False)
    debe_centavos=db.Column(db.BigInteger,default=0,nullable=False)
    haber_centavos=db.Column(db.BigInteger,default=0,nullable=False)
    afecta_saldos=db.Column(db.Boolean,default=False,nullable=False)
    asiento=db.relationship("AsientoContableBorrador",backref="lineas_borrador")
    cuenta=db.relationship("CuentaContable")
