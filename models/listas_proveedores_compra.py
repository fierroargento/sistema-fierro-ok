"""Vínculos y cotizaciones por proveedor y unidad, sobre insumos existentes."""
from extensions import db
from sqlalchemy import text
from services.fechas import ahora_utc_naive

class MaterialProveedorCompra(db.Model):
    __tablename__='material_proveedor_compra'
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey('organizacion.id'),nullable=False,index=True)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey('unidad_negocio.id'),nullable=False,index=True)
    proveedor_id=db.Column(db.Integer,db.ForeignKey('proveedor_compra.id'),nullable=False,index=True)
    insumo_id=db.Column(db.Integer,db.ForeignKey('insumo_productivo.id'),nullable=False,index=True)
    codigo=db.Column(db.String(120),nullable=False)
    codigo_clave=db.Column(db.String(120),nullable=False)
    __table_args__=(db.UniqueConstraint('unidad_negocio_id','proveedor_id','codigo_clave',name='uq_material_proveedor_codigo'),db.UniqueConstraint('unidad_negocio_id','proveedor_id','insumo_id',name='uq_material_proveedor_insumo'))

class CotizacionProveedorCompra(db.Model):
    __tablename__='cotizacion_proveedor_compra'
    id=db.Column(db.Integer,primary_key=True)
    vinculo_id=db.Column(db.Integer,db.ForeignKey('material_proveedor_compra.id'),nullable=False,index=True)
    numero_version=db.Column(db.Integer,nullable=False)
    moneda=db.Column(db.String(3),nullable=False)
    precio_unitario_centavos=db.Column(db.BigInteger,nullable=False)
    cantidad_bulto=db.Column(db.Numeric(18,6))
    precio_bulto_centavos=db.Column(db.BigInteger)
    base_precio=db.Column(db.String(12),nullable=False)
    medidas_origen=db.Column(db.String(120),nullable=False,default='')
    referencia=db.Column(db.String(120),nullable=False,default='')
    vigente=db.Column(db.Boolean,nullable=False,default=True)
    fecha=db.Column(db.DateTime,nullable=False,default=ahora_utc_naive)
    precio_insumo_version_id=db.Column(db.Integer,db.ForeignKey('insumo_precio_version.id'))
    __table_args__=(db.UniqueConstraint('vinculo_id','moneda','numero_version',name='uq_cotizacion_proveedor_version'),db.Index('uq_cotizacion_proveedor_vigente','vinculo_id','moneda',unique=True,postgresql_where=text('vigente IS TRUE'),sqlite_where=text('vigente IS TRUE')),db.CheckConstraint("moneda IN ('ARS','USD')",name='ck_cotizacion_moneda'),db.CheckConstraint('precio_unitario_centavos >= 0',name='ck_cotizacion_precio'),db.CheckConstraint('numero_version > 0',name='ck_cotizacion_version'),db.CheckConstraint("base_precio IN ('unitario','bulto')",name='ck_cotizacion_base'),db.CheckConstraint('cantidad_bulto IS NULL OR cantidad_bulto > 0',name='ck_cotizacion_cantidad'))

class ConfiguracionListaProveedor(db.Model):
    __tablename__='configuracion_lista_proveedor'
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey('organizacion.id'),nullable=False)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey('unidad_negocio.id'),nullable=False)
    proveedor_id=db.Column(db.Integer,db.ForeignKey('proveedor_compra.id'),nullable=False)
    reglas=db.Column(db.JSON,nullable=False)
    __table_args__=(db.UniqueConstraint('unidad_negocio_id','proveedor_id',name='uq_config_lista_proveedor'),)

class CalculoCotizacionProveedor(db.Model):
    __tablename__='calculo_cotizacion_proveedor'
    cotizacion_id=db.Column(db.Integer,db.ForeignKey('cotizacion_proveedor_compra.id'),primary_key=True)
    datos=db.Column(db.JSON,nullable=False)
