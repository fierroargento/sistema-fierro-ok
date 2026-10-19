"""Equivalencias explícitas e inmutables del SKU de materia prima existente."""
import json

from services.disponibilidad_productiva import cantidad_exacta

PRECISIONES = {'unidad': 1, 'milesimas': 1000, 'millonesimas': 1000000}
LIMITE_ENTERO = 2147483647


def definir_unidad(unidad, precision='unidad'):
    unidad = str(unidad or '').strip()
    if not unidad or len(unidad) > 30 or precision not in PRECISIONES:
        raise ValueError('La unidad o precisión de inventario no es válida.')
    factor = PRECISIONES[precision]
    nombres = {('kg', 1000): 'g', ('m', 1000): 'mm', ('litro', 1000): 'ml', ('l', 1000): 'ml'}
    etiqueta = unidad if factor == 1 else nombres.get((unidad.lower(), factor),
        ('Milésima de ' if factor == 1000 else 'Millonésima de ') + unidad)
    return {'unidad_medida': unidad, 'precision_inventario': precision,
        'factor_inventario': factor, 'unidad_inventario': etiqueta, 'version_unidad': 1}


def leer_unidad_item(item):
    if item is None or item.tipo != 'insumo':
        raise ValueError('La unidad requiere un SKU de materia prima.')
    try:
        datos = json.loads(item.atributos_json or '{}')
        if not isinstance(datos, dict): raise ValueError('Atributos inválidos')
        unidad = definir_unidad(datos.get('unidad_medida'), datos.get('precision_inventario', 'unidad'))
        factor = datos.get('factor_inventario', 1)
        version = datos.get('version_unidad', 1)
        if (type(factor) is not int or factor != unidad['factor_inventario']
                or type(version) is not int or version != 1):
            raise ValueError('Factor incompatible')
        ident = datos['insumo_productivo_id']
        if isinstance(ident, bool) or not isinstance(ident, int) or ident <= 0:
            raise ValueError('Insumo no válido')
        unidad['insumo_productivo_id'] = ident
        return unidad
    except (ValueError, TypeError, KeyError) as error:
        raise ValueError('La unidad del SKU de materia prima requiere revisión.') from error


def texto_unidad(item):
    if item is None or getattr(item, 'tipo', None) != 'insumo': return 'unidad'
    try: return leer_unidad_item(item)['unidad_inventario']
    except ValueError: return 'Unidad sin verificar'


def convertir_cantidad(mapeo, cantidad, *, unidad_origen=None):
    insumo = mapeo.insumo
    existencia = mapeo.existencia
    if insumo is None or existencia is None:
        raise ValueError('Falta el insumo o la existencia de la equivalencia.')
    item = getattr(existencia, 'item_inventario', None)
    unidad = leer_unidad_item(item)
    if (insumo.id != mapeo.insumo_id or unidad['insumo_productivo_id'] != insumo.id
            or insumo.organizacion_id != mapeo.organizacion_id
            or insumo.unidad_negocio_id not in (None, mapeo.unidad_negocio_id)
            or existencia.organizacion_id != mapeo.organizacion_id
            or item.organizacion_id != mapeo.organizacion_id
            or item.producto_id != existencia.producto_id):
        raise ValueError('La equivalencia no pertenece al insumo y contexto del mapeo.')
    if str(insumo.unidad_medida).strip().casefold() != unidad['unidad_medida'].casefold():
        raise ValueError('La unidad del insumo cambió después de preparar el SKU.')
    if unidad_origen is not None and str(unidad_origen).strip().casefold() != unidad['unidad_medida'].casefold():
        raise ValueError('La unidad de compra no coincide con la unidad del insumo; no se convierte por suposición.')
    original = cantidad_exacta(cantidad)
    base = original * unidad['factor_inventario']
    if base > LIMITE_ENTERO:
        raise ValueError('La cantidad convertida supera el límite de inventario; revisá su unidad base.')
    return {**unidad, 'cantidad_insumo': format(original.normalize(), 'f'),
        'cantidad_inventario': format(base.normalize(), 'f'),
        'representable': base == base.to_integral_value()}


def convertir_compra(mapeo, cantidad, unidad_origen, organizacion_id, unidad_negocio_id):
    if (mapeo.organizacion_id != organizacion_id or mapeo.unidad_negocio_id != unidad_negocio_id):
        raise ValueError('El mapeo no pertenece al contexto de la recepción.')
    if not unidad_origen:
        raise ValueError('Falta verificar la unidad de la compra antes de proponer inventario.')
    conversion = convertir_cantidad(mapeo, cantidad, unidad_origen=unidad_origen)
    if not conversion['representable']:
        raise ValueError('La cantidad no es representable en la unidad base del SKU; no se redondea.')
    return conversion


def mapeos_unicos(mapeos):
    candidatos = {}
    for item in mapeos:
        if item.activo:
            candidatos.setdefault((item.organizacion_id, item.unidad_negocio_id, int(item.insumo_id)), []).append(item)
    return {clave: lista[0] for clave, lista in candidatos.items() if len(lista) == 1}
