"""Propuestas auditables para asignar identidad SaaS a pedidos legacy."""

from sqlalchemy import CheckConstraint, Index

from extensions import db
from services.fechas import ahora_utc_naive


class AsignacionTenantPedido(db.Model):
    __tablename__ = "asignacion_tenant_pedido"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('preparada', 'aprobada', 'aplicada', 'rechazada', 'obsoleta')",
            name="ck_asignacion_tenant_pedido_estado",
        ),
        Index(
            "ix_asignacion_tenant_pedido_bandeja",
            "organizacion_id", "estado", "fecha_creacion",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(
        db.Integer, db.ForeignKey("pedido.id"), nullable=False, index=True,
    )
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True,
    )
    unidad_negocio_id = db.Column(
        db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True,
    )
    estado = db.Column(db.String(20), nullable=False, default="preparada", index=True)
    ml_cuenta_id_snapshot = db.Column(db.Integer)
    tn_cuenta_id_snapshot = db.Column(db.Integer)
    motivo = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    creado_por_username = db.Column(db.String(80))
    aprobado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    aprobado_por_username = db.Column(db.String(80))
    rechazado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    rechazado_por_username = db.Column(db.String(80))
    aplicado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    aplicado_por_username = db.Column(db.String(80))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_aprobacion = db.Column(db.DateTime)
    fecha_rechazo = db.Column(db.DateTime)
    fecha_aplicacion = db.Column(db.DateTime)

    pedido = db.relationship("Pedido")
    organizacion = db.relationship("Organizacion")
    unidad_negocio = db.relationship("UnidadNegocio")
