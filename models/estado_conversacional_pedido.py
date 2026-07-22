"""
Modelo de estado conversacional y ownership de pedidos.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class EstadoConversacionalPedido(db.Model):
    """
    Estado conversacional APB asociado a un pedido.

    Convive con los indicadores legacy durante la migración.
    """

    __tablename__ = "estado_conversacional_pedido"

    id = db.Column(db.Integer, primary_key=True)

    pedido_id = db.Column(
        db.Integer,
        db.ForeignKey("pedido.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    owner_actual = db.Column(
        db.String(30),
        default="bot",
        index=True,
    )
    estado_conversacional = db.Column(
        db.String(80),
        default="recolectando_datos",
        index=True,
    )

    canal_activo = db.Column(
        db.String(30),
        default="ml",
    )
    flujo_base = db.Column(db.String(80))

    takeover_activo = db.Column(
        db.Boolean,
        default=False,
    )
    bot_pausado = db.Column(
        db.Boolean,
        default=False,
    )
    cross_sell_activo = db.Column(
        db.Boolean,
        default=False,
    )

    ultima_interaccion = db.Column(db.DateTime)
    ultimo_mensaje_cliente = db.Column(db.DateTime)
    ultimo_mensaje_bot = db.Column(db.DateTime)

    fecha_creacion = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        index=True,
    )
    fecha_actualizacion = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
        onupdate=ahora_utc_naive,
        index=True,
    )
