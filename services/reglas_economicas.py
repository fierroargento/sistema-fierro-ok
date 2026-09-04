"""Piso economico anterior a comisiones, cargos, envios y promociones."""

from decimal import Decimal, InvalidOperation, ROUND_CEILING

from services.fechas import ahora_utc_naive


METODOS = {"sobre_costo", "sobre_liquidacion"}
ALCANCES = {"organizacion", "unidad", "catalogo", "producto"}


def _porcentaje(valor, nombre):
    try:
        numero = Decimal(str(valor or 0).replace(",", "."))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{nombre} no es válido.") from error
    if not numero.is_finite() or numero < 0 or numero >= 100:
        raise ValueError(f"{nombre} debe estar entre 0 y menos de 100.")
    return numero


def _metodo(valor, nombre):
    metodo = str(valor or "").strip().lower()
    if metodo not in METODOS:
        raise ValueError(f"{nombre} no es válido.")
    return metodo


def calcular_piso_economico(
    costo_centavos, *, impuesto_pct=0, metodo_impuesto="sobre_liquidacion",
    utilidad_pct=0, metodo_utilidad="sobre_costo", redondeo_centavos=1,
):
    costo = int(costo_centavos)
    paso = int(redondeo_centavos)
    if costo < 0 or paso <= 0:
        raise ValueError("El costo y el redondeo deben ser válidos.")
    impuesto = _porcentaje(impuesto_pct, "El impuesto") / Decimal("100")
    utilidad = _porcentaje(utilidad_pct, "La utilidad") / Decimal("100")
    metodo_i = _metodo(metodo_impuesto, "El método del impuesto")
    metodo_u = _metodo(metodo_utilidad, "El método de utilidad")
    factor_costo = Decimal("1")
    factor_liquidacion = Decimal("0")
    if metodo_i == "sobre_costo": factor_costo += impuesto
    else: factor_liquidacion += impuesto
    if metodo_u == "sobre_costo": factor_costo += utilidad
    else: factor_liquidacion += utilidad
    if factor_liquidacion >= Decimal("1"):
        raise ValueError("Impuesto y utilidad sobre liquidación deben sumar menos de 100%.")
    exacto = Decimal(costo) * factor_costo / (Decimal("1") - factor_liquidacion)
    piso = int((exacto / Decimal(paso)).to_integral_value(rounding=ROUND_CEILING) * paso)
    impuesto_centavos = int((Decimal(piso if metodo_i == "sobre_liquidacion" else costo) * impuesto).to_integral_value(rounding=ROUND_CEILING))
    utilidad_centavos = piso - costo - impuesto_centavos
    return {
        "costo_centavos": costo, "piso_liquidacion_centavos": piso,
        "impuesto_centavos": impuesto_centavos,
        "utilidad_centavos": utilidad_centavos,
    }


def calcular_pisos_regla(costo_centavos, regla):
    if regla is None:
        raise ValueError("No hay una regla económica aplicable.")
    comunes = {
        "impuesto_pct": regla.impuesto_pct,
        "metodo_impuesto": regla.metodo_impuesto,
        "metodo_utilidad": regla.metodo_utilidad,
        "redondeo_centavos": regla.incremento_redondeo_centavos,
    }
    return {
        "minimo": calcular_piso_economico(
            costo_centavos, utilidad_pct=regla.utilidad_minima_pct, **comunes,
        ),
        "objetivo": calcular_piso_economico(
            costo_centavos, utilidad_pct=regla.utilidad_objetivo_pct, **comunes,
        ),
    }


def clave_alcance(alcance, *, unidad_negocio_id=None, catalogo_id=None, producto_id=None):
    alcance = str(alcance or "").strip().lower()
    if alcance not in ALCANCES:
        raise ValueError("El alcance no es válido.")
    requeridos = {
        "organizacion": None, "unidad": unidad_negocio_id,
        "catalogo": catalogo_id, "producto": producto_id,
    }
    if alcance != "organizacion" and requeridos[alcance] is None:
        raise ValueError("Falta el registro correspondiente al alcance.")
    if alcance == "organizacion":
        return alcance
    if alcance == "producto":
        if unidad_negocio_id is None:
            raise ValueError("El alcance producto requiere una unidad.")
        return f"producto:{int(unidad_negocio_id)}:{int(producto_id)}"
    return f"{alcance}:{int(requeridos[alcance])}"


def resolver_regla_vigente(reglas, *, unidad_negocio_id, catalogo_id=None, producto_id=None):
    candidatas = [regla for regla in reglas if regla.vigente]
    prioridades = (
        ("producto", producto_id), ("catalogo", catalogo_id),
        ("unidad", unidad_negocio_id), ("organizacion", None),
    )
    for alcance, identificador in prioridades:
        clave = (
            alcance if identificador is None
            else f"producto:{unidad_negocio_id}:{identificador}"
            if alcance == "producto"
            else f"{alcance}:{identificador}"
        )
        encontrada = next((r for r in candidatas if r.clave_alcance == clave), None)
        if encontrada is not None:
            return encontrada
    return None


def crear_regla(
    *, organizacion_id, alcance, nombre, impuesto_pct, metodo_impuesto,
    utilidad_minima_pct, utilidad_objetivo_pct, metodo_utilidad,
    incremento_redondeo_centavos, unidad_negocio_id=None, catalogo_id=None,
    producto_id=None, observacion=None, usuario=None,
    ReglaEconomicaVersion, db_session,
):
    clave = clave_alcance(
        alcance, unidad_negocio_id=unidad_negocio_id,
        catalogo_id=catalogo_id, producto_id=producto_id,
    )
    minimo = _porcentaje(utilidad_minima_pct, "La utilidad mínima")
    objetivo = _porcentaje(utilidad_objetivo_pct, "La utilidad objetivo")
    if objetivo < minimo:
        raise ValueError("La utilidad objetivo no puede ser menor que la mínima.")
    anteriores = ReglaEconomicaVersion.query.filter_by(
        organizacion_id=organizacion_id, clave_alcance=clave,
    ).all()
    regla = ReglaEconomicaVersion(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        catalogo_id=catalogo_id, producto_id=producto_id, alcance=alcance,
        clave_alcance=clave,
        numero_version=max((r.numero_version for r in anteriores), default=0) + 1,
        nombre=str(nombre or "").strip(), impuesto_pct=_porcentaje(impuesto_pct, "El impuesto"),
        metodo_impuesto=_metodo(metodo_impuesto, "El método del impuesto"),
        utilidad_minima_pct=minimo, utilidad_objetivo_pct=objetivo,
        metodo_utilidad=_metodo(metodo_utilidad, "El método de utilidad"),
        incremento_redondeo_centavos=max(1, int(incremento_redondeo_centavos)),
        observacion=str(observacion or "").strip() or None,
        creado_por_usuario_id=getattr(usuario, "id", None),
        creado_por_username=getattr(usuario, "username", None),
    )
    if not regla.nombre:
        raise ValueError("La regla requiere un nombre.")
    db_session.add(regla); db_session.commit(); return regla


def activar_regla(regla, *, ReglaEconomicaVersion, db_session):
    if regla is None or regla.estado not in {"preparatorio", "archivado"}:
        raise ValueError("La regla no puede activarse.")
    momento = ahora_utc_naive()
    anteriores = ReglaEconomicaVersion.query.filter_by(
        organizacion_id=regla.organizacion_id,
        clave_alcance=regla.clave_alcance, vigente=True,
    ).all()
    for anterior in anteriores:
        anterior.vigente = False; anterior.estado = "archivado"; anterior.vigente_hasta = momento
    regla.vigente = True; regla.estado = "vigente"; regla.vigente_desde = momento; regla.vigente_hasta = None
    db_session.commit(); return regla
