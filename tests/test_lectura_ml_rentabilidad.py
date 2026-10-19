from copy import deepcopy
import json

import pytest

from services.archivo_rentabilidad_ml import analizar_archivo
from services.ejemplo_snapshot_ml_rentabilidad import ejemplo_snapshot_ml
from services.escenarios_rentabilidad_ml import CUENTA_ENSAYO
from test_rentabilidad_ml_routes import app, ingresar

CTX=dict(organizacion_id=1, unidad_negocio_id=3, cuenta_codigo=CUENTA_ENSAYO)


def ejemplo(): return ejemplo_snapshot_ml(organizacion_id=1,unidad_negocio_id=3)
def analizar(d): return analizar_archivo(json.dumps(d).encode(),**CTX)


def test_pack_financiero_conserva_lineas_precios_y_envio_unico():
    d=ejemplo();antes=deepcopy(d);e,r=analizar(d)
    assert d==antes
    assert len(e['lineas'])==4 and sum(x['cantidad'] for x in e['lineas'])==5
    sku_a=[x for x in e['lineas'] if x['sku']=='DEMO-SKU-A']
    assert [x['precio_unitario_centavos'] for x in sku_a]==[1000000,900000]
    assert r['totales']['resultado_centavos']==2040000
    assert r['liquidacion']['observada_centavos']==4190000
    assert r['estado']=='alcance_declarado_completo'
    assert sum(x['importe_centavos'] for x in r['hechos'] if x['tipo']=='envio')==400000
    assert sum(x['importe_centavos'] for f in r['lineas'] for x in f['componentes'] if x['concepto']=='envio')==400000
    assert sum(x['importe_centavos'] for x in r['hechos'] if x['tipo']=='comision')==810000
    assert len(e['trazabilidad_ml']['huella_snapshot'])==64
    assert r['controles']['conexiones_externas']==0 and not r['controles']['persistencia']


@pytest.mark.parametrize('campo', ['price', 'original_price'])
def test_precio_actual_no_reescribe_historia(campo):
    d=ejemplo();_,r=analizar(d)
    d['publicaciones'][0][campo]='1.00'
    _,nuevo=analizar(d)
    assert nuevo['totales']==r['totales']


def test_paid_amount_y_payments_no_son_neto_ni_generan_cobro():
    d=ejemplo()
    for o in d['ordenes']:
        o['paid_amount']=99999999;o['payments']=[{'transaction_amount':99999999,'status':'approved'}]
    d['datos_locales']['eventos']=[x for x in d['datos_locales']['eventos'] if x['tipo']!='liquidacion_neta']
    _,r=analizar(d)
    assert r['liquidacion']['observada_centavos'] is None
    assert r['estado']=='parcial' and 'Cobro observado' in r['faltantes']


@pytest.mark.parametrize('valor',[None,True,-1,'NaN','Infinity','1.001','1e999999','1e-999999','1.000000000000000000000000001',{},[], 'no'])
def test_precio_invalido_no_se_redondea_ni_reemplaza_por_cero(valor):
    d=ejemplo();d['ordenes'][0]['order_items'][0]['unit_price']=valor
    with pytest.raises(ValueError): analizar(d)


@pytest.mark.parametrize('campo,valor',[('organizacion_id',2),('unidad_negocio_id',4),('cuenta_codigo','otra')])
def test_snapshot_ajeno_no_adapta(campo,valor):
    d=ejemplo();d[campo]=valor
    with pytest.raises(ValueError): analizar(d)


def test_pack_incompleto_repetido_y_orden_ajena():
    d=ejemplo();d['ordenes'].pop()
    with pytest.raises(ValueError,match='incompleto'): analizar(d)
    d=ejemplo();d['ordenes'].append(deepcopy(d['ordenes'][0]))
    with pytest.raises(ValueError,match='repetida'): analizar(d)
    d=ejemplo();d['ordenes'][0]['pack_id']='otro'
    with pytest.raises(ValueError,match='pack'): analizar(d)


@pytest.mark.parametrize('campo,valor',[('status','cancelled'),('status','invalid'),('status','partially_refunded'),('currency_id','BRL')])
def test_no_omite_estados_o_moneda_incompatibles(campo,valor):
    d=ejemplo();d['ordenes'][0][campo]=valor
    with pytest.raises(ValueError): analizar(d)


def test_vendedor_publicacion_orden_y_site():
    d=ejemplo();d['ordenes'][0]['seller']['id']='otro'
    with pytest.raises(ValueError,match='vendedor'): analizar(d)
    d=ejemplo();d['publicaciones'][0]['seller_id']='otro'
    with pytest.raises(ValueError,match='vendedor'): analizar(d)
    d=ejemplo();d['ordenes'][0]['context']['site']='MLB'
    with pytest.raises(ValueError,match='MLA'): analizar(d)


def test_ausencia_fee_envio_y_costo_no_inventa_ceros():
    d=ejemplo();d['ordenes'][0]['order_items'][0].pop('sale_fee')
    _,r=analizar(d);assert r['estado']=='parcial' and 'comision' in r['faltantes']
    d=ejemplo();d['costos_envio'][0]['respuesta']['senders']=[]
    _,r=analizar(d);assert r['estado']=='parcial' and 'envio' in r['faltantes']
    d=ejemplo();d['datos_locales']['lineas'][0].pop('costo_snapshot')
    _,r=analizar(d);assert r['estado']=='no_calculable' and r['totales']['resultado_centavos'] is None


def test_envio_cero_confirmado_difiere_de_ausente_y_receiver_no_es_costo_seller():
    d=ejemplo();d['costos_envio'][0]['respuesta']['senders'][0]['cost']='0'
    _,r=analizar(d)
    envio=next(x for x in r['hechos'] if x['tipo']=='envio')
    assert envio['importe_centavos']==0 and envio['estado']=='cero_confirmado'
    assert next(x for x in r['cobertura'] if x['concepto']=='envio')['estado']=='confirmado'


def test_fee_cero_es_confirmado_y_fee_por_unidad_se_multiplica():
    d=ejemplo();d['ordenes'][1]['order_items'][0]['sale_fee']='0'
    _,r=analizar(d)
    assert sum(x['importe_centavos'] for x in r['hechos'] if x['tipo']=='comision')==450000


def test_envio_repetido_ajeno_o_sender_ambiguo_rechazados():
    d=ejemplo();d['costos_envio'].append(deepcopy(d['costos_envio'][0]))
    with pytest.raises(ValueError,match='repetido'): analizar(d)
    d=ejemplo();d['costos_envio'][0]['shipment_id']='otro'
    with pytest.raises(ValueError,match='ajeno'): analizar(d)
    d=ejemplo();senders=d['costos_envio'][0]['respuesta']['senders'];senders.append(deepcopy(senders[0]))
    with pytest.raises(ValueError,match='ambiguo'): analizar(d)


def test_fechas_incompatibles_y_costo_actual_incorrecto_rechazados():
    d=ejemplo();d['costos_envio'][0]['fecha']='2030-01-01T00:00:00-03:00'
    with pytest.raises(ValueError,match='corte'): analizar(d)
    d=ejemplo();d['datos_locales']['lineas'][0]['costo_snapshot']['vigente_desde']='2030-01-01T00:00:00-03:00'
    with pytest.raises(ValueError,match='costo'): analizar(d)


def test_b2b_solo_etiqueta_no_eligibilidad_y_descuentos_no_se_restaan_otra_vez():
    d=ejemplo();d['ordenes'][0]['context']['flows']=['b2b']
    d['ordenes'][0]['order_items'][0]['gross_price']='12000'
    e,r=analizar(d)
    assert e['trazabilidad_ml']['ordenes'][0]['tipo']=='b2b'
    assert e['trazabilidad_ml']['ordenes'][1]['tipo']=='no_determinado'
    assert r['totales']['resultado_centavos']==2040000
    assert r['estado']=='parcial' and 'descuentos' in r['faltantes']


def test_sku_faltante_requiere_vinculo_y_discrepancia_rechazada():
    d=ejemplo();d['ordenes'][0]['order_items'][0]['item'].pop('seller_sku')
    assert analizar(d)[0]['lineas'][0]['sku']=='DEMO-SKU-A'
    d['datos_locales']['lineas'][0].pop('sku')
    with pytest.raises(ValueError,match='SKU'): analizar(d)
    d=ejemplo();d['datos_locales']['lineas'][0]['sku']='otro'
    with pytest.raises(ValueError,match='SKU'): analizar(d)


def test_hechos_ml_duplicados_y_relacion_neto_no_inferida():
    d=ejemplo();d['datos_locales']['eventos'].append({'tipo':'comision'})
    with pytest.raises(ValueError,match='duplicarlos'): analizar(d)
    d=ejemplo();d['datos_locales'].pop('cargos_ml_incluidos_en_neto')
    with pytest.raises(ValueError,match='no se infiere'): analizar(d)
    d=ejemplo();d['datos_locales']['cargos_ml_incluidos_en_neto']=False
    _,r=analizar(d)
    assert r['estado']=='parcial' and r['liquidacion']['diferencia_detalle_centavos']!=0


def test_orden_individual_con_varias_lineas_y_variante():
    d=ejemplo();o=d['ordenes'][0];o['pack_id']=None
    o['order_items'].append(deepcopy(o['order_items'][0]));o['order_items'][1]['item']['variation_id']='VAR-2'
    o['total_amount']='20000';d['ordenes']=[o];d['pack']=None;d['publicaciones']=d['publicaciones'][:1]
    d['datos_locales']['lineas']=d['datos_locales']['lineas'][:1]
    d['datos_locales']['eventos']=[]
    e,r=analizar(d)
    assert len(e['lineas'])==2 and e['lineas'][1]['variante_id']=='VAR-2'
    assert r['estado']=='no_calculable'


def test_publicacion_ausente_vinculo_ajeno_total_incompatible():
    d=ejemplo();d['publicaciones'].pop()
    with pytest.raises(ValueError,match='publicación'): analizar(d)
    d=ejemplo();d['datos_locales']['lineas'][0]['order_id']='extra'
    with pytest.raises(ValueError,match='ajenos'): analizar(d)
    d=ejemplo();d['ordenes'][0]['total_amount']='999'
    with pytest.raises(ValueError,match='total'): analizar(d)


def test_lectura_ml_y_descarga_ejemplo_en_misma_pantalla(app):
    c=app.test_client();ingresar(c)
    descarga=c.get('/admin/comercial/rentabilidad-ml?descargar_snapshot_ml=1&unidad_negocio_id=4')
    assert descarga.status_code==200 and descarga.json['unidad_negocio_id']==3
    r=c.post('/admin/comercial/rentabilidad-ml/archivo',data=descarga.data,content_type='application/json')
    assert r.status_code==200
    assert 'Snapshot ML offline' in r.text and '37,78%' in r.text
    assert 'Origen y alcance del archivo ML' in r.text
    assert 'No determinado' in r.text and '20.400,00' in r.text
    d=ejemplo();d['ordenes'].pop()
    r=c.post('/admin/comercial/rentabilidad-ml/archivo',data=json.dumps(d),content_type='application/json')
    assert r.status_code==400 and 'feedback-error' in r.text
    assert 'evidencia-archivo' not in r.text


def test_exportacion_normalizada_se_puede_releer_sin_reaplicar_cargos():
    entrada,resultado=analizar(ejemplo())
    e,r=analizar({'entrada':entrada,'resultado':{'totales':'falso'}})
    assert e==entrada and r==resultado


def test_dos_envios_con_alcance_distinto_no_se_cobran_a_todas_las_lineas():
    d=ejemplo();d['ordenes'][2]['shipping']['id']='DEMO-SHIP-2';d['ordenes'][3]['shipping']['id']='DEMO-SHIP-2'
    d['costos_envio'][0]['respuesta']['senders'][0]['cost']='3000'
    otro=deepcopy(d['costos_envio'][0]);otro['shipment_id']='DEMO-SHIP-2';otro['respuesta']['senders'][0]['cost']='1000'
    d['costos_envio'].append(otro)
    e,r=analizar(d)
    envios=[x for x in r['hechos'] if x['tipo']=='envio']
    assert len(envios)==2 and set(envios[0]['lineas']).isdisjoint(envios[1]['lineas'])
    assert sum(x['importe_centavos'] for x in envios)==400000
    assert r['totales']['resultado_centavos']==2040000
