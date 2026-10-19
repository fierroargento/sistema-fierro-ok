"""Evidencia de embalaje y contraste offline, con persistencia SQLite reducida."""
from copy import deepcopy
from datetime import timedelta
import json
from types import SimpleNamespace as Obj

import pytest
from sqlalchemy import Column,Integer,Text,create_engine
from sqlalchemy.orm import declarative_base,sessionmaker

from services.cobertura_precio_publicacion import (
    CLAVE,guardar_cobertura,completar_cobertura,preservar_coberturas,
)
from services.control_comercial_masivo import construir_bandeja
from services.cola_acciones_comerciales import planificar_fila
from test_enlace_economico_producto import fuentes,ejecutar,AHORA


class Sesion:
    def __init__(self):self.commits=0
    def commit(self):self.commits+=1


def fila(datos=None):return completar_cobertura(ejecutar(datos)[1][0],ahora=AHORA)


def guardar(f,**cambios):
    datos=dict(cuenta='CUENTA-UAT',publicacion='PUB-UAT',variante='',modo_embalaje='adicional',
        detalle_ids=[],adicional_centavos=1000,referencia='Embalaje del ensayo',
        huella_esperada=f['trazabilidad_economica']['huella_enlace'],usuario=Obj(id=9),db_session=Sesion(),ahora=AHORA)
    datos.update(cambios)
    return guardar_cobertura(f,**datos)


def test_adicional_se_cubre_una_sola_vez_y_no_multiplica_el_costo():
    d=fuentes();f=fila(d);guardar(f)
    nueva=fila(d);traza=nueva['trazabilidad_economica']
    assert traza['embalaje_verificado'] and traza['embalaje_adicional_centavos']==1000
    assert nueva['minimo']['liquidacion_centavos']>=26250
    assert nueva['minimo']['piso_liquidacion_centavos']==26250
    assert d['costos'][0].costo_total_centavos==21000
    assert traza['identidad_publicacion']['cuenta_codigo']=='CUENTA-UAT'
    assert not traza['cargos_contrastados_cuenta'] and not traza['habilita_publicacion']
    control,_=construir_bandeja([nueva],[])
    assert control[0]['propuesto']['embalaje_adicional_centavos']==1000
    assert control[0]['propuesto']['liquidacion_centavos']>=control[0]['objetivo']['piso_liquidacion_centavos']


def test_incluido_no_se_suma_de_nuevo():
    d=fuentes();f=fila(d);antes=f['minimo']['precio_final_centavos']
    guardar(f,modo_embalaje='incluido',detalle_ids=[11],adicional_centavos=0)
    nueva=fila(d)
    assert nueva['minimo']['precio_final_centavos']==antes
    assert nueva['trazabilidad_economica']['evidencia_embalaje']['embalaje_incluido_centavos']==21000
    assert nueva['trazabilidad_economica']['embalaje_adicional_centavos']==0


@pytest.mark.parametrize('cambio',[
    {'modo_embalaje':'incluido','detalle_ids':[11],'adicional_centavos':1},
    {'modo_embalaje':'incluido','detalle_ids':[],'adicional_centavos':0},
    {'detalle_ids':[11]}, {'detalle_ids':[999]}, {'detalle_ids':[11,11]},
    {'modo_embalaje':'sin_costo','adicional_centavos':1},{'adicional_centavos':-1},
    {'adicional_centavos':True},{'adicional_centavos':1.5},{'referencia':''},
    {'cuenta':''},{'publicacion':''},{'variante':'x'*161},{'huella_esperada':'obsoleta'},
])
def test_rechaza_doble_conteo_y_datos_invalidos_sin_escribir(cambio):
    f=fila();s=Sesion();antes=f['inclusion'].canales_json
    with pytest.raises(ValueError):guardar(f,db_session=s,**cambio)
    assert s.commits==0 and f['inclusion'].canales_json==antes


def test_sin_costo_requiere_declaracion_y_no_es_cero_inferido():
    d=fuentes();f=fila(d)
    assert not f['trazabilidad_economica']['embalaje_verificado']
    assert planificar_fila(construir_bandeja([f],[])[0][0])==[]
    guardar(f,modo_embalaje='sin_costo',adicional_centavos=0)
    nueva=fila(d)
    assert nueva['trazabilidad_economica']['embalaje_verificado']
    assert planificar_fila(construir_bandeja([nueva],[])[0][0])


def test_cambio_de_coste_o_politica_conserva_historia_pero_bloquea_propuesta():
    d=fuentes();guardar(fila(d))
    anterior=d['inclusiones'][0].canales_json
    d['reglas_canal'][0].numero_version+=1
    f=fila(d)
    assert f['trazabilidad_economica']['cobertura_estado']=='requiere_revision'
    assert not f['trazabilidad_economica']['embalaje_verificado']
    assert not planificar_fila(construir_bandeja([f],[])[0][0])
    assert d['inclusiones'][0].canales_json==anterior
    guardar(f,adicional_centavos=1200)
    assert len(json.loads(d['inclusiones'][0].canales_json)[CLAVE])==2
    assert fila(d)['trazabilidad_economica']['embalaje_adicional_centavos']==1200


def test_reintento_identico_es_idempotente_y_no_sobrescribe_canales():
    d=fuentes();i=d['inclusiones'][0];i.canales_json=json.dumps({'mercadolibre':{'habilitado':False,'id_externo':'PUB'}})
    f=fila(d);s=Sesion();guardar(f,db_session=s)
    assert not guardar(f,db_session=s)
    dato=json.loads(i.canales_json)
    assert s.commits==1 and len(dato[CLAVE])==1 and dato['mercadolibre']['id_externo']=='PUB'
    otros=preservar_coberturas(i,{'mercadolibre':{'habilitado':True}})
    assert otros[CLAVE]==dato[CLAVE] and otros['mercadolibre']['habilitado']


@pytest.mark.parametrize('contenido',['[]','invalido',json.dumps({CLAVE:{}})])
def test_metadata_invalida_no_se_borra_para_guardar(contenido):
    d=fuentes();d['inclusiones'][0].canales_json=contenido;f=fila(d);s=Sesion()
    assert f['trazabilidad_economica']['cobertura_estado']=='requiere_revision'
    with pytest.raises(ValueError):guardar(f,db_session=s)
    assert s.commits==0 and d['inclusiones'][0].canales_json==contenido


def test_persistencia_real_de_historia_y_actualizacion_de_ficha_preserva_evidencia():
    Base=declarative_base()
    class Inclusion(Base):
        __tablename__='inclusion';id=Column(Integer,primary_key=True);canales_json=Column(Text)
    engine=create_engine('sqlite://');Base.metadata.create_all(engine);session=sessionmaker(bind=engine)()
    try:
        i=Inclusion(id=5,canales_json='{}');session.add(i);session.commit()
        d=fuentes();d['inclusiones'][0].canales_json=i.canales_json;f=fila(d)
        # Persistimos en la misma inclusión ORM, conservando los datos de catálogo del fixture.
        i.catalogo=f['inclusion'].catalogo;i.producto_id=7;i.producto=f['inclusion'].producto;i.catalogo_id=4;i.activo=True
        d['inclusiones']=[i];f=fila(d);guardar(f,db_session=session)
        session.expire_all();assert len(json.loads(session.get(Inclusion,5).canales_json)[CLAVE])==1
        i.canales_json=json.dumps(preservar_coberturas(i,{'mercadolibre':{'habilitado':False}}));session.commit()
        session.expire_all();assert fila(d)['trazabilidad_economica']['embalaje_verificado']
    finally:session.close();engine.dispose()


def observaciones(f,cuenta='CUENTA-UAT',publicacion='PUB-UAT'):
    politica=f['regla_canal'];precio=f['minimo']['precio_final_centavos']
    base=dict(organizacion_id=1,unidad_negocio_id=2,lista_precio_id=6,catalogo_producto_id=5,
        cuenta_codigo=cuenta,referencia_publicacion=publicacion,fecha_observacion=AHORA,origen='manual')
    return [Obj(id=1,tipo='precio',precio_publicado_centavos=precio,**base),
        Obj(id=2,tipo='cargo',comision_pct=politica.comision_pct,cargo_fijo_centavos=f['minimo']['cargo_fijo_centavos'],**base),
        Obj(id=3,tipo='envio',costo_envio_centavos=f['minimo']['envio_centavos'],**base)]


def regla_vigencia():
    return Obj(lista_precio_id=6,vigente=True,estado='vigente',vigente_desde=AHORA-timedelta(days=1),vigente_hasta=None,
        vigencia_precio_horas=24,vigencia_cargos_horas=24,vigencia_envio_horas=24)


def test_contraste_exacto_no_se_presenta_como_verificacion_de_todos_los_cargos():
    d=fuentes();guardar(fila(d));f=fila(d)
    f=completar_cobertura(ejecutar(d)[1][0],observaciones=observaciones(f),reglas_validacion=[regla_vigencia()],ahora=AHORA)
    t=f['trazabilidad_economica']
    assert t['contraste']['estado']=='coincide_en_precio_observado'
    assert t['contraste']['observaciones']=={'precio':1,'cargo':2,'envio':3}
    assert t['identidad_publicacion']['identidad']=='declarada_offline'
    assert not t['cargos_contrastados_cuenta'] and not t['habilita_publicacion']


@pytest.mark.parametrize('cambio',['cuenta','publicacion','tenant','unidad','vencida','futura','comision','envio','contradictoria','variante','sin_regla'])
def test_no_cruza_observaciones_ajenas_vencidas_o_contradictorias(cambio):
    d=fuentes();guardar(fila(d),variante='VAR' if cambio=='variante' else '')
    f=fila(d);obs=observaciones(f);reglas=[regla_vigencia()]
    if cambio=='cuenta':obs[1].cuenta_codigo='OTRA'
    if cambio=='publicacion':obs[1].referencia_publicacion='OTRA'
    if cambio=='tenant':obs[1].organizacion_id=8
    if cambio=='unidad':obs[1].unidad_negocio_id=8
    if cambio=='vencida':obs[1].fecha_observacion=AHORA-timedelta(hours=25)
    if cambio=='futura':obs[1].fecha_observacion=AHORA+timedelta(seconds=1)
    if cambio=='comision':obs[1].comision_pct+=1
    if cambio=='envio':obs[2].costo_envio_centavos+=1
    if cambio=='contradictoria':otro=deepcopy(obs[1]);otro.id=99;otro.comision_pct+=1;obs.append(otro)
    if cambio=='sin_regla':reglas=[]
    r=completar_cobertura(ejecutar(d)[1][0],observaciones=obs,reglas_validacion=reglas,ahora=AHORA)
    assert r['trazabilidad_economica']['contraste']['estado']=='pendiente'
    assert r['trazabilidad_economica']['contraste']['motivos']


def test_precio_mas_alto_no_se_conserva_si_un_salto_de_envio_rompe_el_neto():
    from services.motor_comercial_canal import calcular_precio_minimo_canal
    from services.control_comercial_masivo import evaluar_control
    d=fuentes();p=d['reglas_canal'][0];p.comision_pct=0;p.publicidad_pct=0;p.financiacion_pct=0;p.devoluciones_pct=0
    p.umbral_envio_centavos=33000;p.costo_envio_default_centavos=20000
    p.tramos=[Obj(precio_desde_centavos=0,precio_hasta_centavos=None,cargo_fijo_centavos=0)]
    f=ejecutar(d)[1][0]
    r=evaluar_control(f,precio_actual_centavos=34000)
    assert r['estado_control']=='debajo_del_piso'
    assert r['propuesto']['liquidacion_centavos']>=r['objetivo']['piso_liquidacion_centavos']
    assert r['propuesto']['precio_final_centavos']<34000
    assert r['accion_recomendada']=='actualizar_precio'


def test_repetir_lectura_no_duplica_embalaje_ni_cambia_huella():
    d=fuentes();guardar(fila(d));f=fila(d)
    antes=deepcopy(f['trazabilidad_economica'])
    completar_cobertura(f,ahora=AHORA)
    assert f['trazabilidad_economica']==antes


def test_caso_uat_de_captura_con_embalaje_adicional_cien_pesos():
    d=fuentes();c=d['costos'][0];c.costo_total_centavos=493365
    c.detalles[0].cantidad=1;c.detalles[0].costo_unitario_centavos=493365;c.detalles[0].subtotal_centavos=493365
    r=d['reglas_economicas'][0];r.impuesto_pct=0;r.incremento_redondeo_centavos=100
    p=d['reglas_canal'][0];p.comision_pct=10;p.publicidad_pct=0;p.financiacion_pct=0;p.devoluciones_pct=0
    p.umbral_envio_centavos=0;p.costo_envio_default_centavos=0
    p.tramos=[Obj(precio_desde_centavos=0,precio_hasta_centavos=None,cargo_fijo_centavos=0)]
    f=fila(d);assert f['minimo']['precio_final_centavos']==657900
    guardar(f,adicional_centavos=10000)
    nuevo=fila(d)
    assert nuevo['minimo']['precio_final_centavos']==669000
    assert nuevo['minimo']['comision_centavos']==66900
    assert nuevo['minimo']['liquidacion_centavos']==592100
    assert nuevo['minimo']['piso_liquidacion_centavos']==592100
    assert c.costo_total_centavos==493365


@pytest.mark.parametrize('cambio',['ninguno','otra_unidad','otro_tenant','huella','linea_ajena'])
def test_ruta_real_guarda_solo_tras_validar_contexto_y_calculo(cambio):
    import ast
    from pathlib import Path
    from flask import Flask,request,redirect
    codigo=ast.parse(Path('modules/admin/comercial/routes.py').read_text())
    funcion=next(n for n in ast.walk(codigo) if isinstance(n,ast.FunctionDef) and n.name=='guardar_cobertura_precio')
    funcion.decorator_list=[]
    d=fuentes();f=fila(d);sesion=Sesion();sesion.rollback=lambda:None
    class Consulta:
        bloqueada=False
        def filter_by(self,**kw):self.ident=kw['id'];return self
        def with_for_update(self):self.bloqueada=True;return self
        def first(self):return f['inclusion'] if self.ident==5 else None
    consulta=Consulta();auditorias=[]
    from decimal import InvalidOperation,ROUND_HALF_UP
    codigo_importe=ast.parse(Path('services/catalogos_comerciales.py').read_text())
    funcion_importe=next(n for n in codigo_importe.body if isinstance(n,ast.FunctionDef) and n.name=='importe_a_centavos')
    entorno_importe=dict(Decimal=__import__('decimal').Decimal,InvalidOperation=InvalidOperation,ROUND_HALF_UP=ROUND_HALF_UP)
    exec(compile(ast.Module(body=[funcion_importe],type_ignores=[]),'importe','exec'),entorno_importe)
    importe_a_centavos=entorno_importe['importe_a_centavos']
    contexto=dict(request=request,redirect=redirect,db=Obj(session=sesion),
        url_for=lambda *a,**k:'/panel#politicas',
        modelos={'CatalogoProducto':Obj(query=consulta)},dependencias={'registrar_auditoria':lambda *a,**k:auditorias.append(k)},
        acceso=lambda:(Obj(id=9),Obj(id=1),None),contexto_comercial=lambda *a:(Obj(id=2),[]),
        obtener_datos_panel_comercial=lambda *a,**k:{'simulaciones_canal':[f]},
        guardar_cobertura=guardar_cobertura,importe_a_centavos=importe_a_centavos)
    exec(compile(ast.Module(body=[funcion],type_ignores=[]),'ruta','exec'),contexto)
    app=Flask(__name__);app.add_url_rule('/guardar',view_func=contexto['guardar_cobertura_precio'],methods=['POST'])
    datos=dict(unidad_negocio_id='2',catalogo_producto_id='5',lista_precio_id='6',
        cuenta_codigo='CUENTA-UAT',publicacion='PUB-UAT',variante='',modo_embalaje='adicional',
        embalaje_adicional='100.00',referencia_embalaje='Ensayo',huella_calculo=f['trazabilidad_economica']['huella_enlace'])
    if cambio=='otra_unidad':datos['unidad_negocio_id']='9'
    if cambio=='otro_tenant':f['inclusion'].catalogo.organizacion_id=9
    if cambio=='huella':datos['huella_calculo']='vieja'
    if cambio=='linea_ajena':datos['detalle_embalaje_id']='999'
    r=app.test_client().post('/guardar',data=datos)
    assert r.status_code==302
    if cambio=='ninguno':assert sesion.commits==1 and auditorias and consulta.bloqueada
    else:assert sesion.commits==0 and not auditorias


def test_formulario_descarta_cancelacion_bloquea_enter_y_separa_modos():
    import subprocess
    script=r'''
    const fs=require('fs'),vm=require('vm'),assert=require('assert');
    const eventos={},cambios={},cerrar={};
    const modo={value:'incluido',addEventListener:(n,f)=>cambios[n]=f};
    const adicional={disabled:false};const linea={disabled:false};
    const dialogo={addEventListener:(n,f)=>cerrar[n]=f};
    let reinicios=0,aceptar=false;
    const form={querySelector:s=>s.includes('modo_embalaje')?modo:adicional,
        querySelectorAll:()=>[linea],closest:()=>dialogo,
        reset:()=>{reinicios++;modo.value='incluido';},
        addEventListener:(n,f)=>eventos[n]=f};
    vm.runInNewContext(fs.readFileSync('static/cobertura_precio.js','utf8'),{
        document:{querySelectorAll:()=>[form]},window:{confirm:()=>aceptar},queueMicrotask:f=>f()});
    assert(adicional.disabled&&!linea.disabled);
    modo.value='adicional';cambios.change();assert(!adicional.disabled&&linea.disabled);
    modo.value='sin_costo';cambios.change();assert(adicional.disabled&&linea.disabled);
    cerrar.close();assert.equal(reinicios,1);assert(adicional.disabled&&!linea.disabled);
    let frenado=false;eventos.keydown({key:'Enter',target:{tagName:'INPUT'},preventDefault:()=>frenado=true});assert(frenado);
    frenado=false;eventos.submit({preventDefault:()=>frenado=true});assert(frenado);
    aceptar=true;frenado=false;eventos.submit({preventDefault:()=>frenado=true});assert(!frenado);
    '''
    subprocess.run(['node','-e',script],check=True,capture_output=True,text=True)
