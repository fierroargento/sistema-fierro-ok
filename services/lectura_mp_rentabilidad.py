"""Contrasta pagos MP declarados con líneas y cargos ML. Sin DB, red ni saldos."""
from copy import deepcopy
from hashlib import sha256
import json

from services.lectura_ml_rentabilidad import normalizar_snapshot_ml, _id, _centavos, _lista
from services.rentabilidad_ml_offline import _entero, _fecha, _texto

FORMATO_MP = 'ml_mp_rentabilidad_offline_v1'


def normalizar_snapshot_mp(documento, *, organizacion_id, unidad_negocio_id, cuenta_codigo):
    d=deepcopy(documento)
    if d.get('formato') != FORMATO_MP or not isinstance(d.get('snapshot_ml'), dict):
        raise ValueError('El paquete MP requiere snapshot_ml y formato compatible.')
    ml=d['snapshot_ml']
    locales=ml.get('datos_locales') or {}
    if locales.get('cargos_ml_incluidos_en_neto') is not True:
        raise ValueError('Este lector requiere declarar los cargos ML incluidos en el neto MP; otro alcance necesita revisión.')
    if any(e.get('tipo') in {'liquidacion_neta','pago_bruto'} for e in _lista(locales.get('eventos',[]),'Hechos locales',1000)):
        raise ValueError('No mezclar cobros locales normalizados y snapshots MP para la misma operación.')
    entrada=normalizar_snapshot_ml(ml, organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id, cuenta_codigo=cuenta_codigo)
    collector=_id(d.get('collector_id'),'Cobrador declarado')
    if 'enlace_precio' in entrada and collector != entrada['trazabilidad_ml']['seller_declarado']:
        raise ValueError('El cobrador MP no coincide con el vendedor ML del ensayo enlazado.')
    corte=_fecha(entrada['fecha_corte'])
    filas={f['linea_id']:f for f in entrada['lineas']}
    ordenes={f['order_id'] for f in filas.values()}
    cargos={e['hecho_id']:e for e in entrada['eventos'] if e['tipo'] in {'comision','envio'}}
    pagos=_lista(d.get('pagos_mp'),'Pagos MP',200)
    if not pagos: raise ValueError('Faltan snapshots de pagos MP.')
    vistos=set(); grupos_cobro={}; propietario_orden={}; grupos_cargos={}; propietario_cargo={}
    pendientes=[]; traza_pagos=[]
    for dato in pagos:
        p=dato.get('respuesta')
        if not isinstance(p,dict): raise ValueError('Falta la respuesta del pago MP.')
        ident=_id(p.get('id'),'Pago MP')
        if ident in vistos: raise ValueError('Pago MP repetido; no se suma otra vez.')
        vistos.add(ident)
        if _id(p.get('collector_id'),'Cobrador del pago') != collector or p.get('currency_id')!='ARS':
            raise ValueError('El pago pertenece a otro cobrador declarado o moneda.')
        if p.get('status')!='approved':
            raise ValueError('Este lector requiere pagos approved; otros estados y contracargos necesitan revisión.')
        tipo_operacion=p.get('operation_type')
        if tipo_operacion is None: pendientes.append(f'Tipo de operación MP pendiente: {ident}')
        elif tipo_operacion!='regular_payment': raise ValueError('El snapshot MP no corresponde a un cobro regular; no importar transferencias como ventas.')
        fecha=p.get('date_approved'); aprobacion=_fecha(fecha)
        if aprobacion>corte: raise ValueError('El pago es posterior al corte.')
        actualizada=p.get('date_last_updated')
        if actualizada is None:
            pendientes.append(f'Fecha de actualización pendiente del pago {ident}')
        elif not aprobacion <= _fecha(actualizada) <= corte:
            raise ValueError('La actualización del pago no corresponde al corte/aprobación.')
        reembolso=p.get('transaction_amount_refunded')
        if reembolso is None: pendientes.append(f'Devoluciones no informadas del pago {ident}')
        elif _centavos(reembolso): raise ValueError('El pago tiene reintegros; requiere revisar devolución sin omitirla.')
        if p.get('refunds'): raise ValueError('El pago contiene refunds; requiere otro tratamiento de devolución.')
        if p.get('taxes_amount') is not None and _centavos(p['taxes_amount']):
            pendientes.append(f'Impuestos MP requieren revisión: {ident}')
        if p.get('coupon_amount') is not None and _centavos(p['coupon_amount']):
            pendientes.append(f'Cupón/cofinanciación pendiente del pago {ident}')
        _texto(dato.get('referencia_vinculo'),'Fuente del vínculo entre pago y órdenes')
        refs=dato.get('ordenes')
        if not isinstance(refs,list) or not refs or len(refs)>200:
            raise ValueError('El pago requiere órdenes vinculadas explícitamente.')
        refs=[_id(x,'Orden vinculada al pago') for x in refs]
        if len(refs)!=len(set(refs)) or not set(refs)<=ordenes:
            raise ValueError('El pago contiene órdenes repetidas o ajenas al alcance ML.')
        grupo=tuple(sorted(refs))
        for ref in grupo:
            if ref in propietario_orden and propietario_orden[ref]!=grupo:
                raise ValueError('Los alcances de pagos se solapan de forma ambigua; requiere revisión.')
            propietario_orden[ref]=grupo
        lineas=sorted(i for i,f in filas.items() if f['order_id'] in refs)
        if 'enlace_precio' in entrada and any(_fecha(filas[i]['fecha_venta']) > aprobacion for i in lineas):
            raise ValueError('El cobro MP es anterior a una orden vinculada; requiere revisar las fechas.')
        bruto=_centavos(p.get('transaction_amount'))
        grupos_cobro[grupo]=grupos_cobro.get(grupo,0)+bruto
        detalle=p.get('transaction_details')
        if detalle is not None and not isinstance(detalle,dict): raise ValueError('transaction_details debe ser un objeto.')
        neto=(detalle or {}).get('net_received_amount')
        neto=None if neto is None else _centavos(neto)
        if neto is None:
            pendientes.append(f'Neto no informado del pago {ident}')
        else:
            entrada['eventos'].append({'hecho_id':f'mp-neto:{ident}','tipo':'liquidacion_neta',
                'importe_centavos':neto,'direccion':'credito','lineas':lineas,
                'fuente':f'/v1/payments/{ident} · net_received_amount declarado', 'fecha':fecha,
                'estado':'observado' if neto else 'cero_confirmado', 'impacta_saldo':True,'incluido_en_neto':False})
        fees=p.get('fee_details')
        if fees is None:
            pendientes.append(f'Cargos MP no informados del pago {ident}');fees=[]
        fees=_lista(fees,'fee_details',200)
        relaciones={}
        for rel in _lista(dato.get('relaciones_cargos',[]),'Relaciones de cargos',200):
            indice=_entero(rel.get('indice'),'Índice fee_details',maximo=max(0,len(fees)-1))
            if indice>=len(fees) or indice in relaciones: raise ValueError('Relación de cargo MP repetida o fuera de rango.')
            _texto(rel.get('referencia'),'Fuente de relación del cargo')
            hechos=rel.get('hechos_ml')
            if not isinstance(hechos,list) or not hechos or len(hechos)>200 or any(not isinstance(x,str) for x in hechos):
                raise ValueError('El cargo MP requiere referencias explícitas de hechos ML.')
            if len(hechos)!=len(set(hechos)) or not set(hechos)<=set(cargos):
                raise ValueError('Un cargo MP referencia hechos ML repetidos o ajenos.')
            if len({cargos[x]['tipo'] for x in hechos})!=1:
                raise ValueError('No mezclar conceptos ML para compensar diferencias de cargos.')
            relaciones[indice]=tuple(sorted(hechos))
        ignorados=0; sin_vincular=0
        for indice,fee in enumerate(fees):
            importe=_centavos(fee.get('amount'))
            payer=fee.get('fee_payer')
            if payer=='payer':
                if indice in relaciones: raise ValueError('Un cargo del comprador no se atribuye al vendedor.')
                ignorados+=1;continue
            if payer!='collector':
                if indice in relaciones: raise ValueError('Falta responsable confirmado para vincular el cargo MP.')
                pendientes.append(f'Responsable de cargo MP pendiente: {ident}/{indice}');continue
            grupo_cargo=relaciones.get(indice)
            if grupo_cargo is None:
                sin_vincular+=1;pendientes.append(f'Cargo MP sin vincular: {ident}/{indice}');continue
            alcance=set(i for h in grupo_cargo for i in cargos[h]['lineas'])
            if not alcance.intersection(lineas): raise ValueError('El cargo no corresponde a las líneas del pago declarado.')
            for hecho in grupo_cargo:
                if hecho in propietario_cargo and propietario_cargo[hecho]!=grupo_cargo:
                    raise ValueError('Un hecho ML participa en grupos de cargos MP incompatibles.')
                propietario_cargo[hecho]=grupo_cargo
            g=grupos_cargos.setdefault(grupo_cargo,{'importe':0,'lineas':set(),'fuentes':[]})
            g['importe']+=importe;g['lineas'].update(set(lineas)&alcance)
            g['fuentes'].append({'pago_id':ident,'indice':indice,'importe_centavos':importe,'referencia':dato['referencia_vinculo'],
                'referencia_cargo':next(r['referencia'] for r in dato['relaciones_cargos'] if r['indice']==indice)})
        if p.get('charges_details'):
            pendientes.append(f'charges_details pendiente de clasificación: {ident}')
        traza_pagos.append({'id':ident,'ordenes':list(grupo),'bruto_centavos':bruto,'neto_centavos':neto,
            'fecha_aprobacion':fecha,'fecha_actualizacion':actualizada,'estado':'approved',
            'referencia_vinculo':dato['referencia_vinculo'],'cargos_comprador_no_imputados':ignorados,
            'cargos_sin_vincular':sin_vincular})
    faltan=ordenes-set(propietario_orden)
    if faltan: pendientes.append('Órdenes ML sin evidencia MP completa')
    for grupo,total in grupos_cobro.items():
        esperado=sum(f['cantidad']*f['precio_unitario_centavos'] for f in filas.values() if f['order_id'] in grupo)
        if total!=esperado: pendientes.append('Diferencia entre importe de pagos MP y líneas ML vinculadas')
    if set(cargos)-set(propietario_cargo): pendientes.append('Cargos ML sin contraste MP completo')
    traza_cargos=[]
    for pos,(hechos,g) in enumerate(sorted(grupos_cargos.items()),1):
        esperado=sum(cargos[h]['importe_centavos'] for h in hechos)
        alcance={i for h in hechos for i in cargos[h]['lineas']}
        coincide=g['importe']==esperado and g['lineas']==alcance
        if not coincide: pendientes.append(f'Diferencia o alcance incompleto del grupo MP {pos}')
        else:
            # Fuente agregada del MISMO hecho económico; el motor ya evita sumarlo dos veces.
            huella=sha256(json.dumps(g['fuentes'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            for h in hechos:
                espejo=deepcopy(cargos[h]);espejo['fuente']=f'MP fee_details · grupo {pos} contrastado · {huella[:16]}'
                entrada['eventos'].append(espejo)
        traza_cargos.append({'grupo':pos,'hechos_ml':list(hechos),'importe_ml_centavos':esperado,
            'importe_mp_centavos':g['importe'],'diferencia_centavos':g['importe']-esperado,
            'estado':'coincidente' if coincide else 'requiere_revision','fuentes':g['fuentes']})
    entrada['pendientes_fuente']=sorted(set(entrada.get('pendientes_fuente',[]) + pendientes))
    entrada['trazabilidad_mp']={'formato':FORMATO_MP,'collector_declarado':collector,
        'huella_snapshot':sha256(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),
        'pagos':traza_pagos,'cargos':traza_cargos,'saldo_disponible':'no_consultado',
        'advertencias':['Vínculos, cobrador y snapshots declarados: no acredita autenticidad externa.',
            'Neto de pago no equivale a saldo disponible ni a transferencia bancaria.',
            'Los cargos contrastados se vinculan al hecho ML existente, sin otro descuento.',
            'Diferencias o cargos sin clasificar dejan el resultado parcial; no se modifican gastos para forzar coincidencia.',
            'No se importan todavía reportes de cuenta/liberación, contracargos ni reintegros MP.']}
    return entrada
