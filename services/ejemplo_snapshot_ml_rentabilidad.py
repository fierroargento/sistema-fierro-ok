"""Snapshot sintético descargable: reutiliza el ejemplo de pack ya validado."""
from copy import deepcopy
from decimal import Decimal

from services.escenarios_rentabilidad_ml import escenario_rentabilidad
from services.lectura_ml_rentabilidad import FORMATO_ML


def ejemplo_snapshot_ml(*, organizacion_id, unidad_negocio_id):
    base, _ = escenario_rentabilidad('pack', organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id)
    dinero = lambda c: str(Decimal(c) / 100)
    vendedor = 'DEMO-SELLER'
    envio = 'DEMO-SHIP-1'
    lineas, ordenes, publicaciones = [], [], []
    cambio = {f['linea_id']: f"{f['order_id']}:1" for f in base['lineas']}
    for fila in base['lineas']:
        order, pub, cantidad, precio = fila['order_id'], fila['publicacion_id'], fila['cantidad'], fila['precio_unitario_centavos']
        ordenes.append({'id': order, 'status': 'paid', 'pack_id': 'DEMO-PACK-ML',
            'seller': {'id': vendedor}, 'currency_id': 'ARS', 'date_created': fila['fecha_venta'],
            'shipping': {'id': envio}, 'total_amount': dinero(precio*cantidad),
            'paid_amount': dinero(precio*cantidad), 'context': {'site': 'MLA', 'flows': []},
            'order_items': [{'item': {'id': pub, 'seller_sku': fila['sku'], 'variation_id': None},
                'quantity': cantidad, 'unit_price': dinero(precio), 'currency_id': 'ARS',
                'sale_fee': dinero(precio*15//100)}]})
        publicaciones.append({'id': pub, 'seller_id': vendedor, 'currency_id': 'ARS',
            'title': 'Publicación de ensayo ' + pub, 'price': 99999})
        lineas.append({'order_id': order, 'referencia_linea': '1', 'sku': fila['sku'],
            'costo_snapshot': deepcopy(fila['costo_snapshot']), 'previsto': deepcopy(fila['previsto'])})
    eventos = []
    for e in base['eventos']:
        if e['tipo'] not in {'comision', 'envio'}:
            evento = deepcopy(e); evento['lineas'] = [cambio[i] for i in evento['lineas']]
            eventos.append(evento)
    return {'formato': FORMATO_ML, 'organizacion_id': organizacion_id, 'unidad_negocio_id': unidad_negocio_id,
        'cuenta_codigo': base['cuenta_codigo'], 'seller_id': vendedor, 'fecha_corte': base['fecha_corte'],
        'pack': {'id': 'DEMO-PACK-ML', 'orders': [{'id': o['id']} for o in ordenes]},
        'ordenes': ordenes, 'publicaciones': publicaciones,
        'costos_envio': [{'shipment_id': envio, 'fecha': base['fecha_corte'],
            'respuesta': {'senders': [{'user_id': vendedor, 'cost': '4000'}],
                'receiver': {'cost': '9999'}}}],
        'datos_locales': {'lineas': lineas, 'eventos': eventos, 'cobertura': deepcopy(base['cobertura']),
            'gastos_locales_previstos_centavos': base['gastos_locales_previstos_centavos'],
            'cargos_ml_incluidos_en_neto': True}}
