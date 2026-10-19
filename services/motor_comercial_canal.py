"""Calcula precios de canal sin conectarse ni publicar cambios externos."""

from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP


def _pct(valor):
    try: numero = Decimal(str(valor or 0).replace(",", "."))
    except (InvalidOperation, ValueError) as error: raise ValueError("La comisión no es válida.") from error
    if not numero.is_finite() or numero < 0 or numero >= 100: raise ValueError("La comisión debe estar entre 0 y menos de 100%.")
    return numero


def _redondear(valor, paso):
    return int((Decimal(valor) / Decimal(paso)).to_integral_value(rounding=ROUND_CEILING) * paso)


def precio_lista_para_descuento(precio_efectivo_centavos, descuento_pct, paso_centavos=1):
    """Reconstruye el precio de lista necesario para conservar un descuento observado."""
    efectivo = int(precio_efectivo_centavos)
    descuento = _pct(descuento_pct) / Decimal("100")
    paso = int(paso_centavos)
    if efectivo < 0 or paso <= 0:
        raise ValueError("El precio efectivo y el redondeo deben ser válidos.")
    requerido = (Decimal(efectivo) / (Decimal("1") - descuento)).to_integral_value(rounding=ROUND_CEILING)
    return _redondear(int(requerido), paso)


def cargo_para_precio(precio_centavos, tramos):
    coincidentes = [t for t in tramos if int(t.precio_desde_centavos) <= precio_centavos and (t.precio_hasta_centavos is None or precio_centavos < int(t.precio_hasta_centavos))]
    if len(coincidentes) > 1: raise ValueError("Los tramos de cargo fijo se superponen.")
    return int(coincidentes[0].cargo_fijo_centavos) if coincidentes else 0


def liquidar_precio(precio_centavos, *, comision_pct, publicidad_pct=0, financiacion_pct=0, devoluciones_pct=0, tramos=(), umbral_envio_centavos=0, costo_envio_centavos=0):
    precio = int(precio_centavos); comision = _pct(comision_pct)
    publicidad = _pct(publicidad_pct); financiacion = _pct(financiacion_pct)
    devoluciones = _pct(devoluciones_pct)
    if comision + publicidad + financiacion + devoluciones >= 100:
        raise ValueError("Comision, publicidad, financiacion y devoluciones deben sumar menos de 100%.")
    comision_centavos = int((Decimal(precio) * comision / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    publicidad_centavos = int((Decimal(precio) * publicidad / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    financiacion_centavos = int((Decimal(precio) * financiacion / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    devoluciones_centavos = int((Decimal(precio) * devoluciones / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    cargo = cargo_para_precio(precio, tramos)
    envio = int(costo_envio_centavos) if int(umbral_envio_centavos or 0) > 0 and precio >= int(umbral_envio_centavos) else 0
    return {"precio_final_centavos": precio, "comision_centavos": comision_centavos, "publicidad_centavos": publicidad_centavos, "financiacion_centavos": financiacion_centavos, "devoluciones_centavos": devoluciones_centavos, "cargo_fijo_centavos": cargo, "envio_centavos": envio, "liquidacion_centavos": precio - comision_centavos - publicidad_centavos - financiacion_centavos - devoluciones_centavos - cargo - envio}


def calcular_precio_minimo_canal(piso_liquidacion_centavos, regla, *, costo_envio_centavos=None):
    piso = int(piso_liquidacion_centavos); paso = int(regla.incremento_redondeo_centavos)
    if piso < 0 or paso <= 0: raise ValueError("El piso y el redondeo deben ser válidos.")
    envio = int(regla.costo_envio_default_centavos if costo_envio_centavos is None else costo_envio_centavos)
    limites = {0, int(regla.umbral_envio_centavos or 0)}
    for tramo in regla.tramos:
        limites.add(int(tramo.precio_desde_centavos))
        if tramo.precio_hasta_centavos is not None: limites.add(int(tramo.precio_hasta_centavos))
    limites = sorted(x for x in limites if x >= 0)
    segmentos = [(desde, limites[i + 1] - 1 if i + 1 < len(limites) else None) for i, desde in enumerate(limites)]
    comision = _pct(regla.comision_pct) / Decimal("100")
    publicidad = _pct(getattr(regla, "publicidad_pct", 0)) / Decimal("100")
    financiacion = _pct(getattr(regla, "financiacion_pct", 0)) / Decimal("100")
    devoluciones = _pct(getattr(regla, "devoluciones_pct", 0)) / Decimal("100")
    tasa_total = comision + publicidad + financiacion + devoluciones
    if tasa_total >= 1: raise ValueError("Los costos porcentuales deben sumar menos de 100%.")
    # Cada deducción se redondea por separado. La fórmula continua puede
    # quedar por debajo del piso o saltarse un precio menor válido.
    # Dentro de cada tramo, el error total queda acotado por n/2 centavos.
    error_redondeo = Decimal(sum(tasa > 0 for tasa in (comision, publicidad, financiacion, devoluciones))) / 2
    candidatos = []
    evaluados = 0
    for desde, hasta in segmentos:
        cargo = cargo_para_precio(desde, regla.tramos)
        envio_segmento = envio if int(regla.umbral_envio_centavos or 0) > 0 and desde >= int(regla.umbral_envio_centavos) else 0
        if cargo < 0 or envio_segmento < 0:
            raise ValueError("Los cargos y el envío no pueden ser negativos.")
        constante = Decimal(piso + cargo + envio_segmento)
        inferior = ((constante - error_redondeo) / (Decimal("1") - tasa_total)).to_integral_value(rounding=ROUND_CEILING)
        superior = ((constante + error_redondeo) / (Decimal("1") - tasa_total)).to_integral_value(rounding=ROUND_CEILING)
        primero = _redondear(max(desde, int(inferior)), paso)
        ultimo = _redondear(max(desde, int(superior)), paso)
        if hasta is not None:
            ultimo = min(ultimo, hasta)
        if primero > ultimo:
            continue
        # Tramos en orden creciente: un tramo posterior no mejora un precio encontrado.
        if candidatos and primero >= candidatos[0]["precio_final_centavos"]:
            break
        cantidad = (ultimo - primero) // paso + 1
        if evaluados + cantidad > 100000:
            raise ValueError("La política requiere revisión: no se puede verificar el precio mínimo con este redondeo y tasas.")
        for candidato in range(primero, ultimo + 1, paso):
            evaluados += 1
            liquidacion = liquidar_precio(candidato, comision_pct=regla.comision_pct,
                publicidad_pct=getattr(regla, "publicidad_pct", 0),
                financiacion_pct=getattr(regla, "financiacion_pct", 0),
                devoluciones_pct=getattr(regla, "devoluciones_pct", 0),
                tramos=regla.tramos, umbral_envio_centavos=regla.umbral_envio_centavos,
                costo_envio_centavos=envio)
            if liquidacion["liquidacion_centavos"] >= piso:
                candidatos.append(liquidacion)
                break
    if not candidatos: raise ValueError("No se encontró un precio compatible con la política.")
    resultado = min(candidatos, key=lambda item: item["precio_final_centavos"])
    resultado["piso_liquidacion_centavos"] = piso
    resultado["excedente_centavos"] = resultado["liquidacion_centavos"] - piso
    return resultado
