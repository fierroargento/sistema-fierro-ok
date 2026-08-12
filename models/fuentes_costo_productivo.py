"""Fuentes historicas utilizadas para construir costos productivos."""

from sqlalchemy import CheckConstraint
from sqlalchemy import Index
from sqlalchemy import UniqueConstraint
from sqlalchemy import text

from extensions import db
from services.fechas import ahora_utc_naive


class InsumoProductivo(db.Model):
    """Materia prima, consumible o servicio incorporado a produccion."""

    __tablename__ = "insumo_productivo"
    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "codigo",
            name="uq_insumo_productivo_organizacion_codigo",
        ),
        CheckConstraint(
            "tipo IN ('materia_prima', 'consumible', 'servicio_productivo', "
            "'embalaje_productivo')",
            name="ck_insumo_productivo_tipo",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True,
    )
    unidad_negocio_id = db.Column(
        db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=True, index=True,
    )
    codigo = db.Column(db.String(80), nullable=False, index=True)
    nombre = db.Column(db.String(200), nullable=False, index=True)
    tipo = db.Column(db.String(30), nullable=False, index=True)
    unidad_medida = db.Column(db.String(30), nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False, index=True)
    observacion = db.Column(db.String(500))
    fecha_creacion = db.Column(
        db.DateTime, default=ahora_utc_naive, nullable=False,
    )

    unidad_negocio = db.relationship("UnidadNegocio")


class InsumoPrecioVersion(db.Model):
    """Precio historico normalizado por unidad de un insumo."""

    __tablename__ = "insumo_precio_version"
    __table_args__ = (
        CheckConstraint(
            "precio_unitario_centavos >= 0",
            name="ck_insumo_precio_no_negativo",
        ),
        CheckConstraint(
            "numero_version > 0",
            name="ck_insumo_precio_version_positiva",
        ),
        Index(
            "uq_insumo_precio_numero", "insumo_id", "moneda", "numero_version",
            unique=True,
        ),
        Index(
            "uq_insumo_precio_vigente", "insumo_id", "moneda",
            unique=True,
            postgresql_where=text("vigente IS TRUE"),
            sqlite_where=text("vigente IS TRUE"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    insumo_id = db.Column(
        db.Integer, db.ForeignKey("insumo_productivo.id"), nullable=False,
        index=True,
    )
    moneda = db.Column(db.String(3), default="ARS", nullable=False, index=True)
    numero_version = db.Column(db.Integer, nullable=False)
    precio_unitario_centavos = db.Column(db.BigInteger, nullable=False)
    vigente = db.Column(db.Boolean, default=True, nullable=False, index=True)
    vigente_desde = db.Column(db.DateTime, nullable=False, index=True)
    vigente_hasta = db.Column(db.DateTime)
    proveedor_referencia = db.Column(db.String(200))
    comprobante_referencia = db.Column(db.String(120))
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuario_sistema.id"), nullable=True,
    )
    fecha_creacion = db.Column(
        db.DateTime, default=ahora_utc_naive, nullable=False,
    )

    insumo = db.relationship("InsumoProductivo", backref="versiones_precio")


class EmpleadoProductivo(db.Model):
    """Empleado o recurso laboral cuya tarifa puede aplicarse a productos."""

    __tablename__ = "empleado_productivo"
    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "codigo",
            name="uq_empleado_productivo_organizacion_codigo",
        ),
        CheckConstraint(
            "tipo_registro IN ('empleado', 'recurso')",
            name="ck_empleado_productivo_tipo_registro",
        ),
        CheckConstraint(
            "porcentaje_indirecto >= 0 AND porcentaje_indirecto <= 100",
            name="ck_empleado_productivo_indirecto",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True,
    )
    unidad_negocio_id = db.Column(
        db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=True, index=True,
    )
    codigo = db.Column(db.String(80), nullable=False, index=True)
    nombre = db.Column(db.String(200), nullable=False, index=True)
    sector = db.Column(db.String(120), nullable=False, index=True)
    puesto = db.Column(db.String(120))
    tipo_registro = db.Column(
        db.String(20), default="empleado", nullable=False, index=True,
    )
    porcentaje_indirecto = db.Column(
        db.Numeric(9, 4), default=0, nullable=False,
    )
    activo = db.Column(db.Boolean, default=True, nullable=False, index=True)
    observacion = db.Column(db.String(500))
    fecha_creacion = db.Column(
        db.DateTime, default=ahora_utc_naive, nullable=False,
    )

    unidad_negocio = db.relationship("UnidadNegocio")


class RecursoEmpleadoProductivo(db.Model):
    """Participacion de un empleado en la tarifa ponderada de un recurso."""

    __tablename__ = "recurso_empleado_productivo"
    __table_args__ = (
        UniqueConstraint(
            "recurso_id", "empleado_id",
            name="uq_recurso_empleado_productivo",
        ),
        CheckConstraint(
            "porcentaje_dedicacion > 0 AND porcentaje_dedicacion <= 100",
            name="ck_recurso_empleado_dedicacion",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    recurso_id = db.Column(
        db.Integer, db.ForeignKey("empleado_productivo.id"),
        nullable=False, index=True,
    )
    empleado_id = db.Column(
        db.Integer, db.ForeignKey("empleado_productivo.id"),
        nullable=False, index=True,
    )
    porcentaje_dedicacion = db.Column(
        db.Numeric(9, 4), default=100, nullable=False,
    )
    observacion = db.Column(db.String(500))
    fecha_creacion = db.Column(
        db.DateTime, default=ahora_utc_naive, nullable=False,
    )

    recurso = db.relationship(
        "EmpleadoProductivo", foreign_keys=[recurso_id],
        backref="miembros_recurso",
    )
    empleado = db.relationship(
        "EmpleadoProductivo", foreign_keys=[empleado_id],
        backref="participaciones_recurso",
    )


class EmpleadoCostoVersion(db.Model):
    """Composicion salarial historica y tarifa productiva calculada."""

    __tablename__ = "empleado_costo_version"
    __table_args__ = (
        CheckConstraint(
            "sueldo_base_centavos >= 0 AND cargas_sociales_centavos >= 0 "
            "AND adicionales_centavos >= 0 AND otros_costos_centavos >= 0",
            name="ck_empleado_costo_importes_no_negativos",
        ),
        CheckConstraint(
            "horas_mensuales > 0 AND horas_productivas > 0 "
            "AND horas_productivas <= horas_mensuales",
            name="ck_empleado_costo_horas_validas",
        ),
        CheckConstraint(
            "costo_mensual_total_centavos >= 0 "
            "AND costo_hora_productiva_centavos >= 0 "
            "AND costo_minuto_productivo_centavos >= 0",
            name="ck_empleado_costo_totales_no_negativos",
        ),
        CheckConstraint(
            "porcentaje_cargas >= 0 AND porcentaje_cargas <= 100",
            name="ck_empleado_costo_porcentaje_cargas",
        ),
        CheckConstraint(
            "porcentaje_productivo >= 0 AND porcentaje_productivo <= 100",
            name="ck_empleado_costo_porcentaje_productivo",
        ),
        CheckConstraint(
            "tipo_funcion IN ('directa', 'indirecta_productiva', "
            "'comercial_administrativa', 'mixta')",
            name="ck_empleado_costo_tipo_funcion",
        ),
        Index(
            "uq_empleado_costo_numero", "empleado_id", "moneda", "numero_version",
            unique=True,
        ),
        Index(
            "uq_empleado_costo_vigente", "empleado_id", "moneda",
            unique=True,
            postgresql_where=text("vigente IS TRUE"),
            sqlite_where=text("vigente IS TRUE"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    empleado_id = db.Column(
        db.Integer, db.ForeignKey("empleado_productivo.id"), nullable=False,
        index=True,
    )
    moneda = db.Column(db.String(3), default="ARS", nullable=False, index=True)
    numero_version = db.Column(db.Integer, nullable=False)
    sueldo_base_centavos = db.Column(db.BigInteger, nullable=False)
    cargas_sociales_centavos = db.Column(db.BigInteger, default=0, nullable=False)
    porcentaje_cargas = db.Column(db.Numeric(9, 4), default=0, nullable=False)
    usa_porcentaje_general = db.Column(db.Boolean, default=False, nullable=False)
    ubicacion_trabajo = db.Column(
        db.String(120), default="Sin definir", nullable=False,
    )
    tipo_funcion = db.Column(
        db.String(30), default="directa", nullable=False, index=True,
    )
    porcentaje_productivo = db.Column(
        db.Numeric(9, 4), default=100, nullable=False,
    )
    adicionales_centavos = db.Column(db.BigInteger, default=0, nullable=False)
    otros_costos_centavos = db.Column(db.BigInteger, default=0, nullable=False)
    horas_mensuales = db.Column(db.Numeric(12, 4), nullable=False)
    horas_productivas = db.Column(db.Numeric(12, 4), nullable=False)
    costo_mensual_total_centavos = db.Column(db.BigInteger, nullable=False)
    costo_hora_productiva_centavos = db.Column(db.BigInteger, nullable=False)
    costo_minuto_productivo_centavos = db.Column(db.BigInteger, nullable=False)
    vigente = db.Column(db.Boolean, default=True, nullable=False, index=True)
    vigente_desde = db.Column(db.DateTime, nullable=False, index=True)
    vigente_hasta = db.Column(db.DateTime)
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuario_sistema.id"), nullable=True,
    )
    fecha_creacion = db.Column(
        db.DateTime, default=ahora_utc_naive, nullable=False,
    )

    empleado = db.relationship("EmpleadoProductivo", backref="versiones_costo")


class ConfiguracionCostoLaboralVersion(db.Model):
    """Porcentaje general historico aplicado por unidad de negocio."""

    __tablename__ = "configuracion_costo_laboral_version"
    __table_args__ = (
        CheckConstraint(
            "porcentaje_cargas >= 0 AND porcentaje_cargas <= 100",
            name="ck_config_costo_laboral_porcentaje",
        ),
        Index(
            "uq_config_costo_laboral_numero", "unidad_negocio_id",
            "numero_version", unique=True,
        ),
        Index(
            "uq_config_costo_laboral_vigente", "unidad_negocio_id",
            unique=True,
            postgresql_where=text("vigente IS TRUE"),
            sqlite_where=text("vigente IS TRUE"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True,
    )
    unidad_negocio_id = db.Column(
        db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True,
    )
    numero_version = db.Column(db.Integer, nullable=False)
    porcentaje_cargas = db.Column(db.Numeric(9, 4), nullable=False)
    vigente = db.Column(db.Boolean, default=True, nullable=False, index=True)
    vigente_desde = db.Column(db.DateTime, nullable=False, index=True)
    vigente_hasta = db.Column(db.DateTime)
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuario_sistema.id"), nullable=True,
    )
    fecha_creacion = db.Column(
        db.DateTime, default=ahora_utc_naive, nullable=False,
    )

    unidad_negocio = db.relationship("UnidadNegocio")


class EmpleadoDistribucionVersion(db.Model):
    """Asignación histórica del costo laboral entre unidades de negocio."""

    __tablename__ = "empleado_distribucion_version"
    __table_args__ = (
        CheckConstraint(
            "porcentaje_asignacion > 0 AND porcentaje_asignacion <= 100",
            name="ck_empleado_distribucion_porcentaje",
        ),
        CheckConstraint(
            "tipo_funcion IN ('directa', 'indirecta_productiva', "
            "'comercial_administrativa', 'mixta')",
            name="ck_empleado_distribucion_funcion",
        ),
        UniqueConstraint(
            "empleado_id", "numero_revision", "unidad_negocio_id",
            name="uq_empleado_distribucion_revision_unidad",
        ),
        Index(
            "ix_empleado_distribucion_vigente",
            "empleado_id", "vigente",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True,
    )
    empleado_id = db.Column(
        db.Integer, db.ForeignKey("empleado_productivo.id"),
        nullable=False, index=True,
    )
    unidad_negocio_id = db.Column(
        db.Integer, db.ForeignKey("unidad_negocio.id"),
        nullable=False, index=True,
    )
    numero_revision = db.Column(db.Integer, nullable=False)
    ubicacion_trabajo = db.Column(db.String(120), nullable=False)
    tipo_funcion = db.Column(db.String(30), nullable=False, index=True)
    porcentaje_asignacion = db.Column(db.Numeric(9, 4), nullable=False)
    vigente = db.Column(db.Boolean, default=True, nullable=False, index=True)
    vigente_desde = db.Column(db.DateTime, nullable=False, index=True)
    vigente_hasta = db.Column(db.DateTime)
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuario_sistema.id"), nullable=True,
    )
    fecha_creacion = db.Column(
        db.DateTime, default=ahora_utc_naive, nullable=False,
    )

    empleado = db.relationship(
        "EmpleadoProductivo", backref="distribuciones_versionadas",
    )
    unidad_negocio = db.relationship("UnidadNegocio")


class CostoFijoProductivo(db.Model):
    """Concepto fijo, productivo o general, administrado por tenant."""

    __tablename__ = "costo_fijo_productivo"
    __table_args__ = (
        UniqueConstraint(
            "organizacion_id", "codigo",
            name="uq_costo_fijo_productivo_organizacion_codigo",
        ),
        CheckConstraint(
            "criterio_distribucion IN ('horas_productivas', 'horas_maquina', "
            "'unidades_producidas', 'porcentaje', 'importe_directo', "
            "'sin_distribuir')",
            name="ck_costo_fijo_criterio_distribucion",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True,
    )
    unidad_negocio_id = db.Column(
        db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=True, index=True,
    )
    codigo = db.Column(db.String(80), nullable=False, index=True)
    nombre = db.Column(db.String(200), nullable=False, index=True)
    categoria = db.Column(db.String(100), nullable=False, index=True)
    integra_costo_produccion = db.Column(
        db.Boolean, default=False, nullable=False, index=True,
    )
    criterio_distribucion = db.Column(db.String(30), nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False, index=True)
    observacion = db.Column(db.String(500))
    fecha_creacion = db.Column(
        db.DateTime, default=ahora_utc_naive, nullable=False,
    )

    unidad_negocio = db.relationship("UnidadNegocio")


class CostoFijoVersion(db.Model):
    """Importe historico mensual de un concepto de costo fijo."""

    __tablename__ = "costo_fijo_version"
    __table_args__ = (
        CheckConstraint(
            "importe_mensual_centavos >= 0",
            name="ck_costo_fijo_version_importe_no_negativo",
        ),
        Index(
            "uq_costo_fijo_numero", "costo_fijo_id", "moneda", "numero_version",
            unique=True,
        ),
        Index(
            "uq_costo_fijo_vigente", "costo_fijo_id", "moneda",
            unique=True,
            postgresql_where=text("vigente IS TRUE"),
            sqlite_where=text("vigente IS TRUE"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    costo_fijo_id = db.Column(
        db.Integer, db.ForeignKey("costo_fijo_productivo.id"), nullable=False,
        index=True,
    )
    moneda = db.Column(db.String(3), default="ARS", nullable=False, index=True)
    numero_version = db.Column(db.Integer, nullable=False)
    importe_mensual_centavos = db.Column(db.BigInteger, nullable=False)
    vigente = db.Column(db.Boolean, default=True, nullable=False, index=True)
    vigente_desde = db.Column(db.DateTime, nullable=False, index=True)
    vigente_hasta = db.Column(db.DateTime)
    comprobante_referencia = db.Column(db.String(120))
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuario_sistema.id"), nullable=True,
    )
    fecha_creacion = db.Column(
        db.DateTime, default=ahora_utc_naive, nullable=False,
    )

    costo_fijo = db.relationship("CostoFijoProductivo", backref="versiones")


class CostoFijoDistribucionVersion(db.Model):
    """Distribución histórica de un costo fijo entre unidades y ubicaciones."""

    __tablename__ = "costo_fijo_distribucion_version"
    __table_args__ = (
        CheckConstraint(
            "porcentaje_asignacion > 0 AND porcentaje_asignacion <= 100",
            name="ck_costo_fijo_distribucion_asignacion",
        ),
        CheckConstraint(
            "porcentaje_productivo >= 0 AND porcentaje_productivo <= 100",
            name="ck_costo_fijo_distribucion_productivo",
        ),
        UniqueConstraint(
            "costo_fijo_id", "numero_revision", "unidad_negocio_id",
            name="uq_costo_fijo_distribucion_revision_unidad",
        ),
        Index(
            "ix_costo_fijo_distribucion_vigente",
            "costo_fijo_id", "vigente",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True,
    )
    costo_fijo_id = db.Column(
        db.Integer, db.ForeignKey("costo_fijo_productivo.id"),
        nullable=False, index=True,
    )
    unidad_negocio_id = db.Column(
        db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=False, index=True,
    )
    numero_revision = db.Column(db.Integer, nullable=False)
    ubicacion_costo = db.Column(db.String(120), nullable=False)
    porcentaje_asignacion = db.Column(db.Numeric(9, 4), nullable=False)
    porcentaje_productivo = db.Column(db.Numeric(9, 4), nullable=False)
    vigente = db.Column(db.Boolean, default=True, nullable=False, index=True)
    vigente_desde = db.Column(db.DateTime, nullable=False, index=True)
    vigente_hasta = db.Column(db.DateTime)
    observacion = db.Column(db.String(500))
    creado_por_usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuario_sistema.id"), nullable=True,
    )
    fecha_creacion = db.Column(
        db.DateTime, default=ahora_utc_naive, nullable=False,
    )

    costo_fijo = db.relationship(
        "CostoFijoProductivo", backref="distribuciones_versionadas",
    )
    unidad_negocio = db.relationship("UnidadNegocio")
