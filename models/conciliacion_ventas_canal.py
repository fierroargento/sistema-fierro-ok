"""Ventas y movimientos financieros observados para conciliacion multicanal."""

from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class VentaCanalItem(db.Model):
    __tablename__ = "venta_canal_item"
    __table_args__ = (
        UniqueConstraint("organizacion_id", "cuenta_codigo", "referencia_venta", "referencia_item", name="uq_venta_canal_item_identidad"),
        CheckConstraint("cantidad > 0 AND precio_unitario_centavos >= 0", name="ck_venta_canal_item_importes"),
        CheckConstraint("estado IN ('confirmada', 'cancelada', 'devuelta', 'devolucion_parcial')", name="ck_venta_canal_item_estado"),
        Index("ix_venta_canal_pago", "organizacion_id", "cuenta_codigo", "referencia_pago"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    lista_precio_id = db.Column(db.Integer, db.ForeignKey("lista_precio.id"), nullable=False, index=True)
    catalogo_producto_id = db.Column(db.Integer, db.ForeignKey("catalogo_producto.id"), nullable=False, index=True)
    cuenta_codigo = db.Column(db.String(100), nullable=False, index=True)
    referencia_venta = db.Column(db.String(160), nullable=False, index=True)
    referencia_item = db.Column(db.String(160), nullable=False)
    referencia_pago = db.Column(db.String(160), index=True)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario_centavos = db.Column(db.BigInteger, nullable=False)
    importe_bruto_centavos = db.Column(db.BigInteger, nullable=False)
    comision_esperada_centavos = db.Column(db.BigInteger, default=0, nullable=False)
    cargo_fijo_esperado_centavos = db.Column(db.BigInteger, default=0, nullable=False)
    envio_esperado_centavos = db.Column(db.BigInteger, default=0, nullable=False)
    liquidacion_esperada_centavos = db.Column(db.BigInteger, nullable=False)
    costo_unitario_snapshot_centavos = db.Column(db.BigInteger)
    piso_unitario_snapshot_centavos = db.Column(db.BigInteger)
    estado = db.Column(db.String(30), default="confirmada", nullable=False, index=True)
    fecha_venta = db.Column(db.DateTime, nullable=False, index=True)
    origen = db.Column(db.String(20), default="manual", nullable=False)
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    creado_por_username = db.Column(db.String(80))
    fecha_registro = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    lista_precio = db.relationship("ListaPrecio")
    catalogo_producto = db.relationship("CatalogoProducto")


class MovimientoLiquidacionCanal(db.Model):
    __tablename__ = "movimiento_liquidacion_canal"
    __table_args__ = (
        UniqueConstraint("organizacion_id", "cuenta_codigo", "referencia_movimiento", name="uq_movimiento_liquidacion_identidad"),
        CheckConstraint("direccion IN ('credito', 'debito')", name="ck_movimiento_liquidacion_direccion"),
        CheckConstraint("importe_centavos >= 0", name="ck_movimiento_liquidacion_importe"),
        CheckConstraint("tipo IN ('pago_bruto', 'liquidacion_neta', 'comision', 'cargo_fijo', 'envio', 'impuesto', 'retencion', 'devolucion', 'ajuste')", name="ck_movimiento_liquidacion_tipo"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    cuenta_codigo = db.Column(db.String(100), nullable=False, index=True)
    referencia_venta = db.Column(db.String(160), nullable=False, index=True)
    referencia_pago = db.Column(db.String(160), index=True)
    referencia_movimiento = db.Column(db.String(160), nullable=False, index=True)
    tipo = db.Column(db.String(30), nullable=False, index=True)
    direccion = db.Column(db.String(10), nullable=False)
    importe_centavos = db.Column(db.BigInteger, nullable=False)
    impacta_saldo = db.Column(db.Boolean, default=True, nullable=False)
    estado = db.Column(db.String(30), default="confirmado", nullable=False, index=True)
    fecha_movimiento = db.Column(db.DateTime, nullable=False, index=True)
    origen = db.Column(db.String(20), default="manual", nullable=False)
    detalle = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    creado_por_username = db.Column(db.String(80))
    fecha_registro = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
