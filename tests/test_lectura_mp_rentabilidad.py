from copy import deepcopy
import json

import pytest

from services.archivo_rentabilidad_ml import analizar_archivo
from services.ejemplo_snapshot_mp_rentabilidad import ejemplo_snapshot_mp
from services.escenarios_rentabilidad_ml import CUENTA_ENSAYO
from test_rentabilidad_ml_routes import app, ingresar

CTX=dict(organizacion_id=1,unidad_negocio_id=3,cuenta_codigo=CUENTA_ENSAYO)


def ejemplo(): return ejemplo_snapshot_mp(organizacion_id=1,unidad_negocio_id=3)
def analizar(d): return analizar_archivo(json.dumps(d).encode(),**CTX)


def test_cuatro_pagos_y_cargos_ml_mp_no_duplican_dinero_ni_gastos():
    d=ejemplo();antes=deepcopy(d);e,r=analizar(d)
    assert d==antes
    assert r['estado']=='alcance_declarado_completo'
    assert r['totales']['resultado_centavos']==2040000
    assert r['totales']['gastos_centavos']==1360000
    assert r['liquidacion']['observada_centavos']==4190000
    assert r['fuentes_duplicadas_no_sumadas']==5
    assert len([h for h in r['hechos'] if h['tipo']=='liquidacion_neta'])==4
    assert sum(h['importe_centavos'] for h in r['hechos'] if h['tipo']=='comision')==810000
    assert sum(h['importe_centavos'] for h in r['hechos'] if h['tipo']=='envio')==400000
    traza=e['trazabilidad_mp'];assert len(traza['pagos'])==4 and len(traza['cargos'])==5
    assert all(g['estado']=='coincidente' for g in traza['cargos'])
    assert sum(p['cargos_comprador_no_imputados'] for p in traza['pagos'])==4
    assert traza['saldo_disponible']=='no_consultado' and not r['controles']['persistencia']


def test_exportacion_recalculada_es_reproducible_y_no_contiene_pagador():
    d=ejemplo();d['pagos_mp'][0]['respuesta']['payer']={'email':'privado@example.com','identification':{'number':'12345678'}}
    e,r=analizar(d);otro,rr=analizar({'entrada':e,'resultado':{'falso':True}})
    assert otro==e and rr==r
    assert 'privado@example.com' not in json.dumps(e) and 'identification' not in json.dumps(e)


@pytest.mark.parametrize('campo,valor',[('collector_id','otra'),('currency_id','USD'),('status','refunded'),('status','pending'),('operation_type','money_transfer')])
def test_cobrador_moneda_estado_y_tipo_invalidos(campo,valor):
    d=ejemplo();d['pagos_mp'][0]['respuesta'][campo]=valor
    with pytest.raises(ValueError): analizar(d)


@pytest.mark.parametrize('campo,valor',[('organizacion_id',2),('unidad_negocio_id',4),('cuenta_codigo','otra')])
def test_contexto_ajeno_se_rechaza(campo,valor):
    d=ejemplo();d['snapshot_ml'][campo]=valor
    with pytest.raises(ValueError): analizar(d)


def test_neto_ausente_no_es_cero_ni_bruto():
    d=ejemplo()
    for p in d['pagos_mp']:p['respuesta']['transaction_details'].pop('net_received_amount')
    e,r=analizar(d)
    assert r['estado']=='parcial' and r['liquidacion']['observada_centavos'] is None
    assert all(p['neto_centavos'] is None for p in e['trazabilidad_mp']['pagos'])
    assert any('Neto no informado' in x for x in r['faltantes'])


def test_neto_cero_confirmado_se_conserva_y_no_se_iguala_a_ausencia():
    d=ejemplo()
    for p in d['pagos_mp']:p['respuesta']['transaction_details']['net_received_amount']=0
    e,r=analizar(d)
    assert r['liquidacion']['observada_centavos']==0
    assert all(p['neto_centavos']==0 for p in e['trazabilidad_mp']['pagos'])
    assert r['estado']=='parcial'


def test_pago_repetido_ajeno_y_alcances_superpuestos():
    d=ejemplo();d['pagos_mp'].append(deepcopy(d['pagos_mp'][0]))
    with pytest.raises(ValueError,match='repetido'): analizar(d)
    d=ejemplo();d['pagos_mp'][0]['ordenes']=['AJENA']
    with pytest.raises(ValueError,match='ajenas'): analizar(d)
    d=ejemplo();d['pagos_mp'][0]['ordenes'].append('DEMO-ORD-2')
    with pytest.raises(ValueError,match='solapan'): analizar(d)


def test_no_asocia_pago_por_external_reference_o_importe_solo():
    d=ejemplo();d['pagos_mp'][0]['respuesta']['external_reference']='DEMO-ORD-1';d['pagos_mp'][0].pop('ordenes')
    with pytest.raises(ValueError,match='explícitamente'): analizar(d)
    d=ejemplo();d['pagos_mp'][0].pop('referencia_vinculo')
    with pytest.raises(ValueError,match='vínculo'): analizar(d)


def test_diferencia_cargo_no_sobrescribe_ml_ni_inventa_ganancia_cerrada():
    d=ejemplo();d['pagos_mp'][0]['respuesta']['fee_details'][0]['amount']='1600'
    d['pagos_mp'][0]['respuesta']['transaction_details']['net_received_amount']='7659.26'
    e,r=analizar(d)
    assert r['estado']=='parcial'
    assert r['totales']['resultado_centavos']==2040000
    assert r['liquidacion']['observada_centavos']==4180000
    assert any(g['diferencia_centavos']==10000 for g in e['trazabilidad_mp']['cargos'])
    assert r['fuentes_duplicadas_no_sumadas']==4
    assert any('Diferencia' in p for p in r['faltantes'])


def test_cargo_colector_no_vinculado_y_responsable_desconocido_quedan_pendientes():
    d=ejemplo();d['pagos_mp'][0]['respuesta']['fee_details'].append({'type':'otro','fee_payer':'collector','amount':'10'})
    _,r=analizar(d);assert r['estado']=='parcial' and any('sin vincular' in x for x in r['faltantes'])
    d=ejemplo();d['pagos_mp'][0]['respuesta']['fee_details'].append({'type':'otro','amount':'10'})
    _,r=analizar(d);assert r['estado']=='parcial' and any('Responsable' in x for x in r['faltantes'])


def test_cargo_comprador_no_puede_vincularse_al_vendedor():
    d=ejemplo();d['pagos_mp'][0]['relaciones_cargos'][0]['indice']=2
    with pytest.raises(ValueError,match='comprador'): analizar(d)


def test_cargos_detalle_alternativo_no_se_suman_y_quedan_pendientes():
    d=ejemplo();d['pagos_mp'][0]['respuesta']['charges_details']=[{'id':'x','amounts':{'original':1500,'refunded':0}}]
    _,r=analizar(d)
    assert r['estado']=='parcial' and r['totales']['gastos_centavos']==1360000
    assert any('charges_details' in x for x in r['faltantes'])


def test_fee_details_ausente_no_es_lista_vacia_confirmada():
    d=ejemplo();d['pagos_mp'][0]['respuesta'].pop('fee_details');d['pagos_mp'][0]['relaciones_cargos']=[]
    _,r=analizar(d);assert r['estado']=='parcial' and any('no informados' in x for x in r['faltantes'])


@pytest.mark.parametrize('valor',[True,-1,'NaN','Infinity','1.001','1e999999',{},[]])
def test_neto_monetario_invalido_no_hace_500(valor):
    d=ejemplo();d['pagos_mp'][0]['respuesta']['transaction_details']['net_received_amount']=valor
    with pytest.raises(ValueError): analizar(d)


def test_reintegros_estados_y_corte_no_se_omiten():
    d=ejemplo();d['pagos_mp'][0]['respuesta']['transaction_amount_refunded']='1'
    with pytest.raises(ValueError,match='reintegros'): analizar(d)
    d=ejemplo();d['pagos_mp'][0]['respuesta']['refunds']=[{'amount':'1'}]
    with pytest.raises(ValueError,match='refunds'): analizar(d)
    d=ejemplo();d['pagos_mp'][0]['respuesta']['date_last_updated']='2030-01-01T00:00:00-03:00'
    with pytest.raises(ValueError,match='corte'): analizar(d)
    d=ejemplo();d['pagos_mp'][0]['respuesta']['date_approved']='sin zona'
    with pytest.raises(ValueError,match='zona'): analizar(d)


def test_faltantes_de_origen_y_devolucion_dejan_parcial():
    d=ejemplo();p=d['pagos_mp'][0]['respuesta']
    for campo in ('transaction_amount_refunded','date_last_updated','operation_type'):p.pop(campo)
    _,r=analizar(d);assert r['estado']=='parcial'
    assert any('Devoluciones' in x for x in r['faltantes'])
    assert any('actualización' in x for x in r['faltantes'])
    assert any('Tipo de operación' in x for x in r['faltantes'])


def test_no_mezcla_cobros_locales_y_mp_ni_infieren_cargos_incluidos():
    d=ejemplo();d['snapshot_ml']['datos_locales']['eventos'].append({'tipo':'liquidacion_neta'})
    with pytest.raises(ValueError,match='No mezclar'): analizar(d)
    d=ejemplo();d['snapshot_ml']['datos_locales']['cargos_ml_incluidos_en_neto']=False
    with pytest.raises(ValueError,match='incluidos'): analizar(d)


def test_vinculos_de_cargos_repetidos_ajenos_fuera_de_rango_o_conceptos_mezclados():
    for indices in ([0,0],[99,1],[True,1]):
        d=ejemplo()
        for rel,indice in zip(d['pagos_mp'][0]['relaciones_cargos'],indices):rel['indice']=indice
        with pytest.raises(ValueError): analizar(d)
    d=ejemplo();d['pagos_mp'][0]['relaciones_cargos'][0]['hechos_ml']=['ajeno']
    with pytest.raises(ValueError,match='ajenos'): analizar(d)
    d=ejemplo();d['pagos_mp'][0]['relaciones_cargos'][0]['hechos_ml'].append('ml-envio:DEMO-SHIP-1')
    with pytest.raises(ValueError,match='conceptos'): analizar(d)


def test_importe_pago_y_ordenes_sin_cobertura_mp_muestran_parcial():
    d=ejemplo();d['pagos_mp'][0]['respuesta']['transaction_amount']='9999'
    _,r=analizar(d);assert r['estado']=='parcial' and any('importe de pagos' in x for x in r['faltantes'])
    d=ejemplo();d['pagos_mp'].pop()
    _,r=analizar(d);assert r['estado']=='parcial' and any('Órdenes ML sin' in x for x in r['faltantes'])


@pytest.mark.parametrize('pendientes',[None,'texto',[{}],[''],['x'*201],['x']*201])
def test_pendientes_fuente_invalido_no_se_ignora(pendientes):
    e,_=analizar(ejemplo());e['pendientes_fuente']=pendientes
    with pytest.raises(ValueError): analizar(e)


def test_ruta_descarga_ml_mp_render_y_rechazo(app):
    c=app.test_client();ingresar(c)
    d=c.get('/admin/comercial/rentabilidad-ml?descargar_snapshot_mp=1&cuenta_codigo=otra')
    assert d.status_code==200 and d.json['snapshot_ml']['cuenta_codigo']==CUENTA_ENSAYO
    r=c.post('/admin/comercial/rentabilidad-ml/archivo',data=d.data,content_type='application/json')
    assert r.status_code==200 and 'Snapshot ML + MP offline' in r.text
    assert 'Contraste de cobros y cargos MP' in r.text and 'Saldo disponible: no consultado' in r.text
    assert '20.400,00' in r.text and '37,78%' in r.text
    assert r.headers['Cache-Control']=='no-store'
    dato=d.json;dato['pagos_mp'][0]['respuesta']['status']='refunded'
    r=c.post('/admin/comercial/rentabilidad-ml/archivo',data=json.dumps(dato),content_type='application/json')
    assert r.status_code==400 and 'feedback-error' in r.text and 'evidencia-archivo' not in r.text


@pytest.mark.parametrize('campo',['taxes_amount','coupon_amount'])
def test_impuestos_o_cupones_no_se_descontan_por_suposicion(campo):
    d=ejemplo();d['pagos_mp'][0]['respuesta'][campo]='10.00'
    _,r=analizar(d)
    assert r['estado']=='parcial' and r['totales']['gastos_centavos']==1360000


def test_division_de_un_pago_en_dos_con_mismo_alcance_conserva_total():
    d=ejemplo();original=d['pagos_mp'][0]
    # La relación permite varias partes en el mismo alcance declarado, sin crear otras líneas ML.
    segunda=deepcopy(original);segunda['respuesta']['id']='DEMO-MP-1B'
    original['respuesta']['transaction_amount']='5000';segunda['respuesta']['transaction_amount']='5000'
    original['respuesta']['transaction_details']['net_received_amount']='3879.63'
    segunda['respuesta']['transaction_details']['net_received_amount']='3879.63'
    for pago in (original,segunda):
        pago['respuesta']['fee_details'][0]['amount']='750'
        pago['respuesta']['fee_details'][1]['amount']='370.37'
    d['pagos_mp'].append(segunda)
    _,r=analizar(d)
    assert len(r['lineas'])==4 and r['estado']=='alcance_declarado_completo'
    assert r['liquidacion']['observada_centavos']==4190000
    assert r['totales']['resultado_centavos']==2040000


def test_fuentes_ajenas_no_compensan_cargos_de_otra_orden():
    d=ejemplo();d['pagos_mp'][0]['relaciones_cargos'][0]['hechos_ml']=['ml-comision:DEMO-ORD-2:1']
    with pytest.raises(ValueError,match='líneas'): analizar(d)
