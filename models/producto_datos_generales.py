"""Atributos y relaciones del mismo Producto; sin otra identidad ni stock."""
from extensions import db


class ProductoDatosGenerales(db.Model):
    __tablename__ = 'producto_datos_generales'
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id', ondelete='CASCADE'), primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey('organizacion.id'), nullable=False, index=True)
    rubro = db.Column(db.String(120), nullable=False, default='')
    subrubro = db.Column(db.String(120), nullable=False, default='')
    marca = db.Column(db.String(120), nullable=False, default='')
    # El importe vive en el historial de Costos; aquí solo se referencia.
    costo_carga_id = db.Column(db.Integer, db.ForeignKey('costo_producto_version.id'))
    moneda_costo = db.Column(db.String(3), nullable=False, default='ARS', server_default='ARS')
    iva_pct = db.Column(db.Numeric(9, 6))
    utilidad_pct = db.Column(db.Numeric(12, 6))
    utilidad_base = db.Column(db.String(20), nullable=False, default='costo')
    sucursales_definidas = db.Column(db.Boolean, nullable=False, default=False)
    depositos_definidos = db.Column(db.Boolean, nullable=False, default=False)
    revision = db.Column(db.Integer, nullable=False, default=1)
    __table_args__ = (
        db.CheckConstraint("moneda_costo IN ('ARS','USD')", name='ck_producto_moneda_costo'),
        db.CheckConstraint("iva_pct IS NULL OR (iva_pct >= 0 AND iva_pct <= 100)", name='ck_producto_iva_pct'),
        db.CheckConstraint("utilidad_base IN ('costo','precio_venta')", name='ck_producto_utilidad_base'),
        db.CheckConstraint("utilidad_pct IS NULL OR (utilidad_pct >= 0 AND (utilidad_base != 'precio_venta' OR utilidad_pct < 100))", name='ck_producto_utilidad_pct'),
        db.CheckConstraint("subrubro = '' OR rubro != ''", name='ck_producto_subrubro_padre'),
    )


class ProductoProveedor(db.Model):
    __tablename__ = 'producto_proveedor'
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey('organizacion.id'), nullable=False, index=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id', ondelete='CASCADE'), nullable=False, index=True)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedor_compra.id'), nullable=False, index=True)
    codigo = db.Column(db.String(120), nullable=False, default='')
    codigo_clave = db.Column(db.String(120))
    principal = db.Column(db.Boolean, nullable=False, default=False)
    __table_args__ = (
        db.UniqueConstraint('organizacion_id', 'producto_id', 'proveedor_id', name='uq_producto_proveedor'),
        db.UniqueConstraint('organizacion_id', 'proveedor_id', 'codigo_clave', name='uq_producto_codigo_proveedor'),
    )


class ProductoUbicacion(db.Model):
    __tablename__ = 'producto_ubicacion'
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey('organizacion.id'), nullable=False, index=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id', ondelete='CASCADE'), nullable=False, index=True)
    sucursal_operativa_id = db.Column(db.Integer, db.ForeignKey('sucursal_operativa.id'), nullable=False, index=True)
    tipo = db.Column(db.String(12), nullable=False)
    __table_args__ = (
        db.CheckConstraint("tipo IN ('sucursal','deposito')", name='ck_producto_ubicacion_tipo'),
        db.UniqueConstraint('organizacion_id', 'producto_id', 'sucursal_operativa_id', 'tipo', name='uq_producto_ubicacion'),
    )


class ProductoCodigoBarras(db.Model):
    __tablename__ = 'producto_codigo_barras'
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey('organizacion.id'), nullable=False, index=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id', ondelete='CASCADE'), nullable=False, index=True)
    codigo = db.Column(db.String(80), nullable=False)
    __table_args__ = (db.UniqueConstraint('organizacion_id', 'codigo', name='uq_producto_codigo_barras'),)


class ProductoImagenMaestra(db.Model):
    __tablename__ = 'producto_imagen_maestra'
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey('organizacion.id'), nullable=False, index=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id', ondelete='CASCADE'), nullable=False, index=True)
    nombre = db.Column(db.String(180), nullable=False)
    mime = db.Column(db.String(30), nullable=False)
    contenido = db.deferred(db.Column(db.LargeBinary, nullable=False))
    sha256 = db.Column(db.String(64), nullable=False)
    principal = db.Column(db.Boolean, nullable=False, default=False)
    ancho = db.Column(db.Integer, nullable=False)
    alto = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.UniqueConstraint('producto_id', 'sha256', name='uq_producto_imagen_contenido'),)


TABLAS_DATOS_PRODUCTO = [ProductoDatosGenerales.__table__, ProductoProveedor.__table__,
    ProductoUbicacion.__table__, ProductoCodigoBarras.__table__, ProductoImagenMaestra.__table__]
