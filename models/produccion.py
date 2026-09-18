"""Órdenes preparatorias de producción sin consumos ni altas de stock."""

from sqlalchemy import CheckConstraint, UniqueConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class OrdenProduccion(db.Model):
    __tablename__ = "orden_produccion"
    __table_args__ = (
        UniqueConstraint("organizacion_id", "numero", name="uq_orden_produccion_tenant_numero"),
        CheckConstraint("cantidad_planificada > 0", name="ck_orden_produccion_cantidad"),
        CheckConstraint("costo_planificado_centavos >= 0", name="ck_orden_produccion_costo"),
        CheckConstraint(
            "estado IN ('borrador', 'en_revision', 'aprobada', 'cancelada', 'cerrada')",
            name="ck_orden_produccion_estado",
        ),
        CheckConstraint(
            "impacta_inventario = false AND ejecucion_habilitada = false",
            name="ck_orden_produccion_bloqueada",
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    perfil_costeo_id = db.Column(db.Integer, db.ForeignKey("perfil_costeo_producto.id"), nullable=False, index=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False, index=True)
    numero = db.Column(db.String(80), nullable=False)
    cantidad_planificada = db.Column(db.Numeric(18, 6), nullable=False)
    estado = db.Column(db.String(20), default="borrador", nullable=False, index=True)
    costo_unitario_centavos = db.Column(db.BigInteger, default=0, nullable=False)
    costo_planificado_centavos = db.Column(db.BigInteger, default=0, nullable=False)
    version_costo_id = db.Column(db.Integer, db.ForeignKey("costo_producto_version.id"), index=True)
    impacta_inventario = db.Column(db.Boolean, default=False, nullable=False)
    ejecucion_habilitada = db.Column(db.Boolean, default=False, nullable=False)
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    perfil = db.relationship("PerfilCosteoProducto")
    producto = db.relationship("Producto")
    version_costo = db.relationship("CostoProductoVersion")


class OrdenProduccionInsumo(db.Model):
    __tablename__ = "orden_produccion_insumo"
    __table_args__ = (CheckConstraint("cantidad_planificada > 0", name="ck_op_insumo_cantidad"),)
    id = db.Column(db.Integer, primary_key=True)
    orden_produccion_id = db.Column(db.Integer, db.ForeignKey("orden_produccion.id"), nullable=False, index=True)
    insumo_id = db.Column(db.Integer, db.ForeignKey("insumo_productivo.id"), nullable=False, index=True)
    cantidad_planificada = db.Column(db.Numeric(18, 6), nullable=False)
    porcentaje_merma = db.Column(db.Numeric(9, 6), default=0, nullable=False)
    consumo_registrado = db.Column(db.Boolean, default=False, nullable=False)
    insumo = db.relationship("InsumoProductivo")
    orden = db.relationship("OrdenProduccion", backref=db.backref("insumos_planificados", cascade="all, delete-orphan"))


class OrdenProduccionOperacion(db.Model):
    __tablename__ = "orden_produccion_operacion"
    __table_args__ = (CheckConstraint("minutos_planificados > 0", name="ck_op_operacion_minutos"),)
    id = db.Column(db.Integer, primary_key=True)
    orden_produccion_id = db.Column(db.Integer, db.ForeignKey("orden_produccion.id"), nullable=False, index=True)
    empleado_id = db.Column(db.Integer, db.ForeignKey("empleado_productivo.id"), nullable=False, index=True)
    nombre = db.Column(db.String(160), nullable=False)
    minutos_planificados = db.Column(db.Numeric(18, 4), nullable=False)
    avance_registrado = db.Column(db.Boolean, default=False, nullable=False)
    empleado = db.relationship("EmpleadoProductivo")
    orden = db.relationship("OrdenProduccion", backref=db.backref("operaciones_planificadas", cascade="all, delete-orphan"))


class OrdenProduccionMaquina(db.Model):
    __tablename__ = "orden_produccion_maquina"
    __table_args__ = (CheckConstraint("minutos_planificados > 0", name="ck_op_maquina_minutos"),)
    id = db.Column(db.Integer, primary_key=True)
    orden_produccion_id = db.Column(db.Integer, db.ForeignKey("orden_produccion.id"), nullable=False, index=True)
    maquina_id = db.Column(db.Integer, db.ForeignKey("maquina_productiva.id"), nullable=False, index=True)
    nombre = db.Column(db.String(160), nullable=False)
    minutos_planificados = db.Column(db.Numeric(18, 4), nullable=False)
    uso_registrado = db.Column(db.Boolean, default=False, nullable=False)
    maquina = db.relationship("MaquinaProductiva")
    orden = db.relationship("OrdenProduccion", backref=db.backref("maquinas_planificadas", cascade="all, delete-orphan"))
