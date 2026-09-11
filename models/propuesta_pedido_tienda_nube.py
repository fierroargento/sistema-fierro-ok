"""Propuestas internas previas a incorporar pedidos Tienda Nube."""
from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from extensions import db
from services.fechas import ahora_utc_naive

class PropuestaPedidoTiendaNube(db.Model):
    __tablename__="propuesta_pedido_tienda_nube"
    __table_args__=(UniqueConstraint("organizacion_id","unidad_negocio_id","tienda_nube_cuenta_id","tn_order_id",name="uq_propuesta_pedido_tn_identidad"),CheckConstraint("estado IN ('preparada','aprobada','rechazada','archivada')",name="ck_propuesta_pedido_tn_estado"),CheckConstraint("puede_crear_pedido = false",name="ck_propuesta_pedido_tn_sin_creacion"),Index("ix_propuesta_pedido_tn_bandeja","organizacion_id","unidad_negocio_id","estado"))
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey("organizacion.id"),nullable=False,index=True)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey("unidad_negocio.id"),nullable=False,index=True)
    tienda_nube_cuenta_id=db.Column(db.Integer,db.ForeignKey("tienda_nube_cuenta.id"),nullable=False,index=True)
    lote_diagnostico_id=db.Column(db.Integer,db.ForeignKey("lote_diagnostico_tienda_nube.id"),nullable=False,index=True)
    tn_order_id=db.Column(db.String(50),nullable=False,index=True)
    tn_order_number=db.Column(db.String(50))
    snapshot_json=db.Column(db.Text,nullable=False)
    firma_plan=db.Column(db.String(64),nullable=False,index=True)
    estado=db.Column(db.String(20),default="preparada",nullable=False,index=True)
    puede_crear_pedido=db.Column(db.Boolean,default=False,nullable=False)
    motivo=db.Column(db.String(500))
    creado_por_usuario_id=db.Column(db.Integer,db.ForeignKey("usuario_sistema.id"),index=True)
    creado_por_username=db.Column(db.String(80))
    decidido_por_usuario_id=db.Column(db.Integer,db.ForeignKey("usuario_sistema.id"),index=True)
    decidido_por_username=db.Column(db.String(80))
    fecha_creacion=db.Column(db.DateTime,default=ahora_utc_naive,nullable=False)
    fecha_decision=db.Column(db.DateTime)

class EventoPropuestaPedidoTiendaNube(db.Model):
    __tablename__="evento_propuesta_pedido_tienda_nube"
    id=db.Column(db.Integer,primary_key=True)
    organizacion_id=db.Column(db.Integer,db.ForeignKey("organizacion.id"),nullable=False,index=True)
    unidad_negocio_id=db.Column(db.Integer,db.ForeignKey("unidad_negocio.id"),nullable=False,index=True)
    propuesta_id=db.Column(db.Integer,db.ForeignKey("propuesta_pedido_tienda_nube.id"),nullable=False,index=True)
    estado_anterior=db.Column(db.String(20));estado_nuevo=db.Column(db.String(20),nullable=False)
    motivo=db.Column(db.String(500));username=db.Column(db.String(80))
    fecha_evento=db.Column(db.DateTime,default=ahora_utc_naive,nullable=False)
    propuesta=db.relationship("PropuestaPedidoTiendaNube",backref="eventos")
