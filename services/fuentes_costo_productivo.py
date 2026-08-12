"""Administracion aislada de fuentes historicas del costo productivo."""

from decimal import Decimal
from decimal import InvalidOperation
from decimal import ROUND_HALF_UP

from sqlalchemy import func

from services.costos_productos import normalizar_moneda
from services.fechas import ahora_utc_naive


TIPOS_INSUMO = {
    "materia_prima",
    "consumible",
    "servicio_productivo",
    "embalaje_productivo",
}

CRITERIOS_DISTRIBUCION = {
    "horas_productivas",
    "horas_maquina",
    "unidades_producidas",
    "porcentaje",
    "importe_directo",
    "sin_distribuir",
}

TIPOS_FUNCION_LABORAL = {
    "directa", "indirecta_productiva", "comercial_administrativa", "mixta",
}

NATURALEZAS_COSTO = {"fijo", "variable", "provision"}
MESES_PERIODICIDAD = {
    "mensual": Decimal("1"), "bimestral": Decimal("2"),
    "trimestral": Decimal("3"), "cuatrimestral": Decimal("4"),
    "semestral": Decimal("6"), "anual": Decimal("12"),
}


def calcular_equivalente_mensual(
    importe_periodo_centavos, *, naturaleza="fijo", periodicidad="mensual",
    meses_cobertura=None,
):
    importe = _entero_no_negativo(importe_periodo_centavos, "El importe")
    naturaleza_normalizada = str(naturaleza or "fijo").strip().lower()
    if naturaleza_normalizada not in NATURALEZAS_COSTO:
        raise ValueError("La naturaleza del costo no es válida.")
    periodo = str(periodicidad or "mensual").strip().lower()
    if periodo == "eventual":
        meses = _decimal_positivo(
            meses_cobertura, "Los meses de cobertura",
        )
    elif periodo in MESES_PERIODICIDAD:
        meses = MESES_PERIODICIDAD[periodo]
    else:
        raise ValueError("La periodicidad del costo no es válida.")
    mensual = int(
        (Decimal(importe) / meses).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP,
        )
    )
    return {
        "importe_periodo_centavos": importe,
        "importe_mensual_centavos": mensual,
        "naturaleza": naturaleza_normalizada,
        "periodicidad": periodo,
        "meses_cobertura": meses,
    }


def _texto_requerido(valor, campo, limite):
    texto = str(valor or "").strip()
    if not texto:
        raise ValueError(f"{campo} es obligatorio.")
    if len(texto) > limite:
        raise ValueError(f"{campo} supera {limite} caracteres.")
    return texto


def _entero_no_negativo(valor, campo):
    try:
        numero = int(valor)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{campo} no es valido.") from error
    if numero < 0:
        raise ValueError(f"{campo} no puede ser negativo.")
    return numero


def _decimal_positivo(valor, campo):
    try:
        numero = Decimal(str(valor).strip())
    except (InvalidOperation, AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"{campo} no es valido.") from error
    if not numero.is_finite() or numero <= 0:
        raise ValueError(f"{campo} debe ser mayor que cero.")
    return numero


def _validar_alcance(
    *, organizacion_id, unidad_negocio_id, Organizacion, UnidadNegocio,
    db_session,
):
    organizacion = db_session.get(Organizacion, organizacion_id)
    if organizacion is None:
        raise ValueError("La organizacion indicada no existe.")

    unidad = None
    if unidad_negocio_id is not None:
        unidad = db_session.get(UnidadNegocio, unidad_negocio_id)
        if unidad is None:
            raise ValueError("La unidad de negocio indicada no existe.")
        if int(unidad.organizacion_id) != int(organizacion_id):
            raise ValueError("La unidad no pertenece a la organizacion.")
    return organizacion, unidad


def _crear_maestro(
    Modelo, *, organizacion_id, unidad_negocio_id, codigo, nombre,
    Organizacion, UnidadNegocio, db_session, campos, commit,
):
    _validar_alcance(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        Organizacion=Organizacion,
        UnidadNegocio=UnidadNegocio,
        db_session=db_session,
    )
    codigo_normalizado = _texto_requerido(codigo, "El codigo", 80).lower()
    if Modelo.query.filter_by(
        organizacion_id=organizacion_id,
        codigo=codigo_normalizado,
    ).first() is not None:
        raise ValueError("El codigo ya existe en la organizacion.")

    registro = Modelo(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        codigo=codigo_normalizado,
        nombre=_texto_requerido(nombre, "El nombre", 200),
        **campos,
    )
    try:
        db_session.add(registro)
        if commit:
            db_session.commit()
        else:
            db_session.flush()
    except Exception:
        db_session.rollback()
        raise
    return registro


def crear_insumo(
    *, organizacion_id, unidad_negocio_id, codigo, nombre, tipo,
    unidad_medida, observacion=None, Organizacion, UnidadNegocio,
    InsumoProductivo, db_session, commit=True,
):
    tipo_normalizado = str(tipo or "").strip().lower()
    if tipo_normalizado not in TIPOS_INSUMO:
        raise ValueError("El tipo de insumo no es valido.")
    return _crear_maestro(
        InsumoProductivo,
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        codigo=codigo,
        nombre=nombre,
        Organizacion=Organizacion,
        UnidadNegocio=UnidadNegocio,
        db_session=db_session,
        commit=commit,
        campos={
            "tipo": tipo_normalizado,
            "unidad_medida": _texto_requerido(
                unidad_medida, "La unidad de medida", 30,
            ),
            "observacion": str(observacion or "").strip() or None,
        },
    )


def crear_empleado(
    *, organizacion_id, unidad_negocio_id, codigo, nombre, sector,
    puesto=None, observacion=None, Organizacion, UnidadNegocio,
    EmpleadoProductivo, db_session, commit=True,
):
    return _crear_maestro(
        EmpleadoProductivo,
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        codigo=codigo,
        nombre=nombre,
        Organizacion=Organizacion,
        UnidadNegocio=UnidadNegocio,
        db_session=db_session,
        commit=commit,
        campos={
            "sector": _texto_requerido(sector, "El sector", 120),
            "puesto": str(puesto or "").strip() or None,
            "observacion": str(observacion or "").strip() or None,
        },
    )


def crear_costo_fijo(
    *, organizacion_id, unidad_negocio_id, codigo, nombre, categoria,
    integra_costo_produccion, criterio_distribucion, observacion=None,
    Organizacion, UnidadNegocio, CostoFijoProductivo, db_session, commit=True,
):
    criterio = str(criterio_distribucion or "").strip().lower()
    if criterio not in CRITERIOS_DISTRIBUCION:
        raise ValueError("El criterio de distribucion no es valido.")
    if not integra_costo_produccion and criterio != "sin_distribuir":
        raise ValueError(
            "Un costo que no integra produccion debe quedar sin distribuir."
        )
    return _crear_maestro(
        CostoFijoProductivo,
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        codigo=codigo,
        nombre=nombre,
        Organizacion=Organizacion,
        UnidadNegocio=UnidadNegocio,
        db_session=db_session,
        commit=commit,
        campos={
            "categoria": _texto_requerido(categoria, "La categoria", 100),
            "integra_costo_produccion": bool(integra_costo_produccion),
            "criterio_distribucion": criterio,
            "observacion": str(observacion or "").strip() or None,
        },
    )


def _crear_version_vigente(
    *, maestro, moneda, ModeloVersion, fk_nombre, valores, vigente_desde,
    db_session,
):
    if maestro is None:
        raise ValueError("El registro base no existe.")
    moneda_normalizada = normalizar_moneda(moneda)
    momento = vigente_desde or ahora_utc_naive()
    filtro_fk = getattr(ModeloVersion, fk_nombre) == maestro.id

    numero = (
        db_session.query(func.max(ModeloVersion.numero_version))
        .filter(filtro_fk, ModeloVersion.moneda == moneda_normalizada)
        .scalar()
        or 0
    ) + 1

    anteriores = ModeloVersion.query.filter(
        filtro_fk,
        ModeloVersion.moneda == moneda_normalizada,
        ModeloVersion.vigente.is_(True),
    ).all()
    version = ModeloVersion(
        **{fk_nombre: maestro.id},
        moneda=moneda_normalizada,
        numero_version=numero,
        vigente=True,
        vigente_desde=momento,
        **valores,
    )
    try:
        for anterior in anteriores:
            anterior.vigente = False
            anterior.vigente_hasta = momento
        db_session.add(version)
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return version


def registrar_precio_insumo(
    insumo, *, moneda, precio_unitario_centavos, vigente_desde=None,
    proveedor_referencia=None, comprobante_referencia=None, observacion=None,
    creado_por_usuario_id=None, InsumoPrecioVersion, db_session,
):
    return _crear_version_vigente(
        maestro=insumo,
        moneda=moneda,
        ModeloVersion=InsumoPrecioVersion,
        fk_nombre="insumo_id",
        vigente_desde=vigente_desde,
        db_session=db_session,
        valores={
            "precio_unitario_centavos": _entero_no_negativo(
                precio_unitario_centavos, "El precio unitario",
            ),
            "proveedor_referencia": str(proveedor_referencia or "").strip() or None,
            "comprobante_referencia": str(comprobante_referencia or "").strip() or None,
            "observacion": str(observacion or "").strip() or None,
            "creado_por_usuario_id": creado_por_usuario_id,
        },
    )


def calcular_tarifa_laboral(
    *, sueldo_base_centavos, cargas_sociales_centavos=0,
    porcentaje_cargas=None,
    adicionales_centavos=0, otros_costos_centavos=0,
    horas_mensuales, horas_productivas, porcentaje_productivo=100,
):
    sueldo = _entero_no_negativo(sueldo_base_centavos, "El sueldo base")
    porcentaje = Decimal("0")
    if porcentaje_cargas is not None:
        try:
            porcentaje = Decimal(str(porcentaje_cargas).replace(",", "."))
        except (InvalidOperation, ValueError) as error:
            raise ValueError("El porcentaje de cargas no es valido.") from error
        if not porcentaje.is_finite() or porcentaje < 0 or porcentaje > 100:
            raise ValueError("El porcentaje de cargas debe estar entre 0 y 100.")
        cargas_sociales_centavos = int(
            (Decimal(sueldo) * porcentaje / Decimal("100")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP,
            )
        )
    importes = [
        sueldo,
        _entero_no_negativo(cargas_sociales_centavos, "Las cargas sociales"),
        _entero_no_negativo(adicionales_centavos, "Los adicionales"),
        _entero_no_negativo(otros_costos_centavos, "Los otros costos"),
    ]
    horas_mes = _decimal_positivo(horas_mensuales, "Las horas mensuales")
    horas_prod = _decimal_positivo(horas_productivas, "Las horas productivas")
    if horas_prod > horas_mes:
        raise ValueError(
            "Las horas productivas no pueden superar las horas mensuales."
        )
    porcentaje_prod = Decimal(str(porcentaje_productivo or "0").replace(",", "."))
    if not porcentaje_prod.is_finite() or porcentaje_prod < 0 or porcentaje_prod > 100:
        raise ValueError("El porcentaje productivo debe estar entre 0 y 100.")
    total = sum(importes)
    hora = int(
        (Decimal(total) / horas_prod).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    minuto = int(
        (Decimal(total) / horas_prod / Decimal("60")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP,
        )
    )
    return {
        "sueldo_base_centavos": importes[0],
        "cargas_sociales_centavos": importes[1],
        "porcentaje_cargas": porcentaje,
        "adicionales_centavos": importes[2],
        "otros_costos_centavos": importes[3],
        "horas_mensuales": horas_mes,
        "horas_productivas": horas_prod,
        "porcentaje_productivo": porcentaje_prod,
        "costo_mensual_total_centavos": total,
        "costo_hora_productiva_centavos": hora,
        "costo_minuto_productivo_centavos": minuto,
    }


def registrar_costo_empleado(
    empleado, *, moneda, sueldo_base_centavos, cargas_sociales_centavos=0,
    porcentaje_cargas=None, usa_porcentaje_general=False,
    adicionales_centavos=0, otros_costos_centavos=0, horas_mensuales,
    horas_productivas, ubicacion_trabajo="Sin definir", tipo_funcion="directa",
    porcentaje_productivo=100, vigente_desde=None, observacion=None,
    creado_por_usuario_id=None, EmpleadoCostoVersion, db_session,
):
    valores = calcular_tarifa_laboral(
        sueldo_base_centavos=sueldo_base_centavos,
        cargas_sociales_centavos=cargas_sociales_centavos,
        porcentaje_cargas=porcentaje_cargas,
        adicionales_centavos=adicionales_centavos,
        otros_costos_centavos=otros_costos_centavos,
        horas_mensuales=horas_mensuales,
        horas_productivas=horas_productivas,
        porcentaje_productivo=porcentaje_productivo,
    )
    tipo = str(tipo_funcion or "").strip().lower()
    if tipo not in TIPOS_FUNCION_LABORAL:
        raise ValueError("El tipo de función laboral no es válido.")
    valores.update({
        "usa_porcentaje_general": bool(usa_porcentaje_general),
        "ubicacion_trabajo": _texto_requerido(
            ubicacion_trabajo, "La ubicación de trabajo", 120,
        ),
        "tipo_funcion": tipo,
        "observacion": str(observacion or "").strip() or None,
        "creado_por_usuario_id": creado_por_usuario_id,
    })
    return _crear_version_vigente(
        maestro=empleado,
        moneda=moneda,
        ModeloVersion=EmpleadoCostoVersion,
        fk_nombre="empleado_id",
        valores=valores,
        vigente_desde=vigente_desde,
        db_session=db_session,
    )


def registrar_importe_costo_fijo(
    costo_fijo, *, moneda, importe_mensual_centavos=None,
    importe_periodo_centavos=None, naturaleza="fijo", periodicidad="mensual",
    meses_cobertura=None, vigente_desde=None,
    comprobante_referencia=None, observacion=None, creado_por_usuario_id=None,
    CostoFijoVersion, db_session,
):
    importe_declarado = (
        importe_periodo_centavos
        if importe_periodo_centavos is not None
        else importe_mensual_centavos
    )
    valores_periodicos = calcular_equivalente_mensual(
        importe_declarado, naturaleza=naturaleza,
        periodicidad=periodicidad, meses_cobertura=meses_cobertura,
    )
    return _crear_version_vigente(
        maestro=costo_fijo,
        moneda=moneda,
        ModeloVersion=CostoFijoVersion,
        fk_nombre="costo_fijo_id",
        vigente_desde=vigente_desde,
        db_session=db_session,
        valores={
            **valores_periodicos,
            "comprobante_referencia": str(comprobante_referencia or "").strip() or None,
            "observacion": str(observacion or "").strip() or None,
            "creado_por_usuario_id": creado_por_usuario_id,
        },
    )
