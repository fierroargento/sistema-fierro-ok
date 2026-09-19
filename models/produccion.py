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


class ParteProduccion(db.Model):
    """Avance declarado para ensayo; no genera consumos ni producto terminado."""

    __tablename__ = "parte_produccion"
    __table_args__ = (
        UniqueConstraint("organizacion_id", "numero", name="uq_parte_produccion_tenant_numero"),
        CheckConstraint("cantidad_buena >= 0 AND cantidad_rechazada >= 0", name="ck_parte_cantidades"),
        CheckConstraint("cantidad_buena + cantidad_rechazada > 0", name="ck_parte_avance_positivo"),
        CheckConstraint("minutos_reales >= 0", name="ck_parte_minutos"),
        CheckConstraint(
            "impacta_inventario = false AND consume_insumos = false AND crea_producto_terminado = false",
            name="ck_parte_sin_impacto",
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    orden_produccion_id = db.Column(db.Integer, db.ForeignKey("orden_produccion.id"), nullable=False, index=True)
    numero = db.Column(db.String(80), nullable=False)
    cantidad_buena = db.Column(db.Numeric(18, 6), default=0, nullable=False)
    cantidad_rechazada = db.Column(db.Numeric(18, 6), default=0, nullable=False)
    minutos_reales = db.Column(db.Numeric(18, 4), default=0, nullable=False)
    estado = db.Column(db.String(20), default="informado", nullable=False)
    impacta_inventario = db.Column(db.Boolean, default=False, nullable=False)
    consume_insumos = db.Column(db.Boolean, default=False, nullable=False)
    crea_producto_terminado = db.Column(db.Boolean, default=False, nullable=False)
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    orden = db.relationship("OrdenProduccion", backref="partes_informados")


class LoteProduccion(db.Model):
    """Lote trazable nacido de un parte, siempre retenido fuera del inventario."""

    __tablename__ = "lote_produccion"
    __table_args__ = (
        UniqueConstraint("organizacion_id", "codigo", name="uq_lote_produccion_tenant_codigo"),
        CheckConstraint("cantidad > 0", name="ck_lote_produccion_cantidad"),
        CheckConstraint(
            "estado IN ('cuarentena', 'en_control', 'aprobado_interno', 'rechazado_interno')",
            name="ck_lote_produccion_estado",
        ),
        CheckConstraint(
            "liberado_inventario = false AND movimiento_creado = false",
            name="ck_lote_produccion_sin_impacto",
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    orden_produccion_id = db.Column(db.Integer, db.ForeignKey("orden_produccion.id"), nullable=False, index=True)
    parte_produccion_id = db.Column(db.Integer, db.ForeignKey("parte_produccion.id"), nullable=False, index=True)
    codigo = db.Column(db.String(100), nullable=False)
    cantidad = db.Column(db.Numeric(18, 6), nullable=False)
    estado = db.Column(db.String(30), default="cuarentena", nullable=False, index=True)
    liberado_inventario = db.Column(db.Boolean, default=False, nullable=False)
    movimiento_creado = db.Column(db.Boolean, default=False, nullable=False)
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    orden = db.relationship("OrdenProduccion", backref="lotes_preparatorios")
    parte = db.relationship("ParteProduccion", backref="lotes_preparatorios")


class ControlCalidadProduccion(db.Model):
    """Inspeccion interna de un lote sin liberarlo al inventario."""

    __tablename__ = "control_calidad_produccion"
    __table_args__ = (
        UniqueConstraint("organizacion_id", "numero", name="uq_control_calidad_tenant_numero"),
        CheckConstraint("muestra > 0", name="ck_control_calidad_muestra"),
        CheckConstraint("aprobadas >= 0 AND rechazadas >= 0", name="ck_control_calidad_resultados"),
        CheckConstraint("aprobadas + rechazadas = muestra", name="ck_control_calidad_balance"),
        CheckConstraint(
            "resultado IN ('aprobado_interno', 'rechazado_interno')",
            name="ck_control_calidad_resultado",
        ),
        CheckConstraint("libera_stock = false", name="ck_control_calidad_sin_liberacion"),
    )
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True)
    unidad_negocio_id = db.Column(db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True)
    lote_produccion_id = db.Column(db.Integer, db.ForeignKey("lote_produccion.id"), nullable=False, index=True)
    numero = db.Column(db.String(100), nullable=False)
    muestra = db.Column(db.Numeric(18, 6), nullable=False)
    aprobadas = db.Column(db.Numeric(18, 6), nullable=False)
    rechazadas = db.Column(db.Numeric(18, 6), nullable=False)
    resultado = db.Column(db.String(30), nullable=False, index=True)
    libera_stock = db.Column(db.Boolean, default=False, nullable=False)
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuario_sistema.id"))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    lote = db.relationship("LoteProduccion", backref="controles_calidad")
