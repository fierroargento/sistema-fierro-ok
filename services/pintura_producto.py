"""Estimación de polvo por superficie desarrollada, nunca por volumen exterior."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
import unicodedata


def positivo(valor, nombre):
    try:
        n = Decimal(str(valor).replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise ValueError(f'{nombre}: ingresá un número mayor que cero.') from None
    if not n.is_finite() or n <= 0 or n > Decimal('1000000'):
        raise ValueError(f'{nombre}: ingresá un número mayor que cero y hasta 1000000.')
    return n


def _pulgadas(texto):
    if '/' in texto:
        a, b = texto.split('/')
        return Decimal(a) / Decimal(b) * Decimal('0.0254')
    return Decimal(texto.replace(',', '.')) * Decimal('0.0254')


def superficie_pieza(pieza, nombre):
    """Planchuelas en pulgadas y redondos DN en mm; incluye caras y cantos.

    Solo reconoce formatos inequívocos del catálogo. Otros materiales requieren
    superficie manual del producto. Tornillos y tarugos no se pintan.
    """
    nombre = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode().upper()
    if nombre.startswith(('TORNILLO ', 'TARUGO ')):
        return Decimal(0)
    if pieza.get('modo') != 'longitud':
        raise ValueError(f'Faltan medidas para estimar la pintura de {nombre}. Completá la superficie manual del producto.')
    largo = positivo(pieza['largo_cm'], 'Largo') / 100
    cantidad = positivo(pieza['cantidad'], 'Cantidad')
    medida = r'(\d+/\d+|\d+(?:[.,]\d+)?)'
    plana = re.search(r'PLANCHUELA\s+' + medida + r'\s*[Xx]\s*' + medida + r'\s*(?:\"|\b)', nombre)
    redondo = re.search(r'(?:REDONDO|TORSIONADO)\s+DN\s*' + medida + r'\s*MM\b', nombre)
    if plana and re.match(r'\s*(?:MM|CM)\b', nombre[plana.end():]):
        plana = None
    if plana:
        try:
            ancho, espesor = (_pulgadas(v) for v in plana.groups())
        except (InvalidOperation, ZeroDivisionError):
            raise ValueError('Revisá las medidas de la planchuela.') from None
        if ancho <= 0 or espesor <= 0:
            raise ValueError('Revisá las medidas de la planchuela.')
        return cantidad * (2 * largo * (ancho + espesor) + 2 * ancho * espesor)
    if redondo:
        diametro = positivo(redondo.group(1), 'Diámetro') / 1000
        pi = Decimal('3.141592653589793')
        return cantidad * (pi * diametro * largo + pi * diametro ** 2 / 2)
    raise ValueError(f'Faltan medidas para estimar la pintura de {nombre}. Completá la superficie manual del producto.')


def calcular(config, piezas):
    """piezas: pares de pieza validada y nombre de material autorizado."""
    rendimiento = positivo(config.get('rendimiento_m2_kg', '10'), 'Rendimiento de pintura')
    manual = str(config.get('superficie_manual_m2') or '').strip()
    superficie = positivo(manual, 'Superficie a pintar') if manual else sum(
        (superficie_pieza(p, nombre) for p, nombre in piezas), Decimal(0))
    if superficie <= 0:
        raise ValueError('No hay superficie para pintar. Revisá los componentes o completá la superficie manual.')
    kg = (superficie / rendimiento).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    if kg <= 0:
        raise ValueError('El consumo estimado de pintura es demasiado pequeño.')
    return superficie, kg, rendimiento
