"""Calcula precios de canal sin conectarse ni publicar cambios externos."""

from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP


def _pct(valor):
    try: numero = Decimal(str(valor or 0).replace(",", "."))
    except (InvalidOperation, ValueError) as error: raise ValueError("La comisión no es válida.") from error
    if not numero.is_finite() or numero < 0 or numero >= 100: raise ValueError("La comisión debe estar entre 0 y menos de 100%.")
    return numero


def _redondear(valor, paso):
    return int((Decimal(valor) / Decimal(paso)).to_integral_value(rounding=ROUND_CEILING) * paso)


def cargo_para_precio(precio_centavos, tramos):
    coincidentes = [t for t in tramos if int(t.precio_desde_centavos) <= precio_centavos and (t.precio_hasta_centavos is None or precio_centavos < int(t.precio_hasta_centavos))]
    if len(coincidentes) > 1: raise ValueError("Los tramos de cargo fijo se superponen.")
    return int(coincidentes[0].cargo_fijo_centavos) if coincidentes else 0


def liquidar_precio(precio_centavos, *, comision_pct, tramos=(), umbral_envio_centavos=0, costo_envio_centavos=0):
    precio = int(precio_centavos); comision = _pct(comision_pct)
    comision_centavos = int((Decimal(precio) * comision / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    cargo = cargo_para_precio(precio, tramos)
    envio = int(costo_envio_centavos) if int(umbral_envio_centavos or 0) > 0 and precio >= int(umbral_envio_centavos) else 0
    return {"precio_final_centavos": precio, "comision_centavos": comision_centavos, "cargo_fijo_centavos": cargo, "envio_centavos": envio, "liquidacion_centavos": precio - comision_centavos - cargo - envio}


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
    candidatos = []
    for desde, hasta in segmentos:
        muestra = desde
        cargo = cargo_para_precio(muestra, regla.tramos)
        envio_segmento = envio if int(regla.umbral_envio_centavos or 0) > 0 and muestra >= int(regla.umbral_envio_centavos) else 0
        requerido = (Decimal(piso + cargo + envio_segmento) / (Decimal("1") - comision)).to_integral_value(rounding=ROUND_CEILING)
        candidato = _redondear(max(desde, int(requerido)), paso)
        if hasta is not None and candidato > hasta: continue
        liquidacion = liquidar_precio(candidato, comision_pct=regla.comision_pct, tramos=regla.tramos, umbral_envio_centavos=regla.umbral_envio_centavos, costo_envio_centavos=envio)
        if liquidacion["liquidacion_centavos"] >= piso: candidatos.append(liquidacion)
    if not candidatos: raise ValueError("No se encontró un precio compatible con la política.")
    resultado = min(candidatos, key=lambda item: item["precio_final_centavos"])
    resultado["piso_liquidacion_centavos"] = piso
    resultado["excedente_centavos"] = resultado["liquidacion_centavos"] - piso
    return resultado
