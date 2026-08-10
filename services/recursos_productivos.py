"""Equipos de mano de obra y sus tarifas ponderadas, aislados por unidad."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from services.fuentes_costo_productivo import crear_empleado, registrar_costo_empleado


def _decimal_porcentaje(valor, campo, *, permite_cero=True):
    try:
        numero = Decimal(str(valor or "0").replace(",", ".").strip())
    except (InvalidOperation, AttributeError, ValueError) as error:
        raise ValueError(f"{campo} no es válido.") from error
    minimo = Decimal("0") if permite_cero else Decimal("0.0001")
    if not numero.is_finite() or numero < minimo or numero > Decimal("100"):
        raise ValueError(f"{campo} debe estar entre {minimo} y 100.")
    return numero


def _vigente(empleado):
    return next(
        (v for v in empleado.versiones_costo if v.vigente and v.moneda == "ARS"),
        None,
    )


def crear_recurso(
    *, organizacion_id, unidad_negocio_id, codigo, nombre, sector,
    porcentaje_indirecto=0, observacion=None, Organizacion, UnidadNegocio,
    EmpleadoProductivo, db_session,
):
    recurso = crear_empleado(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        codigo=codigo,
        nombre=nombre,
        sector=sector,
        puesto="Equipo productivo",
        observacion=observacion,
        Organizacion=Organizacion,
        UnidadNegocio=UnidadNegocio,
        EmpleadoProductivo=EmpleadoProductivo,
        db_session=db_session,
        commit=False,
    )
    recurso.tipo_registro = "recurso"
    recurso.porcentaje_indirecto = _decimal_porcentaje(
        porcentaje_indirecto, "El porcentaje indirecto",
    )
    db_session.commit()
    return recurso


def vincular_empleado(
    recurso, empleado, *, porcentaje_dedicacion=100, observacion=None,
    RecursoEmpleadoProductivo, db_session,
):
    if recurso is None or recurso.tipo_registro != "recurso":
        raise ValueError("El recurso productivo no es válido.")
    if empleado is None or empleado.tipo_registro != "empleado":
        raise ValueError("Solo se pueden incorporar empleados individuales.")
    if int(recurso.organizacion_id) != int(empleado.organizacion_id):
        raise ValueError("El empleado no pertenece a la organización del recurso.")
    if recurso.unidad_negocio_id != empleado.unidad_negocio_id:
        raise ValueError("El empleado y el recurso deben pertenecer a la misma unidad.")
    dedicacion = _decimal_porcentaje(
        porcentaje_dedicacion, "La dedicación", permite_cero=False,
    )
    otras = RecursoEmpleadoProductivo.query.filter_by(
        empleado_id=empleado.id,
    ).all()
    asignado = sum(
        (Decimal(str(x.porcentaje_dedicacion)) for x in otras if x.recurso_id != recurso.id),
        Decimal("0"),
    )
    if asignado + dedicacion > Decimal("100"):
        raise ValueError(
            f"La dedicación total de {empleado.nombre} supera el 100%."
        )
    vinculo = RecursoEmpleadoProductivo.query.filter_by(
        recurso_id=recurso.id, empleado_id=empleado.id,
    ).first()
    if vinculo is None:
        vinculo = RecursoEmpleadoProductivo(
            recurso_id=recurso.id, empleado_id=empleado.id,
        )
        db_session.add(vinculo)
    vinculo.porcentaje_dedicacion = dedicacion
    vinculo.observacion = str(observacion or "").strip() or None
    db_session.commit()
    return vinculo


def calcular_componentes_recurso(recurso):
    if recurso is None or recurso.tipo_registro != "recurso":
        raise ValueError("El recurso productivo no es válido.")
    if not recurso.miembros_recurso:
        raise ValueError(f"{recurso.nombre} todavía no tiene empleados asignados.")
    acumulados = {
        "sueldo_base_centavos": Decimal("0"),
        "cargas_sociales_centavos": Decimal("0"),
        "adicionales_centavos": Decimal("0"),
        "otros_costos_centavos": Decimal("0"),
        "horas_mensuales": Decimal("0"),
        "horas_productivas": Decimal("0"),
    }
    for vinculo in recurso.miembros_recurso:
        version = _vigente(vinculo.empleado)
        if version is None:
            raise ValueError(f"{vinculo.empleado.nombre} no tiene costo vigente.")
        factor = (
            Decimal(str(vinculo.porcentaje_dedicacion)) / Decimal("100")
            * Decimal(str(getattr(version, "porcentaje_productivo", 100)))
            / Decimal("100")
        )
        for campo in (
            "sueldo_base_centavos", "cargas_sociales_centavos",
            "adicionales_centavos", "otros_costos_centavos",
            "horas_mensuales", "horas_productivas",
        ):
            acumulados[campo] += Decimal(str(getattr(version, campo))) * factor
    total_directo = sum(
        acumulados[campo] for campo in (
            "sueldo_base_centavos", "cargas_sociales_centavos",
            "adicionales_centavos", "otros_costos_centavos",
        )
    )
    porcentaje_indirecto = _decimal_porcentaje(
        recurso.porcentaje_indirecto, "El porcentaje indirecto",
    )
    indirecto = (
        total_directo * porcentaje_indirecto
        / Decimal("100")
    ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    acumulados["otros_costos_centavos"] += indirecto
    for campo in (
        "sueldo_base_centavos", "cargas_sociales_centavos",
        "adicionales_centavos", "otros_costos_centavos",
    ):
        acumulados[campo] = int(
            acumulados[campo].quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
    acumulados["costo_directo_centavos"] = int(
        total_directo.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    acumulados["costo_indirecto_centavos"] = int(indirecto)
    return acumulados


def recalcular_tarifa_recurso(
    recurso, *, EmpleadoCostoVersion, db_session, usuario_id=None,
):
    valores = calcular_componentes_recurso(recurso)
    version = registrar_costo_empleado(
        recurso,
        moneda="ARS",
        sueldo_base_centavos=valores["sueldo_base_centavos"],
        cargas_sociales_centavos=valores["cargas_sociales_centavos"],
        adicionales_centavos=valores["adicionales_centavos"],
        otros_costos_centavos=valores["otros_costos_centavos"],
        horas_mensuales=valores["horas_mensuales"],
        horas_productivas=valores["horas_productivas"],
        observacion=(
            f"Tarifa ponderada automática; directo "
            f"${valores['costo_directo_centavos'] / 100:.2f}; indirecto "
            f"${valores['costo_indirecto_centavos'] / 100:.2f}."
        ),
        creado_por_usuario_id=usuario_id,
        EmpleadoCostoVersion=EmpleadoCostoVersion,
        db_session=db_session,
    )
    return version, valores


def recalcular_recursos_del_empleado(
    empleado, *, EmpleadoCostoVersion, db_session, usuario_id=None,
):
    resultados = []
    for vinculo in empleado.participaciones_recurso:
        resultados.append(recalcular_tarifa_recurso(
            vinculo.recurso,
            EmpleadoCostoVersion=EmpleadoCostoVersion,
            db_session=db_session,
            usuario_id=usuario_id,
        ))
    return resultados
