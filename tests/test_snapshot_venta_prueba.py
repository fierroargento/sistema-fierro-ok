"""Puente completo: fuentes de costo/precio -> snapshots ML/MP -> analizador."""
from copy import deepcopy
from datetime import timedelta
import json

import pytest

from services.snapshot_venta_prueba import snapshot_venta_prueba
from services.venta_prueba_precio import preparar_venta_prueba, CUENTA
from services.archivo_rentabilidad_ml import analizar_archivo
from test_venta_prueba_precio import producto_uat
from test_cobertura_precio_publicacion import fila, guardar
from test_enlace_economico_producto import AHORA


def preparar(caso='completo', *, envio_mayor=False, embalaje=10000, modo='adicional'):
    datos = producto_uat()
    guardar(fila(datos), adicional_centavos=embalaje if modo=='adicional' else 0,
        modo_embalaje=modo, detalle_ids=[11] if modo=='incluido' else [])
    entrada = preparar_venta_prueba(fila(datos), ahora=AHORA,
        caso='envio_mayor' if envio_mayor else 'previsto')
    return snapshot_venta_prueba(entrada, caso=caso)


def analizar(snapshot):
    return analizar_archivo(json.dumps(snapshot).encode(), organizacion_id=1,
        unidad_negocio_id=2, cuenta_codigo=CUENTA)


def test_paquete_coincidente_no_duplica_comision_envio_o_embalaje():
    p = preparar()
    antes = deepcopy(p)
    entrada, r = analizar(p)
    assert p == antes
    assert r['totales']['costo_centavos']==493365
    assert r['totales']['gastos_centavos']==76900
    assert r['totales']['resultado_centavos']==98735
    assert r['totales']['diferencia_resultado_centavos']==0
    assert r['fuentes_duplicadas_no_sumadas']==2
    assert r['liquidacion']['observada_centavos']==602100
    assert r['liquidacion']['diferencia_detalle_centavos']==0
    assert r['enlace_precio']['neto_cobrado_despues_locales_centavos']==592100
    assert r['enlace_precio']['neto_ensayo_centavos']==592100
    assert r['enlace_precio']['desde_snapshot']
    assert r['enlace_precio']['estado']=='cubre_minimo'
    assert not r['enlace_precio']['definitivo']
    assert r['estado']=='parcial' and 'impuestos' in r['faltantes']
    assert len(entrada['trazabilidad_mp']['cargos'])==2
    assert all(g['estado']=='coincidente' for g in entrada['trazabilidad_mp']['cargos'])
    assert r['controles']==dict(persistencia=False, conexiones_externas=0,stock=0,pagos=0,publicaciones=0)


def test_caso_staging_con_embalaje_500_y_envio_adicional_500():
    _, r = analizar(preparar(envio_mayor=True,embalaje=50000))
    e=r['enlace_precio']
    assert e['precio_minimo_centavos']==713500
    assert e['neto_previsto_centavos']==592150
    assert e['neto_ensayo_centavos']==e['neto_cobrado_despues_locales_centavos']==542150
    assert e['diferencia_minimo_centavos']==-49950
    assert e['diferencia_previsto_centavos']==-50000
    assert e['estado']=='bajo_minimo'
    assert r['totales']['resultado_centavos']==48785


def test_neto_ausente_permanece_pendiente_no_se_reemplaza_por_bruto():
    _,r=analizar(preparar('sin_neto'))
    assert r['liquidacion']['observada_centavos'] is None
    assert r['enlace_precio']['neto_cobrado_despues_locales_centavos'] is None
    assert r['enlace_precio']['estado']=='requiere_revision'
    assert any('Falta el neto' in x for x in r['enlace_precio']['problemas_cobro'])
    assert r['enlace_precio']['diferencia_minimo_centavos'] is None
    assert r['totales']['diferencia_resultado_centavos'] is None
    # La previsión y el detalle parcial se conservan; no son prueba de cobro.
    assert r['enlace_precio']['neto_previsto_centavos']==592100


def test_comision_diferente_no_se_suma_otro_descuento_para_forzar_coincidencia():
    _,r=analizar(preparar('cargo_diferente'))
    assert r['enlace_precio']['estado']=='requiere_revision'
    assert r['enlace_precio']['neto_cobrado_despues_locales_centavos']==582100
    assert r['liquidacion']['diferencia_detalle_centavos']==-10000
    assert r['totales']['gastos_centavos']==76900
    assert r['totales']['resultado_centavos']==98735  # Parcial según detalle ML; no se lo disfraza de final.
    assert r['totales']['diferencia_resultado_centavos'] is None
    assert r['enlace_precio']['diferencia_previsto_centavos'] is None
    assert r['fuentes_duplicadas_no_sumadas']==1  # Solo el envío coincide.
    assert any('diferencias' in x for x in r['enlace_precio']['problemas_cobro'])


@pytest.mark.parametrize('modo',['incluido','sin_costo'])
def test_modos_sin_embalaje_adicional_no_generan_otra_deduccion(modo):
    _,r=analizar(preparar(modo=modo))
    assert r['enlace_precio']['neto_cobrado_despues_locales_centavos']==592110
    assert r['totales']['diferencia_resultado_centavos']==0
    assert r['enlace_precio']['estado']=='cubre_minimo'


@pytest.mark.parametrize('caso',['completo','sin_neto','cargo_diferente'])
def test_relectura_normalizada_o_raw_conserva_snapshot_y_recalcula_resultado(caso):
    raw=preparar(caso,embalaje=50000)
    entrada,original=analizar(raw)
    for payload in (raw, entrada):
        _,r=analizar({'entrada':payload,'resultado':{'estado':'cubre_minimo','totales':{'costo_centavos':0}}})
        assert r==original


@pytest.mark.parametrize('cambio',['seller','collector','fecha_pago','fecha_orden','sku','publicacion','variante',
    'cantidad','costo','prevision','huella','otra_unidad','otra_cuenta'])
def test_fuentes_o_vinculos_ajenos_no_se_asignan_por_aproximacion(cambio):
    p=preparar();ml=p['snapshot_ml'];o=ml['ordenes'][0];pago=p['pagos_mp'][0]['respuesta']
    if cambio=='seller':o['seller']['id']='OTRO'
    if cambio=='collector':p['collector_id']=pago['collector_id']='OTRO'
    if cambio=='fecha_pago':pago['date_approved']=(AHORA-timedelta(seconds=1)).isoformat()+'Z'
    if cambio=='fecha_orden':o['date_created']=(AHORA-timedelta(seconds=1)).isoformat()+'Z'
    if cambio=='sku':o['order_items'][0]['item']['seller_sku']='OTRO'
    if cambio=='publicacion':o['order_items'][0]['item']['id']='OTRA'
    if cambio=='variante':o['order_items'][0]['item']['variation_id']='OTRA'
    if cambio=='cantidad':o['order_items'][0]['quantity']=2
    if cambio=='costo':ml['datos_locales']['lineas'][0]['costo_snapshot']['unitario_centavos']+=1
    if cambio=='prevision':ml['datos_locales']['lineas'][0]['previsto']['liquidacion_centavos']+=1
    if cambio=='huella':ml['datos_locales']['enlace_precio']['huella_snapshot']='otra'
    if cambio=='otra_unidad':ml['unidad_negocio_id']=9
    if cambio=='otra_cuenta':ml['cuenta_codigo']='CUENTA-UAT'
    with pytest.raises(ValueError):analizar(p)


@pytest.mark.parametrize('cambio',['sin_contraste_mp','sin_fees','comision_ml_ausente','embalaje_estimado'])
def test_importes_aparentemente_suficientes_no_producen_verde_sin_evidencia(cambio):
    p=preparar()
    if cambio=='sin_contraste_mp':p=p['snapshot_ml']
    if cambio=='sin_fees':p['pagos_mp'][0]['respuesta'].pop('fee_details');p['pagos_mp'][0]['relaciones_cargos']=[]
    if cambio=='comision_ml_ausente':
        p['snapshot_ml']['ordenes'][0]['order_items'][0].pop('sale_fee')
        p['pagos_mp'][0]['relaciones_cargos']=p['pagos_mp'][0]['relaciones_cargos'][1:]
    if cambio=='embalaje_estimado':
        next(e for e in p['snapshot_ml']['datos_locales']['eventos'] if e['tipo']=='embalaje')['estado']='estimado'
    _,r=analizar(p)
    assert r['enlace_precio']['estado']=='requiere_revision'
    assert r['enlace_precio']['problemas_cobro']


def test_gasto_local_observado_distinto_del_previsto_conserva_ambas_fotografias():
    p=preparar()
    next(e for e in p['snapshot_ml']['datos_locales']['eventos'] if e['tipo']=='embalaje')['importe_centavos']=20000
    _,r=analizar(p)
    assert r['enlace_precio']['neto_previsto_centavos']==592100
    assert r['enlace_precio']['neto_cobrado_despues_locales_centavos']==582100
    assert r['enlace_precio']['estado']=='bajo_minimo'
    assert r['totales']['diferencia_resultado_centavos']==-10000
