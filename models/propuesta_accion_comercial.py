"""Cola auditable de acciones comerciales internas, sin ejecutor de canal."""

from sqlalchemy import CheckConstraint, UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class PropuestaAccionComercial(db.Model):
    __tablename__ = "propuesta_accion_comercial"
    __table_args__ = (
        UniqueConstraint("organizacion_id", "clave_idempotencia", name="uq_propuesta_accion_comercial_clave"),
        CheckConstraint("tipo_accion IN ('cancelar_promocion', 'actualizar_precio')", name="ck_propuesta_accion_tipo"),
        CheckConstraint(
            "estado IN ('preparada', 'aprobada', 'rechazada', 'archivada', 'completada_manual')",
            name="ck_propuesta_accion_estado",
        ),
        CheckConstraint("puede_ejecutar = false", name="ck_propuesta_accion_sin_ejecucion"),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    lista_precio_id = db.Column(db.Integer, db.ForeignKey("lista_precio.id"), nullable=False, index=True)
    catalogo_producto_id = db.Column(db.Integer, db.ForeignKey("catalogo_producto.id"), nullable=False, index=True)
    promocion_observacion_id = db.Column(db.Integer, db.ForeignKey("promocion_canal_observacion.id"), index=True)
    depende_de_id = db.Column(db.Integer, db.ForeignKey("propuesta_accion_comercial.id"), index=True)
    tipo_accion = db.Column(db.String(30), nullable=False, index=True)
    orden = db.Column(db.Integer, nullable=False)
    precio_actual_centavos = db.Column(db.BigInteger)
    precio_propuesto_centavos = db.Column(db.BigInteger)
    clave_idempotencia = db.Column(db.String(64), nullable=False)
    huella_calculo = db.Column(db.String(64), nullable=False, index=True)
    snapshot_json = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(30), default="preparada", nullable=False, index=True)
    puede_ejecutar = db.Column(db.Boolean, default=False, nullable=False)
    motivo_decision = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    creado_por_username = db.Column(db.String(80))
    decidido_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"), index=True)
    decidido_por_username = db.Column(db.String(80))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_decision = db.Column(db.DateTime)
    fecha_actualizacion = db.Column(db.DateTime, default=ahora_utc_naive, onupdate=ahora_utc_naive)

    lista_precio = db.relationship("ListaPrecio")
    catalogo_producto = db.relationship("CatalogoProducto")
    promocion_observacion = db.relationship("PromocionCanalObservacion")
    depende_de = db.relationship("PropuestaAccionComercial", remote_side=[id])
