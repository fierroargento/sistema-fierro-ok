"""Calculos puros para tarifas historicas de maquinas productivas."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _decimal(valor, campo, *, positivo=False, maximo=None):
    try:
        numero = Decimal(str(valor).strip())
    except (InvalidOperation, AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"{campo} no es valido.") from error
    if not numero.is_finite() or numero < 0 or (positivo and numero <= 0):
        raise ValueError(f"{campo} esta fuera de rango.")
    if maximo is not None and numero > maximo:
        raise ValueError(f"{campo} esta fuera de rango.")
    return numero


def _centavos(valor, campo):
    numero = _decimal(valor, campo)
    if numero != numero.to_integral_value():
        raise ValueError(f"{campo} debe expresarse en centavos enteros.")
    return int(numero)


def calcular_tarifa_maquina(
    *, valor_adquisicion_centavos, valor_residual_centavos=0,
    vida_util_horas, potencia_kw=0, factor_carga_pct=100,
    costo_kwh_centavos=0, mantenimiento_mensual_centavos=0,
    otros_costos_mensuales_centavos=0, horas_productivas_mensuales,
):
    """Devuelve un snapshot explicable de costo por hora y minuto."""
    adquisicion = _centavos(valor_adquisicion_centavos, "El valor de adquisicion")
    residual = _centavos(valor_residual_centavos, "El valor residual")
    if residual > adquisicion:
        raise ValueError("El valor residual no puede superar la adquisicion.")
    vida = _decimal(vida_util_horas, "La vida util", positivo=True)
    potencia = _decimal(potencia_kw, "La potencia")
    factor = _decimal(
        factor_carga_pct, "El factor de carga", maximo=Decimal("100"),
    )
    costo_kwh = _centavos(costo_kwh_centavos, "El costo del kWh")
    mantenimiento = _centavos(
        mantenimiento_mensual_centavos, "El mantenimiento mensual",
    )
    otros = _centavos(
        otros_costos_mensuales_centavos, "Los otros costos mensuales",
    )
    horas_mes = _decimal(
        horas_productivas_mensuales, "Las horas productivas", positivo=True,
    )

    amortizacion_hora = (Decimal(adquisicion - residual) / vida)
    energia_hora = potencia * factor / Decimal("100") * Decimal(costo_kwh)
    mantenimiento_hora = Decimal(mantenimiento) / horas_mes
    otros_hora = Decimal(otros) / horas_mes
    total_hora = (
        amortizacion_hora + energia_hora + mantenimiento_hora + otros_hora
    )
    total_minuto = total_hora / Decimal("60")

    redondear = lambda numero: int(
        numero.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    return {
        "amortizacion_hora_centavos": redondear(amortizacion_hora),
        "energia_hora_centavos": redondear(energia_hora),
        "mantenimiento_hora_centavos": redondear(mantenimiento_hora),
        "otros_hora_centavos": redondear(otros_hora),
        "costo_hora_centavos": redondear(total_hora),
        "costo_minuto_centavos": redondear(total_minuto),
    }
