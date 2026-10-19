"""Regresiones del cruce: calidad real del lote y stock neto comparten la decisión."""
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace as Obj

import pytest

from services.calidad_produccion import elegibilidad_inventario
from services.plan_materiales_produccion import planificar_materiales
from services.propuestas_inventario_produccion import preparar_propuesta_inventario
from services.disponibilidad_productiva import disponibilidad_neta
from test_propuestas_inventario_produccion import orden, datos


def preparar(op=None,mapeos=None):
    op=op or orden()
    base,destinos=datos()
    return preparar_propuesta_inventario(op,organizacion_id=7,unidad_negocio_id=9,
        mapeos_insumo=base if mapeos is None else mapeos,existencias_producto=destinos)


@pytest.mark.parametrize('estado',['cuarentena','en_control','rechazado_interno'])
def test_buenas_del_parte_no_habilitan_un_lote_retenido_o_rechazado(estado):
    op=orden();op.lotes_preparatorios[0].estado=estado
    r=preparar(op)
    assert not r['aprobada'] and r['calidad']['elegibles']=='0'
    assert not any(m['tipo']=='entrada_teorica' for m in r['movimientos_propuestos'])


def test_lote_aprobado_sin_control_no_es_una_liberacion():
    op=orden();op.lotes_preparatorios[0].controles_calidad=[]
    assert not preparar(op)['aprobada']
    op.lotes_preparatorios=[]
    r=preparar(op)
    assert r['calidad']['sin_lote']=='6' and not r['aprobada']


def test_ultimo_control_contradictorio_o_ajeno_bloquea():
    for cambios in ({'resultado':'rechazado_interno'},{'lote_produccion_id':99},
                     {'organizacion_id':8},{'muestra':'NaN'},{'libera_stock':True}):
        op=orden();control=deepcopy(op.lotes_preparatorios[0].controles_calidad[0]);control.id+=1
        control.__dict__.update(cambios);op.lotes_preparatorios[0].controles_calidad.append(control)
        assert not preparar(op)['aprobada']


def test_lotes_mixtos_solo_proponen_cantidad_aprobada_sin_perder_consumos():
    op=orden();aprobado=op.lotes_preparatorios[0];aprobado.cantidad='2'
    aprobado.controles_calidad[0].muestra='2';aprobado.controles_calidad[0].aprobadas='2'
    rechazo=deepcopy(aprobado);rechazo.id=22;rechazo.cantidad='4';rechazo.estado='rechazado_interno'
    op.lotes_preparatorios.append(rechazo)
    r=preparar(op)
    assert r['calidad']['elegibles']=='2' and not r['aprobada']
    assert r['movimientos_propuestos'][0]['cantidad']=='16'
    assert r['movimientos_propuestos'][1]['cantidad']=='2'
    assert not r['habilita_ejecucion'] and not r['controles']['stock_modificado']


def test_sobreasignacion_de_lotes_no_aprueba_ninguno_del_parte():
    op=orden();otro=deepcopy(op.lotes_preparatorios[0]);otro.id=22
    op.lotes_preparatorios.append(otro)
    r=preparar(op)
    assert r['calidad']['elegibles']=='0' and not r['aprobada']
    assert any(h['codigo']=='lotes_superan_parte' for h in r['hallazgos'])


def test_reservas_y_bloqueos_impiden_consumo_aunque_haya_stock_bruto():
    mapeos,_=datos();e=mapeos[0].existencia
    e.stock_actual=20;e.stock_reservado=3;e.stock_bloqueado=2
    r=preparar(mapeos=mapeos)
    assert not r['aprobada']
    assert r['movimientos_propuestos'][0]['faltante']=='1'
    assert r['movimientos_propuestos'][0]['disponible_antes']=='15'
    assert e.stock_actual==20 and e.stock_reservado==3 and e.stock_bloqueado==2


@pytest.mark.parametrize('valor',[None,'NaN','Infinity',-1,True])
def test_stock_no_verificable_no_se_inventa(valor):
    mapeos,_=datos();mapeos[0].existencia.stock_actual=valor
    r=preparar(mapeos=mapeos)
    assert not r['aprobada'] and any(h['codigo']=='stock_no_verificable' for h in r['hallazgos'])


def test_fraccion_se_conserva_pero_no_se_declara_ejecutable_con_inventario_entero():
    op=orden();op.insumos_planificados[0].cantidad_planificada='2.625'
    r=preparar(op)
    assert r['movimientos_propuestos'][0]['cantidad']=='2.1'
    assert not r['aprobada'] and any(h['codigo']=='consumo_fraccionario_no_ejecutable' for h in r['hallazgos'])
    assert not r['habilita_ejecucion']


def test_materiales_consistentes_pero_insuficientes_no_aprueban_el_expediente():
    from test_plan_materiales_produccion import orden as pendiente, mapeo
    op=pendiente(1,'OP');op.insumos_planificados[0].cantidad_planificada='2.1'
    r=planificar_materiales(organizacion_id=7,unidad_negocio_id=9,ordenes=[op],mapeos_insumo=[mapeo(stock=2)])
    assert r['consistente'] and not r['aprobado'] and not r['disponibilidad_suficiente']
    assert r['requiere_fracciones'] and r['asignaciones_virtuales'][0]['faltante']=='0.1'


def test_orden_terminada_sin_demanda_no_prueba_stock_para_consumir_el_avance():
    op=orden();op.cantidad_planificada='8'
    mapeos,_=datos();mapeos[0].existencia.stock_actual=0
    plan=planificar_materiales(organizacion_id=7,unidad_negocio_id=9,ordenes=[op],mapeos_insumo=mapeos)
    assert not plan['demanda_pendiente']
    assert not preparar(op,mapeos)['aprobada']


def test_varios_insumos_no_reutilizan_la_misma_disponibilidad():
    op=orden();op.insumos_planificados.append(Obj(insumo_id=8,cantidad_planificada='20'))
    mapeos,_=datos();mapeos[0].existencia.stock_actual=20
    otro=deepcopy(mapeos[0]);otro.id=6;otro.insumo_id=8
    r=preparar(op,mapeos+[otro])
    assert r['movimientos_propuestos'][0]['faltante']=='0'
    assert r['movimientos_propuestos'][1]['faltante']=='12'
    assert not r['aprobada']


def test_tenant_parte_y_lote_se_controlan_y_no_se_mutan():
    op=orden();original=deepcopy(op)
    preparar(op)
    assert op.__dict__.keys()==original.__dict__.keys()
    assert op.lotes_preparatorios[0].estado=='aprobado_interno'
    op.partes_informados[0].organizacion_id=8
    assert not preparar(op)['aprobada']


def test_destino_automatico_unico_tambien_necesita_sku_y_sucursal_activos():
    mapeos,destinos=datos();destinos[0].sucursal.activa=False
    r=preparar_propuesta_inventario(orden(),organizacion_id=7,unidad_negocio_id=9,
        mapeos_insumo=mapeos,existencias_producto=destinos)
    assert not r['aprobada']
    assert any(h['codigo']=='destino_producto_no_valido' for h in r['hallazgos'])


def expediente(stock=100,estado_lote='aprobado_interno'):
    from services.expediente_habilitacion_produccion import construir_expediente
    op=orden();op.costo_unitario_centavos=10000
    op.operaciones_planificadas[0].empleado_id=1;op.maquinas_planificadas=[]
    op.lotes_preparatorios[0].estado=estado_lote
    op.lotes_preparatorios[0].controles_calidad[0].numero='C-1'
    mapeos,destinos=datos();mapeos[0].existencia.stock_actual=stock
    version=Obj(vigente=True,horas_productivas=1,
        empleado=Obj(id=1,organizacion_id=7,unidad_negocio_id=9,activo=True))
    return construir_expediente(organizacion_id=7,unidad_negocio_id=9,ordenes=[op],
        mapeos_insumo=mapeos,existencias_producto=destinos,
        versiones_empleado=[version],versiones_maquina=[],lotes=op.lotes_preparatorios)


def test_expediente_integra_calidad_materiales_costeo_y_capacidad_reales():
    r=expediente()
    assert r['apto_para_ensayo'] and not r['habilitacion_ejecucion']
    assert r['ordenes'][0]['inventario_aprobado']
    assert not expediente(stock=0)['apto_para_ensayo']
    assert not expediente(estado_lote='rechazado_interno')['apto_para_ensayo']
    assert not r['controles']['persistencia'] and r['controles']['movimientos_stock']==0


def test_nueva_seccion_produccion_se_renderiza_plegada_con_bloqueos():
    from flask import Flask
    from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
    from services.avances_produccion import resumir_orden
    app=Flask(__name__)
    app.jinja_loader=ChoiceLoader([DictLoader({'base.html':'{% block extra_head %}{% endblock %}{% block content %}{% endblock %}'}),FileSystemLoader('templates')])
    op=orden();op.producto=Obj(sku='ENSAYO');op.cantidad_planificada=Decimal('10')
    op.maquinas_planificadas=[]
    op.partes_informados[0].cantidad_buena=Decimal('6')
    op.partes_informados[0].lotes_preparatorios=[]
    calidad=elegibilidad_inventario(op,organizacion_id=7,unidad_negocio_id=9)
    plan=Obj(consistente=True,demanda_pendiente=True,disponibilidad_suficiente=False,
        requiere_fracciones=True,sugerencias_compra=[Obj(insumo_id=3,existencia_sucursal_id=11,cantidad='0.1')])
    with app.test_request_context():
        html=app.jinja_env.get_template('admin_produccion.html').render(
            url_for=lambda *a,**k:'#',unidad_activa=Obj(nombre='UAT'),perfiles_produccion=[],
            resumen_produccion=Obj(ordenes=1,borradores=0,aprobadas=1,ejecuciones=0),
            ordenes_produccion=[op],avances_por_orden={1:resumir_orden(op)},
            destinos_por_orden={1:None},opciones_destino_por_orden={1:[]},
            lotes_produccion=[],materiales_preparacion=plan,calidad_por_orden={1:calidad})
    assert 'Faltan materiales' in html and 'cantidades fraccionarias' in html
    assert 'Elegibles por calidad' in html and 'No elegibles / sin lote' in html
    assert '<details class="production-lot-create"><summary>Disponibilidad de materiales y calidad' in html


def test_expediente_no_asigna_el_mismo_stock_a_dos_ordenes():
    from services.expediente_habilitacion_produccion import construir_expediente
    uno=orden();uno.costo_unitario_centavos=10000
    uno.operaciones_planificadas[0].empleado_id=1;uno.maquinas_planificadas=[]
    uno.lotes_preparatorios[0].controles_calidad[0].numero='C-1'
    dos=deepcopy(uno);dos.id=2;dos.numero='OP-2'
    dos.partes_informados[0].id=5;dos.partes_informados[0].orden_produccion_id=2
    lote=dos.lotes_preparatorios[0];lote.id=22;lote.codigo='L-2'
    lote.orden_produccion_id=2;lote.parte_produccion_id=5
    lote.controles_calidad[0].id=23;lote.controles_calidad[0].numero='C-2'
    lote.controles_calidad[0].lote_produccion_id=22
    mapeos,destinos=datos();mapeos[0].existencia.stock_actual=20
    version=Obj(vigente=True,horas_productivas=1,
        empleado=Obj(id=1,organizacion_id=7,unidad_negocio_id=9,activo=True))
    r=construir_expediente(organizacion_id=7,unidad_negocio_id=9,ordenes=[uno,dos],
        mapeos_insumo=mapeos,existencias_producto=destinos,versiones_empleado=[version],
        versiones_maquina=[],lotes=uno.lotes_preparatorios+dos.lotes_preparatorios)
    assert not r['apto_para_ensayo']
    assert r['disponibilidad_compartida'][-1]['faltante']=='12'
    assert any(h['codigo']=='stock_compartido_insuficiente' for h in r['hallazgos'])
    assert mapeos[0].existencia.stock_actual==20


def test_stock_suficiente_no_elimina_el_bloqueo_por_fracciones():
    from test_plan_materiales_produccion import orden as pendiente, mapeo
    op=pendiente(1,'OP');op.insumos_planificados[0].cantidad_planificada='2.1'
    r=planificar_materiales(organizacion_id=7,unidad_negocio_id=9,ordenes=[op],mapeos_insumo=[mapeo(stock=3)])
    assert r['consistente'] and r['disponibilidad_suficiente']
    assert not r['compatible_con_inventario'] and not r['aprobado']
    assert r['asignaciones_virtuales'][0]['requerida']=='2.1'
    assert not r['habilita_ejecucion']
