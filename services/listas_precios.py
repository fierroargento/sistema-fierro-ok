"""Reglas puras y persistencia del dominio de listas de precios."""

from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP


def decimal_porcentaje(valor, nombre):
    try:
        numero = Decimal(str(valor).strip())
    except (InvalidOperation, AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"{nombre} no es valido.") from error
    if not numero.is_finite() or numero < 0 or numero >= 100:
        raise ValueError(f"{nombre} debe estar entre 0 y menos de 100.")
    return numero


def entero_no_negativo(valor, nombre):
    try:
        numero = int(valor)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{nombre} no es valido.") from error
    if numero < 0:
        raise ValueError(f"{nombre} no puede ser negativo.")
    return numero


def redondear_hacia_arriba(centavos, incremento):
    importe = entero_no_negativo(centavos, "El importe")
    paso = entero_no_negativo(incremento, "El incremento")
    if paso == 0:
        raise ValueError("El incremento debe ser mayor que cero.")
    return int(
        (Decimal(importe) / Decimal(paso)).to_integral_value(
            rounding=ROUND_CEILING
        ) * paso
    )


def calcular_precio_comercial(
    *, costo_base_centavos, flete_venta_centavos=0,
    cargo_fijo_centavos=0, comision_pct=0,
    margen_objetivo_pct=0, impuesto_pct=0,
    incremento_redondeo_centavos=1, precio_elegido_centavos=None,
):
    costo = entero_no_negativo(costo_base_centavos, "El costo base")
    flete = entero_no_negativo(flete_venta_centavos, "El flete de venta")
    cargo = entero_no_negativo(cargo_fijo_centavos, "El cargo fijo")
    comision = decimal_porcentaje(comision_pct, "La comision")
    margen_objetivo = decimal_porcentaje(
        margen_objetivo_pct, "El margen objetivo"
    )
    impuesto = decimal_porcentaje(impuesto_pct, "El impuesto")
    if comision + margen_objetivo >= Decimal("100"):
        raise ValueError("Comision y margen deben sumar menos de 100.")

    base_fija = costo + flete + cargo
    divisor = Decimal("1") - (
        comision + margen_objetivo
    ) / Decimal("100")
    sugerido_sin_redondear = int(
        (Decimal(base_fija) / divisor).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    sugerido = redondear_hacia_arriba(
        sugerido_sin_redondear, incremento_redondeo_centavos
    )
    elegido = sugerido if precio_elegido_centavos is None else (
        entero_no_negativo(precio_elegido_centavos, "El precio elegido")
    )
    comision_centavos = int(
        (Decimal(elegido) * comision / Decimal("100")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    margen_centavos = elegido - base_fija - comision_centavos
    margen_pct = (
        Decimal(margen_centavos) * Decimal("100") / Decimal(elegido)
        if elegido else Decimal("0")
    ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    impuestos_centavos = int(
        (Decimal(elegido) * impuesto / Decimal("100")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    return {
        "costo_base_centavos": costo,
        "flete_venta_centavos": flete,
        "cargo_fijo_centavos": cargo,
        "comision_centavos": comision_centavos,
        "margen_centavos": margen_centavos,
        "margen_pct": margen_pct,
        "impuestos_centavos": impuestos_centavos,
        "precio_neto_sugerido_centavos": sugerido,
        "precio_elegido_centavos": elegido,
        "precio_final_centavos": elegido + impuestos_centavos,
    }


def validar_alcance_lista(
    *, organizacion_id, unidad_negocio_id, catalogo_producto,
    costo_version, lista_precio=None,
):
    if catalogo_producto is None or catalogo_producto.catalogo is None:
        raise ValueError("La inclusion de catalogo no existe.")
    catalogo = catalogo_producto.catalogo
    if int(catalogo.organizacion_id) != int(organizacion_id):
        raise ValueError("El catalogo no pertenece a la organizacion.")
    if catalogo.unidad_negocio_id not in (None, unidad_negocio_id):
        raise ValueError("El catalogo no pertenece a la unidad.")
    if int(costo_version.organizacion_id) != int(organizacion_id):
        raise ValueError("El costo no pertenece a la organizacion.")
    if costo_version.unidad_negocio_id not in (None, unidad_negocio_id):
        raise ValueError("El costo no corresponde a la unidad.")
    if int(costo_version.producto_id) != int(catalogo_producto.producto_id):
        raise ValueError("El costo corresponde a otro producto.")
    if lista_precio is not None:
        if int(lista_precio.organizacion_id) != int(organizacion_id):
            raise ValueError("La lista no pertenece a la organizacion.")
        if lista_precio.unidad_negocio_id not in (None, unidad_negocio_id):
            raise ValueError("La lista no corresponde a la unidad.")
        if lista_precio.moneda != costo_version.moneda:
            raise ValueError("La moneda de la lista y el costo no coinciden.")
    return True
