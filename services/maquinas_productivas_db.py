"""Persistencia tenant de maquinas y sus tarifas historicas."""

from services.costos_productos import normalizar_moneda
from services.fechas import ahora_utc_naive
from services.maquinas_productivas import calcular_tarifa_maquina


def _texto(valor, nombre, limite):
    texto = str(valor or "").strip()
    if not texto:
        raise ValueError(f"{nombre} es obligatorio.")
    if len(texto) > limite:
        raise ValueError(f"{nombre} supera {limite} caracteres.")
    return texto


def crear_maquina(
    *, organizacion_id, unidad_negocio_id, codigo, nombre, categoria,
    observacion=None, Organizacion, UnidadNegocio, MaquinaProductiva,
    db_session, commit=False,
):
    organizacion = db_session.get(Organizacion, organizacion_id)
    unidad = db_session.get(UnidadNegocio, unidad_negocio_id)
    if organizacion is None or unidad is None:
        raise ValueError("La organizacion o unidad no existe.")
    if int(unidad.organizacion_id) != int(organizacion_id):
        raise ValueError("La unidad no pertenece a la organizacion.")
    codigo_normalizado = _texto(codigo, "El codigo", 80).lower()
    if MaquinaProductiva.query.filter_by(
        organizacion_id=organizacion_id, codigo=codigo_normalizado,
    ).first() is not None:
        raise ValueError("El codigo de maquina ya existe en la organizacion.")
    maquina = MaquinaProductiva(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        codigo=codigo_normalizado,
        nombre=_texto(nombre, "El nombre", 200),
        categoria=_texto(categoria, "La categoria", 100),
        activo=False,
        observacion=str(observacion or "").strip() or None,
    )
    db_session.add(maquina)
    if commit:
        db_session.commit()
    else:
        db_session.flush()
    return maquina


def registrar_costo_maquina(
    maquina, *, moneda, valor_adquisicion_centavos,
    valor_residual_centavos=0, vida_util_horas, potencia_kw=0,
    factor_carga_pct=100, costo_kwh_centavos=0,
    mantenimiento_mensual_centavos=0, otros_costos_mensuales_centavos=0,
    horas_productivas_mensuales, vigente_desde=None, observacion=None,
    creado_por_usuario_id=None, MaquinaCostoVersion, db_session,
):
    if maquina is None:
        raise ValueError("La maquina no existe.")
    tarifa = calcular_tarifa_maquina(
        valor_adquisicion_centavos=valor_adquisicion_centavos,
        valor_residual_centavos=valor_residual_centavos,
        vida_util_horas=vida_util_horas,
        potencia_kw=potencia_kw,
        factor_carga_pct=factor_carga_pct,
        costo_kwh_centavos=costo_kwh_centavos,
        mantenimiento_mensual_centavos=mantenimiento_mensual_centavos,
        otros_costos_mensuales_centavos=otros_costos_mensuales_centavos,
        horas_productivas_mensuales=horas_productivas_mensuales,
    )
    moneda_normalizada = normalizar_moneda(moneda)
    versiones = MaquinaCostoVersion.query.filter_by(
        maquina_id=maquina.id, moneda=moneda_normalizada,
    ).all()
    momento = vigente_desde or ahora_utc_naive()
    numero = max((v.numero_version for v in versiones), default=0) + 1
    for anterior in versiones:
        if anterior.vigente:
            anterior.vigente = False
            anterior.vigente_hasta = momento
    version = MaquinaCostoVersion(
        maquina_id=maquina.id,
        moneda=moneda_normalizada,
        numero_version=numero,
        valor_adquisicion_centavos=int(valor_adquisicion_centavos),
        valor_residual_centavos=int(valor_residual_centavos or 0),
        vida_util_horas=vida_util_horas,
        potencia_kw=potencia_kw or 0,
        factor_carga_pct=factor_carga_pct,
        costo_kwh_centavos=int(costo_kwh_centavos or 0),
        mantenimiento_mensual_centavos=int(
            mantenimiento_mensual_centavos or 0
        ),
        otros_costos_mensuales_centavos=int(
            otros_costos_mensuales_centavos or 0
        ),
        horas_productivas_mensuales=horas_productivas_mensuales,
        costo_hora_centavos=tarifa["costo_hora_centavos"],
        costo_minuto_centavos=tarifa["costo_minuto_centavos"],
        vigente=True,
        vigente_desde=momento,
        observacion=str(observacion or "").strip() or None,
        creado_por_usuario_id=creado_por_usuario_id,
    )
    db_session.add(version)
    db_session.commit()
    return version
