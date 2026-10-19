"""Conversión exacta compartida de compras y fabricación, sin movimientos reales."""
import json
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace as Obj

import pytest

from services.unidades_materias_primas import (
    definir_unidad, leer_unidad_item, convertir_cantidad, convertir_compra,
)
from services.plan_materiales_produccion import planificar_materiales
from services.propuestas_inventario_produccion import preparar_propuesta_inventario
from services.propuestas_impacto_compra import preparar_propuestas
from services.mapeos_compras_inventario import habilitar_propuestas_stock
from test_plan_materiales_produccion import orden as pendiente
from test_propuestas_inventario_produccion import orden, datos
from test_mapeos_compras_inventario import Propuesta, Session


def mapeo(precision='milesimas', unidad='kg', stock=10000):
    mapas,_=datos(); m=mapas[0]
    m.insumo.unidad_medida=unidad
    m.existencia_sucursal_id=m.existencia.id
    m.existencia.stock_actual=stock
    m.existencia.item_inventario.atributos_json=json.dumps(
        {'insumo_productivo_id':3, **definir_unidad(unidad,precision)})
    return m


@pytest.mark.parametrize('precision,cantidad,esperado',[
    ('unidad','2','2'),('milesimas','2.1','2100'),
    ('millonesimas','0.000001','1'),('milesimas','0','0'),
])
def test_conversion_exacta_conserva_cantidad_de_costeo(precision,cantidad,esperado):
    m=mapeo(precision);antes=deepcopy(m)
    c=convertir_cantidad(m,cantidad)
    assert c['representable'] and c['cantidad_inventario']==esperado
    assert Decimal(c['cantidad_insumo'])==Decimal(cantidad)
    assert m.existencia.stock_actual==antes.existencia.stock_actual


def test_precision_insuficiente_no_redondea_ni_habilita():
    c=convertir_cantidad(mapeo(),'0.000001')
    assert c['cantidad_inventario']=='0.001' and not c['representable']
    with pytest.raises(ValueError,match='no se redondea'):
        convertir_compra(mapeo(),'0.000001','kg',7,9)


@pytest.mark.parametrize('cantidad',['NaN','Infinity','-1',True,'0.0000001','2147.483648'])
def test_cantidades_invalidas_o_desborde_no_se_convierten(cantidad):
    with pytest.raises(ValueError): convertir_cantidad(mapeo('millonesimas'),cantidad)


@pytest.mark.parametrize('cambio',['tenant','unidad_negocio','insumo','producto','unidad_origen','unidad_cambiada','atributos','factor','version'])
def test_identidad_contexto_y_unidades_no_se_suponen(cambio):
    m=mapeo();origen='kg'
    if cambio=='tenant':m.existencia.item_inventario.organizacion_id=8
    if cambio=='unidad_negocio':m.insumo.unidad_negocio_id=10
    if cambio=='insumo':m.insumo_id=4
    if cambio=='producto':m.existencia.producto_id=99
    if cambio=='unidad_origen':origen='g'
    if cambio=='unidad_cambiada':m.insumo.unidad_medida='litro'
    if cambio=='atributos':m.existencia.item_inventario.atributos_json='[]'
    if cambio in ['factor','version']:
        atributos=json.loads(m.existencia.item_inventario.atributos_json)
        atributos['factor_inventario' if cambio=='factor' else 'version_unidad']=True if cambio=='factor' else 2
        m.existencia.item_inventario.atributos_json=json.dumps(atributos)
    with pytest.raises(ValueError):convertir_cantidad(m,'1',unidad_origen=origen)


def test_mismo_insumo_no_supone_conversion_de_peso_a_superficie():
    m=mapeo(unidad='plancha')
    assert convertir_cantidad(m,'0.25')['cantidad_inventario']=='250'
    with pytest.raises(ValueError):convertir_cantidad(m,'0.25',unidad_origen='kg')


def test_plan_asigna_stock_base_y_sugiere_compra_en_unidad_del_insumo():
    op=pendiente(1,'OP');op.insumos_planificados[0].cantidad_planificada='2.1'
    m=mapeo(stock=2500);m.existencia.stock_reservado=300;m.existencia.stock_bloqueado=200
    r=planificar_materiales(organizacion_id=7,unidad_negocio_id=9,ordenes=[op],mapeos_insumo=[m])
    fila=r['asignaciones_virtuales'][0]
    assert fila['cantidad_inventario']=='2100' and fila['unidad_inventario']=='g'
    assert fila['requerida']=='2.1' and fila['asignada_virtual']=='2' and fila['faltante']=='0.1'
    assert r['sugerencias_compra'][0]['cantidad']=='0.1'
    assert r['sugerencias_compra'][0]['unidad_medida']=='kg'
    assert r['compatible_con_inventario'] and not r['aprobado']
    assert m.existencia.stock_actual==2500
    m.existencia.stock_actual=2600
    r=planificar_materiales(organizacion_id=7,unidad_negocio_id=9,ordenes=[op],mapeos_insumo=[m])
    assert r['aprobado'] and r['requiere_fracciones'] and not r['habilita_ejecucion']


def test_propuesta_produccion_convierte_consumos_y_conserva_producto_terminado():
    op=orden();op.insumos_planificados[0].cantidad_planificada='2.625'
    m=mapeo();_,destinos=datos()
    r=preparar_propuesta_inventario(op,organizacion_id=7,unidad_negocio_id=9,
        mapeos_insumo=[m],existencias_producto=destinos)
    salida,entrada=r['movimientos_propuestos']
    assert r['aprobada'] and salida['cantidad']=='2100' and salida['cantidad_insumo']=='2.1'
    assert salida['unidad_inventario']=='g' and entrada['cantidad']=='6'
    assert not r['habilita_ejecucion'] and not r['controles']['stock_modificado']
    assert r['reversion_teorica'][-1]['cantidad']=='2100'


def test_legado_conserva_uno_a_uno_y_fracciones_bloqueadas():
    m=mapeo();m.existencia.item_inventario.atributos_json=json.dumps({'insumo_productivo_id':3,'unidad_medida':'kg'})
    assert leer_unidad_item(m.existencia.item_inventario)['factor_inventario']==1
    assert not convertir_cantidad(m,'2.1')['representable']


def compra(m,unidad='kg',cantidad='2.1'):
    recepcion=Obj(id=10,organizacion_id=7,unidad_negocio_id=9,estado='preparatoria',
        items=[Obj(id=30,cantidad_recibida=cantidad,orden_item=Obj(insumo_id=3,
        unidad_medida=unidad,precio_unitario_centavos=10000))],
        orden=Obj(proveedor_id=4),comprobante_referencia='FC')
    return preparar_propuestas(recepcion,organizacion_id=7,unidad_negocio_id=9,
        PropuestaImpactoCompra=Propuesta,db_session=Session(),mapeos=m)


def test_compra_convierte_stock_sin_multiplicar_precio_u_obligacion():
    propuestas=compra([mapeo()]);costo,stock,pagar=propuestas
    detalle=json.loads(stock.detalle_json)
    assert stock.estado=='preparada' and detalle['cantidad_inventario']=='2100'
    assert detalle['cantidad_recibida']=='2.1' and detalle['unidad_compra']=='kg'
    assert json.loads(costo.detalle_json)['precio_unitario_centavos']==10000
    assert json.loads(pagar.detalle_json)['importe_centavos']==21000
    assert all(not p.ejecutada for p in propuestas)


@pytest.mark.parametrize('unidad',['g',None])
def test_compra_no_supone_unidad_ajena_o_ausente(unidad):
    stock=compra([mapeo()],unidad=unidad)[1]
    assert stock.estado=='bloqueada' and json.loads(stock.detalle_json)['motivo_bloqueo']


def test_mapeo_posterior_aplica_misma_conversion_sin_reabrir_decisiones():
    propuestas=compra([]);stock=propuestas[1]
    assert stock.estado=='bloqueada'
    assert habilitar_propuestas_stock(propuestas,[mapeo()],db_session=Session())==[stock]
    assert json.loads(stock.detalle_json)['cantidad_inventario']=='2100'
    stock.estado='rechazada';anterior=stock.detalle_json
    assert habilitar_propuestas_stock([stock],[mapeo('millonesimas')],db_session=Session())==[]
    assert stock.detalle_json==anterior and stock.estado=='rechazada'


def test_mapeos_ambiguos_y_otros_contextos_no_habilitan():
    m=mapeo();otro=deepcopy(m);otro.id+=1
    assert compra([m,otro])[1].estado=='bloqueada'
    m.unidad_negocio_id=10
    assert compra([m])[1].estado=='bloqueada'


def test_propuesta_legacy_sin_unidad_no_se_habilita_silenciosamente():
    stock=compra([])[1];detalle=json.loads(stock.detalle_json);del detalle['unidad_compra']
    stock.detalle_json=json.dumps(detalle)
    assert habilitar_propuestas_stock([stock],[mapeo()],db_session=Session())==[]
    assert stock.estado=='bloqueada' and json.loads(stock.detalle_json)['motivo_bloqueo']


def test_inventario_nucleo_sigue_entero_usando_la_unidad_base():
    from services.inventario_nucleo import aplicar_movimiento
    m=mapeo(stock=0);e=m.existencia
    aplicar_movimiento(e,'ingreso',convertir_cantidad(m,'2.1')['cantidad_inventario'])
    aplicar_movimiento(e,'reserva',convertir_cantidad(m,'0.1')['cantidad_inventario'])
    aplicar_movimiento(e,'egreso',convertir_cantidad(m,'2')['cantidad_inventario'])
    assert e.stock_actual==100 and e.stock_reservado==100
    with pytest.raises(ValueError):aplicar_movimiento(e,'egreso','0.1')


def test_paneles_muestran_conversion_y_motivo_sin_exponer_json():
    from flask import Flask
    from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
    app=Flask(__name__)
    app.jinja_loader=ChoiceLoader([DictLoader({'base.html':'{% block extra_head %}{% endblock %}{% block content %}{% endblock %}'}),FileSystemLoader('templates')])
    stock=compra([mapeo()])[1];stock.id=1;stock.recepcion=Obj(numero='R-1')
    insumo=Obj(id=3,codigo='MP',nombre='Material',tipo='materia_prima',unidad_medida='kg')
    with app.test_request_context():
        html=app.jinja_env.get_template('admin_compras.html').render(
            url_for=lambda *a,**k:'#',organizacion=Obj(nombre='UAT'),unidad_activa=Obj(nombre='UAT'),
            resumen_compras={},insumos_compra=[insumo],propuestas_impacto_compra=[stock],
            detalles_propuestas_compra={1:json.loads(stock.detalle_json)})
        assert 'Precisión del nuevo SKU' in html and '2.1 kg → 2100 g' in html
        stock.estado='bloqueada'
        html=app.jinja_env.get_template('admin_compras.html').render(
            url_for=lambda *a,**k:'#',organizacion=Obj(nombre='UAT'),unidad_activa=Obj(nombre='UAT'),resumen_compras={},
            propuestas_impacto_compra=[stock],detalles_propuestas_compra={1:{'motivo_bloqueo':'Unidad incompatible'}})
        assert 'Unidad incompatible' in html
        m=mapeo();e=m.existencia;e.item_inventario_id=1;e.stock_minimo=0;e.stock_maximo=None
        e.stock_transito=0;e.sucursal=Obj(nombre='Taller')
        html=app.jinja_env.get_template('admin_inventario.html').render(
            url_for=lambda *a,**k:'#',existencias=[e],items_inventario=[],reservas=[],
            transferencias=[],conteos=[],sucursales=[],resumen_diagnosticos_canal={},
            resumen_propuestas_publicacion={},resumen_mapeos_publicaciones={'cruzado':0,'invalido':0},unidad_stock_por_item={1:'g'})
        assert 'Cantidad en unidad base del SKU' in html
        assert ' · g' in html


def test_expediente_conserva_unidad_base_en_disponibilidad_compartida():
    from services.expediente_habilitacion_produccion import construir_expediente
    op=orden();op.insumos_planificados[0].cantidad_planificada='2.625'
    op.costo_unitario_centavos=10000;op.operaciones_planificadas[0].empleado_id=1
    op.maquinas_planificadas=[];op.lotes_preparatorios[0].controles_calidad[0].numero='C-1'
    version=Obj(vigente=True,horas_productivas=1,
        empleado=Obj(id=1,organizacion_id=7,unidad_negocio_id=9,activo=True))
    _,destinos=datos()
    r=construir_expediente(organizacion_id=7,unidad_negocio_id=9,ordenes=[op],
        mapeos_insumo=[mapeo()],existencias_producto=destinos,
        versiones_empleado=[version],versiones_maquina=[],lotes=op.lotes_preparatorios)
    fila=r['disponibilidad_compartida'][0]
    assert r['apto_para_ensayo'] and not r['habilitacion_ejecucion']
    assert fila['consumo_acumulado']=='2100' and fila['unidad_inventario']=='g'
    assert fila['factor_inventario']==1000 and fila['unidad_medida']=='kg'
