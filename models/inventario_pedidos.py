"""Configuración y bitácora del futuro ciclo automático pedido-inventario."""

from sqlalchemy import UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class ConfiguracionInventarioPedidos(db.Model):
    __tablename__ = "configuracion_inventario_pedidos"
    __table_args__ = (
        UniqueConstraint(
            "organizacion_id",
            name="uq_configuracion_inventario_pedidos_organizacion",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True,
    )
    sucursal_operativa_id = db.Column(
        db.Integer, db.ForeignKey("sucursal_operativa.id"), index=True,
    )
    estado = db.Column(
        db.String(20), default="desactivado", nullable=False, index=True,
    )
    reservar_al_ingresar = db.Column(db.Boolean, default=True, nullable=False)
    consumir_al_despachar = db.Column(db.Boolean, default=True, nullable=False)
    liberar_al_cancelar = db.Column(db.Boolean, default=True, nullable=False)
    permitir_stock_negativo = db.Column(db.Boolean, default=False, nullable=False)
    fecha_ultima_validacion = db.Column(db.DateTime)
    detalle_validacion = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_actualizacion = db.Column(
        db.DateTime, default=ahora_utc_naive, onupdate=ahora_utc_naive,
    )

    sucursal = db.relationship("SucursalOperativa")


class EventoInventarioPedido(db.Model):
    """Evento idempotente: nunca permite procesar dos veces el mismo hecho."""

    __tablename__ = "evento_inventario_pedido"
    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "clave_idempotencia",
            name="uq_evento_inventario_pedido_organizacion_clave",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True,
    )
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedido.id"), index=True)
    tipo_evento = db.Column(db.String(30), nullable=False, index=True)
    clave_idempotencia = db.Column(db.String(200), nullable=False)
    estado = db.Column(db.String(20), default="pendiente", nullable=False, index=True)
    detalle = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_procesamiento = db.Column(db.DateTime)
