"""Núcleo tenant de proveedores, órdenes y recepciones preparatorias."""

from sqlalchemy import CheckConstraint, UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class ProveedorCompra(db.Model):
    __tablename__ = "proveedor_compra"
    __table_args__ = (
        UniqueConstraint("organizacion_id", "codigo", name="uq_proveedor_compra_tenant_codigo"),
        UniqueConstraint("organizacion_id", "cuit", name="uq_proveedor_compra_tenant_cuit"),
        CheckConstraint("estado IN ('activo', 'inactivo')", name="ck_proveedor_compra_estado"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    codigo = db.Column(db.String(80), nullable=False)
    razon_social = db.Column(db.String(200), nullable=False)
    cuit = db.Column(db.String(16), index=True)
    email = db.Column(db.String(200))
    telefono = db.Column(db.String(80))
    estado = db.Column(db.String(20), default="activo", nullable=False, index=True)
    observacion = db.Column(db.String(500))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)


class OrdenCompra(db.Model):
    __tablename__ = "orden_compra"
    __table_args__ = (
        UniqueConstraint("organizacion_id", "numero", name="uq_orden_compra_tenant_numero"),
        CheckConstraint(
            "estado IN ('borrador', 'en_revision', 'aprobada', 'cancelada', 'cerrada')",
            name="ck_orden_compra_estado",
        ),
        CheckConstraint("total_centavos >= 0", name="ck_orden_compra_total"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    proveedor_id = db.Column(db.Integer, db.ForeignKey("proveedor_compra.id"), nullable=False, index=True)
    numero = db.Column(db.String(80), nullable=False)
    moneda = db.Column(db.String(3), default="ARS", nullable=False)
    estado = db.Column(db.String(20), default="borrador", nullable=False, index=True)
    total_centavos = db.Column(db.BigInteger, default=0, nullable=False)
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_actualizacion = db.Column(db.DateTime, default=ahora_utc_naive, onupdate=ahora_utc_naive, nullable=False)
    proveedor = db.relationship("ProveedorCompra", backref="ordenes")
    unidad_negocio = db.relationship("UnidadNegocio")
    items = db.relationship("OrdenCompraItem", back_populates="orden", cascade="all, delete-orphan", order_by="OrdenCompraItem.id")


class OrdenCompraItem(db.Model):
    __tablename__ = "orden_compra_item"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_orden_compra_item_cantidad"),
        CheckConstraint("precio_unitario_centavos >= 0 AND subtotal_centavos >= 0", name="ck_orden_compra_item_importes"),
    )
    id = db.Column(db.Integer, primary_key=True)
    orden_compra_id = db.Column(db.Integer, db.ForeignKey("orden_compra.id"), nullable=False, index=True)
    insumo_id = db.Column(db.Integer, db.ForeignKey("insumo_productivo.id"), index=True)
    descripcion = db.Column(db.String(250), nullable=False)
    unidad_medida = db.Column(db.String(30), nullable=False)
    cantidad = db.Column(db.Numeric(18, 6), nullable=False)
    precio_unitario_centavos = db.Column(db.BigInteger, nullable=False)
    subtotal_centavos = db.Column(db.BigInteger, nullable=False)
    orden = db.relationship("OrdenCompra", back_populates="items")
    insumo = db.relationship("InsumoProductivo")


class RecepcionCompra(db.Model):
    __tablename__ = "recepcion_compra"
    __table_args__ = (
        UniqueConstraint("organizacion_id", "numero", name="uq_recepcion_compra_tenant_numero"),
        CheckConstraint("estado IN ('preparatoria', 'revisada', 'anulada')", name="ck_recepcion_compra_estado"),
        CheckConstraint("impacta_stock = false AND impacta_costos = false", name="ck_recepcion_compra_sin_impacto"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    orden_compra_id = db.Column(db.Integer, db.ForeignKey("orden_compra.id"), nullable=False, index=True)
    numero = db.Column(db.String(80), nullable=False)
    estado = db.Column(db.String(20), default="preparatoria", nullable=False, index=True)
    comprobante_referencia = db.Column(db.String(160))
    impacta_stock = db.Column(db.Boolean, default=False, nullable=False)
    impacta_costos = db.Column(db.Boolean, default=False, nullable=False)
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    orden = db.relationship("OrdenCompra", backref="recepciones")
    items = db.relationship("RecepcionCompraItem", back_populates="recepcion", cascade="all, delete-orphan", order_by="RecepcionCompraItem.id")


class RecepcionCompraItem(db.Model):
    __tablename__ = "recepcion_compra_item"
    __table_args__ = (
        CheckConstraint("cantidad_recibida > 0", name="ck_recepcion_compra_item_cantidad"),
    )
    id = db.Column(db.Integer, primary_key=True)
    recepcion_compra_id = db.Column(db.Integer, db.ForeignKey("recepcion_compra.id"), nullable=False, index=True)
    orden_compra_item_id = db.Column(db.Integer, db.ForeignKey("orden_compra_item.id"), nullable=False, index=True)
    cantidad_recibida = db.Column(db.Numeric(18, 6), nullable=False)
    recepcion = db.relationship("RecepcionCompra", back_populates="items")
    orden_item = db.relationship("OrdenCompraItem")


class PropuestaImpactoCompra(db.Model):
    """Efecto futuro sugerido; nunca ejecuta inventario, costos o pagos."""

    __tablename__ = "propuesta_impacto_compra"
    __table_args__ = (
        UniqueConstraint("organizacion_id", "clave_idempotencia", name="uq_propuesta_compra_tenant_clave"),
        CheckConstraint("tipo IN ('stock', 'costo', 'cuenta_pagar')", name="ck_propuesta_compra_tipo"),
        CheckConstraint("estado IN ('preparada', 'aprobada', 'rechazada', 'bloqueada', 'archivada')", name="ck_propuesta_compra_estado"),
        CheckConstraint("ejecutada = false", name="ck_propuesta_compra_no_ejecutada"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    recepcion_compra_id = db.Column(db.Integer, db.ForeignKey("recepcion_compra.id"), nullable=False, index=True)
    recepcion_item_id = db.Column(db.Integer, db.ForeignKey("recepcion_compra_item.id"), index=True)
    tipo = db.Column(db.String(30), nullable=False, index=True)
    clave_idempotencia = db.Column(db.String(180), nullable=False)
    estado = db.Column(db.String(30), default="preparada", nullable=False, index=True)
    detalle_json = db.Column(db.Text, nullable=False)
    ejecutada = db.Column(db.Boolean, default=False, nullable=False)
    motivo_decision = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    decidido_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_decision = db.Column(db.DateTime)
    recepcion = db.relationship("RecepcionCompra", backref="propuestas_impacto")
    recepcion_item = db.relationship("RecepcionCompraItem")
