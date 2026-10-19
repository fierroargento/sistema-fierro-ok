"""Ejemplo ML+MP reutilizando pack, costos y reparto ya validados."""
from decimal import Decimal
from services.ejemplo_snapshot_ml_rentabilidad import ejemplo_snapshot_ml
from services.lectura_ml_rentabilidad import normalizar_snapshot_ml
from services.lectura_mp_rentabilidad import FORMATO_MP
from services.rentabilidad_ml_offline import _repartir


CASOS_SNAPSHOT_MP = {
    'completo': 'Cobros y cargos',
    'sin_neto': 'Neto pendiente',
    'cargo_diferente': 'Cargo con diferencia',
}


def ejemplo_snapshot_mp(*, organizacion_id, unidad_negocio_id, caso='completo'):
    if caso not in CASOS_SNAPSHOT_MP:
        raise ValueError('Elegí uno de los ejemplos MP disponibles.')
    ml=ejemplo_snapshot_ml(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id)
    ml['datos_locales']['eventos']=[e for e in ml['datos_locales']['eventos'] if e['tipo'] not in {'pago_bruto','liquidacion_neta'}]
    normal=normalizar_snapshot_ml(ml,organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,cuenta_codigo=ml['cuenta_codigo'])
    pesos={f['linea_id']:f['cantidad']*f['precio_unitario_centavos'] for f in normal['lineas']}
    envio=next(e for e in normal['eventos'] if e['tipo']=='envio')
    reparto=_repartir(envio['importe_centavos'],envio['lineas'],pesos)
    dinero=lambda c:str(Decimal(c)/100)
    pagos=[]
    for pos,f in enumerate(normal['lineas'],1):
        comision=next(e for e in normal['eventos'] if e['tipo']=='comision' and e['lineas']==[f['linea_id']])
        bruto=pesos[f['linea_id']];fee=comision['importe_centavos'];shipping=reparto[f['linea_id']]
        pagos.append({'ordenes':[f['order_id']],'referencia_vinculo':'Vínculo sintético por orden original',
            'respuesta':{'id':f'DEMO-MP-{pos}','collector_id':'DEMO-SELLER','currency_id':'ARS',
                'status':'approved','operation_type':'regular_payment','date_approved':normal['fecha_corte'],'date_last_updated':normal['fecha_corte'],
                'transaction_amount':dinero(bruto),'transaction_amount_refunded':0,'refunds':[],
                'transaction_details':{'net_received_amount':dinero(bruto-fee-shipping)},
                'fee_details':[{'type':'mercadopago_fee','fee_payer':'collector','amount':dinero(fee)},
                    {'type':'shipping_fee','fee_payer':'collector','amount':dinero(shipping)},
                    {'type':'financing_fee','fee_payer':'payer','amount':'1.23'}]},
            'relaciones_cargos':[{'indice':0,'hechos_ml':[comision['hecho_id']], 'referencia':'Mismo cargo sintético de comisión'},
                {'indice':1,'hechos_ml':[envio['hecho_id']], 'referencia':'Porción sintética del único envío compartido'}]})
    if caso == 'sin_neto':
        # Ausencia de evidencia, no un cobro de cero ni el importe bruto.
        for pago in pagos:
            pago['respuesta']['transaction_details'].pop('net_received_amount')
    elif caso == 'cargo_diferente':
        # MP declara $100 más de comisión y $100 menos de neto en la primera orden.
        # El lector mantiene la evidencia ML para revisión; no fuerza su coincidencia.
        pago = pagos[0]['respuesta']
        pago['fee_details'][0]['amount'] = '1600.00'
        pago['transaction_details']['net_received_amount'] = '7659.26'
    return {'formato':FORMATO_MP,'snapshot_ml':ml,'collector_id':'DEMO-SELLER','pagos_mp':pagos}
