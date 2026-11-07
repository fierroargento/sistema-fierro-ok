"""Base mayorista calculada exclusivamente con la ficha de cada producto."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _numero(valor, nombre):
    if valor is None or str(valor).strip() == '':
        raise ValueError(f'Falta {nombre} en la ficha del producto.')
    try:
        n = Decimal(str(valor).replace(',', '.'))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f'{nombre} no válido.') from error
    if not n.is_finite() or n < 0:
        raise ValueError(f'{nombre} no válido.')
    return n


def calcular_mayorista(costo_centavos, *, utilidad_pct, utilidad_base,
                       iva_pct, iibb_pct):
    """Recargo o margen individual; IIBB sobre neto de venta, IVA al final.

    El precio base conserva costo + utilidad. Se exponen por separado el
    neto que cubre IIBB y el total con IVA; no se reaplica utilidad al canal.
    """
    costo = _numero(costo_centavos, 'costo')
    if costo != costo.to_integral_value():
        raise ValueError('El costo debe expresarse en centavos enteros.')
    utilidad = _numero(utilidad_pct, 'utilidad') / 100
    iva = _numero(iva_pct, 'IVA') / 100
    iibb = _numero(iibb_pct, 'IIBB') / 100
    if iva > 1 or iibb >= 1:
        raise ValueError('Porcentajes de impuestos no válidos.')
    if utilidad_base == 'costo':
        base = costo * (1 + utilidad)
    elif utilidad_base == 'precio_venta' and utilidad < 1:
        base = costo / (1 - utilidad)
    else:
        raise ValueError('Base o margen de utilidad no válido.')
    centavos = lambda n: int(n.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    base = centavos(base)
    neto = centavos(Decimal(base) / (1 - iibb))
    iva_importe = centavos(Decimal(neto) * iva)
    return dict(costo_centavos=int(costo), base_centavos=base,
                iibb_centavos=neto-base, neto_centavos=neto,
                iva_centavos=iva_importe, precio_final_centavos=neto+iva_importe,
                utilidad_pct=str(utilidad_pct), utilidad_base=utilidad_base,
                iva_pct=str(iva_pct), iibb_pct=str(iibb_pct))


def calcular_desde_ficha(costo, ficha):
    if ficha is None or (ficha.producto_id, ficha.organizacion_id) != (
            costo.producto_id, costo.organizacion_id):
        raise ValueError('Falta la ficha fiscal y de utilidad del producto en esta organización.')
    return calcular_mayorista(costo.costo_total_centavos,
        utilidad_pct=ficha.utilidad_pct, utilidad_base=ficha.utilidad_base,
        iva_pct=ficha.iva_pct, iibb_pct=ficha.iibb_pct)


def piso_mayorista(resultado):
    return dict(costo_centavos=resultado['costo_centavos'],
        piso_liquidacion_centavos=resultado['precio_final_centavos'],
        impuesto_centavos=resultado['iibb_centavos']+resultado['iva_centavos'],
        utilidad_centavos=resultado['base_centavos']-resultado['costo_centavos'])


def preparar_mayoristas(costos, datos_productos):
    """Último costo ARS por producto, sin activar ni persistir versiones."""
    elegidos = {}
    for costo in costos:
        if costo.moneda == 'ARS' and (costo.producto_id not in elegidos or
                (costo.numero_version, costo.id) >
                (elegidos[costo.producto_id].numero_version, elegidos[costo.producto_id].id)):
            elegidos[costo.producto_id] = costo
    filas = []
    for costo in sorted(elegidos.values(), key=lambda c: c.producto.sku):
        try:
            precio = calcular_desde_ficha(costo, datos_productos.get(costo.producto_id))
            error = None
        except ValueError as exc:
            precio, error = None, str(exc)
        filas.append(dict(costo=costo, precio=precio, error=error))
    return filas
