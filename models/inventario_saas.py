"""Entidades auditables para inventario SaaS multideposito."""

from sqlalchemy import UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class ItemInventario(db.Model):
    """SKU estable: producto principal, variante o insumo inventariable."""

    __tablename__ = "item_inventario"
    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "sku",
            name="uq_item_inventario_organizacion_sku",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True,
    )
    producto_id = db.Column(
        db.Integer, db.ForeignKey("producto.id"), nullable=False, index=True,
    )
    catalogo_producto_id = db.Column(
        db.Integer, db.ForeignKey("catalogo_producto.id"), index=True,
    )
    sku = db.Column(db.String(100), nullable=False, index=True)
    nombre = db.Column(db.String(220), nullable=False)
    tipo = db.Column(db.String(30), default="producto", nullable=False)
    atributos_json = db.Column(db.Text)
    activo = db.Column(db.Boolean, default=False, nullable=False, index=True)
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive)
    fecha_actualizacion = db.Column(
        db.DateTime, default=ahora_utc_naive, onupdate=ahora_utc_naive,
    )


class ReservaInventario(db.Model):
    """Reserva individual identificable por pedido, canal u operación interna."""

    __tablename__ = "reserva_inventario"
    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "clave_idempotencia",
            name="uq_reserva_inventario_organizacion_clave",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True,
    )
    existencia_sucursal_id = db.Column(
        db.Integer, db.ForeignKey("existencia_sucursal.id"), nullable=False, index=True,
    )
    canal = db.Column(db.String(50), nullable=False, index=True)
    referencia_externa = db.Column(db.String(150), index=True)
    clave_idempotencia = db.Column(db.String(180), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    estado = db.Column(db.String(30), default="activa", nullable=False, index=True)
    vence_en = db.Column(db.DateTime, index=True)
    motivo = db.Column(db.String(300))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_cierre = db.Column(db.DateTime)

    existencia = db.relationship("ExistenciaSucursal", backref="reservas_detalladas")


class TransferenciaInventario(db.Model):
    """Traslado de un SKU entre dos ubicaciones con recepción parcial."""

    __tablename__ = "transferencia_inventario"
    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "codigo",
            name="uq_transferencia_inventario_organizacion_codigo",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True,
    )
    codigo = db.Column(db.String(100), nullable=False, index=True)
    existencia_origen_id = db.Column(
        db.Integer, db.ForeignKey("existencia_sucursal.id"), nullable=False, index=True,
    )
    existencia_destino_id = db.Column(
        db.Integer, db.ForeignKey("existencia_sucursal.id"), nullable=False, index=True,
    )
    cantidad_solicitada = db.Column(db.Integer, nullable=False)
    cantidad_despachada = db.Column(db.Integer, default=0, nullable=False)
    cantidad_recibida = db.Column(db.Integer, default=0, nullable=False)
    estado = db.Column(db.String(30), default="borrador", nullable=False, index=True)
    motivo = db.Column(db.String(300), nullable=False)
    usuario_solicita = db.Column(db.String(100))
    usuario_despacha = db.Column(db.String(100))
    usuario_recibe = db.Column(db.String(100))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_despacho = db.Column(db.DateTime)
    fecha_recepcion = db.Column(db.DateTime)

    origen = db.relationship("ExistenciaSucursal", foreign_keys=[existencia_origen_id])
    destino = db.relationship("ExistenciaSucursal", foreign_keys=[existencia_destino_id])


class ConteoInventario(db.Model):
    """Cabecera de inventario físico que no ajusta hasta ser conciliado."""

    __tablename__ = "conteo_inventario"
    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "codigo",
            name="uq_conteo_inventario_organizacion_codigo",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True,
    )
    sucursal_operativa_id = db.Column(
        db.Integer, db.ForeignKey("sucursal_operativa.id"), nullable=False, index=True,
    )
    codigo = db.Column(db.String(100), nullable=False, index=True)
    estado = db.Column(db.String(30), default="borrador", nullable=False, index=True)
    observacion = db.Column(db.String(300))
    usuario_inicia = db.Column(db.String(100))
    usuario_concilia = db.Column(db.String(100))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_conciliacion = db.Column(db.DateTime)

    sucursal = db.relationship("SucursalOperativa", backref="conteos_inventario")


class ConteoInventarioItem(db.Model):
    """Fotografía esperada, cantidad contada y diferencia por existencia."""

    __tablename__ = "conteo_inventario_item"
    __table_args__ = (
        UniqueConstraint(
            "conteo_inventario_id", "existencia_sucursal_id",
            name="uq_conteo_inventario_existencia",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    conteo_inventario_id = db.Column(
        db.Integer, db.ForeignKey("conteo_inventario.id"), nullable=False, index=True,
    )
    existencia_sucursal_id = db.Column(
        db.Integer, db.ForeignKey("existencia_sucursal.id"), nullable=False, index=True,
    )
    cantidad_esperada = db.Column(db.Integer, nullable=False)
    cantidad_contada = db.Column(db.Integer)
    diferencia = db.Column(db.Integer)
    observacion = db.Column(db.String(300))

    conteo = db.relationship("ConteoInventario", backref="items")
    existencia = db.relationship("ExistenciaSucursal", backref="items_conteo")
