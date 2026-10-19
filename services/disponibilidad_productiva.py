"""Disponibilidad decimal para planificación; no convierte ni mueve inventario."""
from decimal import Decimal, InvalidOperation


def cantidad_exacta(valor):
    try:
        if isinstance(valor, bool):
            raise ValueError('Cantidad no válida.')
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ValueError('Cantidad no válida.') from error
    if not numero.is_finite() or numero < 0 or numero > Decimal('1e12'):
        raise ValueError('Cantidad no válida.')
    if numero != numero.quantize(Decimal('0.000001')):
        raise ValueError('La cantidad excede seis decimales.')
    return numero


def disponibilidad_neta(existencia):
    # Ausencia de stock/reserva/bloqueo es evidencia incompleta, no cero.
    actual = cantidad_exacta(getattr(existencia, 'stock_actual', None))
    reservado = cantidad_exacta(getattr(existencia, 'stock_reservado', None))
    bloqueado = cantidad_exacta(getattr(existencia, 'stock_bloqueado', None))
    return max(Decimal('0'), actual - reservado - bloqueado)
