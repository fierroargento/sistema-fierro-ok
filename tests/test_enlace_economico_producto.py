"""Prueba el recorrido real costo -> regla -> motor y su alcance declarado."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace as Obj
import json

import pytest

from services.enlace_economico_producto import construir_enlaces
from services.control_comercial_masivo import construir_bandeja
from services.cola_acciones_comerciales import planificar_fila, propuesta_esta_vigente
from services.motor_comercial_canal import liquidar_precio

AHORA=datetime(2026,10,19,16)


def fuentes():
    fecha=dict(vigente=True,estado='vigente',vigente_desde=AHORA-timedelta(days=1),vigente_hasta=None,numero_version=1)
    producto=Obj(id=7,organizacion_id=1,sku='UAT-PRODUCTO')
    detalle=Obj(tipo='insumo',codigo='MP',concepto='Material',cantidad=Decimal('2.1'),
        unidad_medida='kg',costo_unitario_centavos=10000,porcentaje_merma=0,
        subtotal_centavos=21000,orden=0,observacion=None)
    costo=Obj(id=10,organizacion_id=1,unidad_negocio_id=2,producto_id=7,
        producto=producto,moneda='ARS',tipo='manual',costo_total_centavos=21000,
        detalles=[detalle],**fecha)
    perfil=Obj(id=12,organizacion_id=1,unidad_negocio_id=2,producto_id=7,tipo='simple',activo=True)
    catalogo=Obj(id=4,organizacion_id=1,unidad_negocio_id=2,nombre='Catálogo UAT')
    inclusion=Obj(id=5,producto_id=7,producto=producto,catalogo_id=4,catalogo=catalogo,activo=True)
    economica=Obj(id=13,organizacion_id=1,unidad_negocio_id=2,catalogo_id=None,producto_id=7,
        alcance='producto',clave_alcance='producto:2:7',impuesto_pct=Decimal('5'),metodo_impuesto='sobre_costo',
        utilidad_minima_pct=Decimal('20'),utilidad_objetivo_pct=Decimal('30'),metodo_utilidad='sobre_costo',
        incremento_redondeo_centavos=1,nombre='Regla UAT',**fecha)
    lista=Obj(id=6,organizacion_id=1,unidad_negocio_id=2,moneda='ARS',estado='preparatorio',tipo='mercadolibre',nombre='ML UAT')
    canal=Obj(id=14,lista_precio_id=6,lista_precio=lista,nombre='Política UAT',comision_pct=Decimal('15'),
        publicidad_pct=Decimal('2'),financiacion_pct=Decimal('3'),devoluciones_pct=Decimal('1'),
        incremento_redondeo_centavos=100,umbral_envio_centavos=33000,costo_envio_default_centavos=6000,
        tramos=[Obj(precio_desde_centavos=0,precio_hasta_centavos=33000,cargo_fijo_centavos=1000),
            Obj(precio_desde_centavos=33000,precio_hasta_centavos=None,cargo_fijo_centavos=0)],**fecha)
    return dict(costos=[costo],inclusiones=[inclusion],reglas_economicas=[economica],
        reglas_canal=[canal],perfiles=[perfil],modelo_costo=None)


def ejecutar(d=None):
    return construir_enlaces(organizacion_id=1,unidad_negocio_id=2,ahora=AHORA,**(d or fuentes()))


def test_recorrido_completo_respeta_minimo_y_no_duplica_costo():
    d=fuentes();antes=deepcopy(d);pisos,filas,bloqueos=ejecutar(d)
    assert len(filas)==1 and not bloqueos
    fila=filas[0];traza=fila['trazabilidad_economica'];minimo=fila['minimo']
    assert pisos[0]['pisos']['minimo']['piso_liquidacion_centavos']==26250
    assert minimo['piso_liquidacion_centavos']==26250 and minimo['liquidacion_centavos']>=26250
    assert traza['costo']['costo_total_centavos']==21000
    assert not traza['embalaje_verificado'] and not traza['habilita_publicacion']
    assert not traza['cargos_contrastados_cuenta'] and len(traza['faltantes'])==2
    canal=d['reglas_canal'][0]
    for precio in range(0,minimo['precio_final_centavos'],canal.incremento_redondeo_centavos):
        r=liquidar_precio(precio,comision_pct=canal.comision_pct,publicidad_pct=canal.publicidad_pct,
            financiacion_pct=canal.financiacion_pct,devoluciones_pct=canal.devoluciones_pct,
            tramos=canal.tramos,umbral_envio_centavos=canal.umbral_envio_centavos,costo_envio_centavos=6000)
        assert r['liquidacion_centavos']<26250
    assert d['costos'][0].costo_total_centavos==antes['costos'][0].costo_total_centavos
    assert d['costos'][0].estado=='vigente'


@pytest.mark.parametrize('cambio',['sin_perfil','perfil_inactivo','perfil_otra_unidad','sin_detalle','total_erroneo',
    'subtotal_erroneo','costo_otra_org','costo_futuro','costo_vencido','costo_doble','costo_usd',
    'catalogo_doble','catalogo_otra_org','producto_otra_org','catalogo_inactivo','sin_regla','regla_doble',
    'regla_otra_org','regla_futura','regla_estado','regla_clave_erronea','politica_doble','politica_futura',
    'lista_usd','lista_otra_unidad','lista_archivada','porcentaje_ausente','sin_tramos','tramo_hueco','tramo_solapado','tramo_sin_final'])
def test_fuentes_incompletas_ambiguas_o_ajenas_se_explican_sin_precio(cambio):
    d=fuentes();c=d['costos'][0];p=d['perfiles'][0];i=d['inclusiones'][0];r=d['reglas_economicas'][0];canal=d['reglas_canal'][0]
    if cambio=='sin_perfil':d['perfiles']=[]
    if cambio=='perfil_inactivo':p.activo=False
    if cambio=='perfil_otra_unidad':p.unidad_negocio_id=9
    if cambio=='sin_detalle':c.detalles=[]
    if cambio=='total_erroneo':c.costo_total_centavos+=1
    if cambio=='subtotal_erroneo':c.detalles[0].subtotal_centavos+=1
    if cambio=='costo_otra_org':c.organizacion_id=9
    if cambio=='costo_futuro':c.vigente_desde=AHORA+timedelta(seconds=1)
    if cambio=='costo_vencido':c.vigente_hasta=AHORA
    if cambio=='costo_doble':d['costos'].append(deepcopy(c));d['costos'][1].id+=1
    if cambio=='costo_usd':c.moneda='USD'
    if cambio=='catalogo_doble':d['inclusiones'].append(deepcopy(i));d['inclusiones'][1].id+=1
    if cambio=='catalogo_otra_org':i.catalogo.organizacion_id=9
    if cambio=='producto_otra_org':i.producto.organizacion_id=9
    if cambio=='catalogo_inactivo':i.activo=False
    if cambio=='sin_regla':d['reglas_economicas']=[]
    if cambio=='regla_doble':d['reglas_economicas'].append(deepcopy(r))
    if cambio=='regla_otra_org':r.organizacion_id=9
    if cambio=='regla_futura':r.vigente_desde=AHORA+timedelta(seconds=1)
    if cambio=='regla_estado':r.estado='cancelado'
    if cambio=='regla_clave_erronea':r.producto_id=99
    if cambio=='politica_doble':d['reglas_canal'].append(deepcopy(canal))
    if cambio=='politica_futura':canal.vigente_desde=AHORA+timedelta(seconds=1)
    if cambio=='lista_usd':canal.lista_precio.moneda='USD'
    if cambio=='lista_otra_unidad':canal.lista_precio.unidad_negocio_id=9
    if cambio=='lista_archivada':canal.lista_precio.estado='archivado'
    if cambio=='porcentaje_ausente':canal.publicidad_pct=None
    if cambio=='sin_tramos':canal.tramos=[]
    if cambio=='tramo_hueco':canal.tramos[1].precio_desde_centavos+=1
    if cambio=='tramo_solapado':canal.tramos[1].precio_desde_centavos-=1
    if cambio=='tramo_sin_final':canal.tramos[-1].precio_hasta_centavos=99999
    _,filas,bloqueos=ejecutar(d)
    assert not filas and bloqueos and all(b['motivo'] for b in bloqueos)


def test_prioridad_de_regla_es_la_existente_y_no_hay_fallback_de_una_excepcion_invalida():
    d=fuentes();especifica=d['reglas_economicas'][0];general=deepcopy(especifica)
    general.id=40;general.alcance='organizacion';general.clave_alcance='organizacion'
    general.unidad_negocio_id=None;general.producto_id=None
    d['reglas_economicas'].append(general)
    assert ejecutar(d)[1][0]['regla'].id==especifica.id
    especifica.vigente_hasta=AHORA
    assert not ejecutar(d)[1] and ejecutar(d)[2]


def test_fecha_con_zona_y_orden_de_entrada_no_cambian_la_huella():
    d=fuentes();uno=ejecutar(d)[1][0]['trazabilidad_economica']['huella_enlace']
    d['reglas_canal'][0].tramos.reverse()
    for grupo in ['costos','reglas_economicas','reglas_canal']:
        for r in d[grupo]:r.vigente_desde=r.vigente_desde.replace(tzinfo=timezone.utc)
    # La representación temporal se normaliza en el snapshot.
    dos=ejecutar(d)[1][0]['trazabilidad_economica']['huella_enlace']
    assert uno==dos


def test_cambio_de_version_aunque_conserve_precio_invalida_propuesta():
    d=fuentes();sim=ejecutar(d)[1]
    filas,_=construir_bandeja(sim,[])
    especificacion=planificar_fila(filas[0])[0]
    propuesta=Obj(tipo_accion=especificacion['tipo_accion'],huella_calculo=especificacion['huella_calculo'])
    assert propuesta_esta_vigente(propuesta,filas[0])
    d['reglas_economicas'][0].id+=1;d['reglas_economicas'][0].numero_version+=1
    nuevas,_=construir_bandeja(ejecutar(d)[1],[])
    assert nuevas[0]['minimo']['precio_final_centavos']==filas[0]['minimo']['precio_final_centavos']
    assert not propuesta_esta_vigente(propuesta,nuevas[0])
    assert json.loads(especificacion['snapshot_json'])['huella_enlace_economico']


def produccion(d):
    p=d['perfiles'][0];p.tipo='produccion';p.operaciones_costeo=[];p.maquinas_costeo=[];p.costos_fijos_costeo=[]
    # Es la composición real que consume construir_detalles, no un resultado simulado.
    insumo=Obj(codigo='MP',nombre='Material',unidad_medida='kg',versiones_precio=[Obj(vigente=True,moneda='ARS',precio_unitario_centavos=10000)])
    p.insumos_costeo=[Obj(insumo=insumo,cantidad=Decimal('2.1'),porcentaje_merma=0,observacion=None)]
    d['costos'][0].tipo='calculado'
    return p


def test_ficha_productiva_actual_se_usa_y_cambio_de_fuentes_bloquea():
    d=fuentes();p=produccion(d)
    assert ejecutar(d)[1]
    p.insumos_costeo[0].insumo.versiones_precio[0].precio_unitario_centavos=12000
    _,filas,bloqueos=ejecutar(d)
    assert not filas and 'cambiaron' in bloqueos[0]['motivo']


def test_modal_usa_estilos_y_eventos_existentes_y_explica_limites():
    from flask import Flask
    from jinja2 import FileSystemLoader
    app=Flask(__name__);app.jinja_loader=FileSystemLoader('templates')
    fila=ejecutar()[1][0]
    with app.test_request_context():
        html=app.jinja_env.get_template('partials/enlace_economico_dialog.html').render(fila=fila)
    assert 'catalog-product-dialog' in html and 'data-close-catalog-dialog' in html
    assert 'Gestionar' not in html and 'Neto calculado' in html
    assert 'Versión 1' in html and 'Embalaje' not in html and 'embalaje' in html
    assert 'no certifica rentabilidad real' in html and 'method="dialog"' in html


def test_combo_reutiliza_composicion_existente_y_cambio_de_componente_bloquea():
    d=fuentes();p=d['perfiles'][0];p.tipo='combo'
    componente=Obj(producto_id=8,producto=Obj(sku='COMPONENTE',descripcion='Componente'))
    p.componentes_combo=[Obj(componente=componente,cantidad=Decimal('2.1'),observacion=None)]
    costo_componente=Obj(costo_total_centavos=10000)
    class Consulta:
        def filter_by(self,**contexto):
            assert contexto==dict(organizacion_id=1,unidad_negocio_id=2,producto_id=8,moneda='ARS',vigente=True)
            return self
        def first(self):return costo_componente
    d['modelo_costo']=Obj(query=Consulta())
    c=d['costos'][0];c.tipo='calculado';detalle=c.detalles[0]
    detalle.tipo='elaboracion';detalle.codigo='COMPONENTE';detalle.concepto='Componente';detalle.unidad_medida='unidad'
    assert ejecutar(d)[1]
    costo_componente.costo_total_centavos+=1
    assert not ejecutar(d)[1]


def test_exportacion_existente_conserva_huella_y_versiones():
    from io import BytesIO
    from openpyxl import load_workbook
    from services.control_comercial_masivo import exportar_bandeja_excel
    filas,_=construir_bandeja(ejecutar()[1],[])
    hoja=load_workbook(exportar_bandeja_excel(filas)).active
    fila=dict(zip([c.value for c in hoja[1]],[c.value for c in hoja[2]]))
    assert fila['COSTO_VERSION_ID']==10 and fila['REGLA_ECONOMICA_ID']==13
    assert fila['POLITICA_CANAL_ID']==14 and fila['CATALOGO_PRODUCTO_ID']==5
    assert fila['HUELLA_ENLACE']==filas[0]['trazabilidad_economica']['huella_enlace']
    assert fila['ALCANCE']=='estimacion_segun_versiones_internas'


def test_consulta_existente_usa_el_enlace_y_conserva_bloqueos():
    """Ejecuta la función real de consulta con dobles de ORM; no inicia Flask/app."""
    import ast
    from pathlib import Path
    codigo=ast.parse(Path('services/comercial_consultas.py').read_text())
    funcion=next(n for n in codigo.body if isinstance(n,ast.FunctionDef) and n.name=='obtener_datos_panel_comercial')
    d=fuentes();inclusion=d['inclusiones'][0];inclusion.nombre_comercial='UAT'
    class Col:
        def __eq__(self,otro):return self
        def __or__(self,otro):return self
        def is_(self,otro):return self
        def asc(self):return self
        def desc(self):return self
    class Consulta:
        def __init__(self,filas):self.filas=filas;self.filtros=[]
        def filter_by(self,**filtros):self.filtros.append(filtros);return self
        def filter(self,*a):return self
        def order_by(self,*a):return self
        def join(self,*a):return self
        def all(self):return self.filas
    class Meta(type):
        def __getattr__(cls,nombre):return Col()
    def modelo(filas):return Meta('Modelo',(),{'query':Consulta(filas)})
    modelos={nombre:modelo([]) for nombre in ['UnidadNegocio','Producto','Catalogo','CatalogoProducto','CostoProductoVersion',
        'ListaPrecio','PoliticaComercialLista','ListaPrecioItem','ReglaEconomicaVersion','ReglaCanalVersion',
        'PromocionCanalObservacion','PropuestaAccionComercial','ObservacionComercialCanal','ReglaValidacionCanalVersion','PerfilCosteoProducto']}
    for nombre,filas in [('CatalogoProducto',d['inclusiones']),('CostoProductoVersion',d['costos']),
        ('ReglaEconomicaVersion',d['reglas_economicas']),('ReglaCanalVersion',d['reglas_canal']),
        ('PerfilCosteoProducto',d['perfiles'])]:modelos[nombre].query.filas=filas
    def enlace(**k):return construir_enlaces(**k,ahora=AHORA)
    entorno=dict(construir_enlaces=enlace,calcular_completitud=lambda *a:(100,[]),construir_bandeja=construir_bandeja,
        construir_tablero=lambda *a:([],{},[]),construir_control_motores=lambda *a:{},
        construir_plan_transicion=lambda *a:{},construir_ensayo_transicion=lambda *a:{},
        cargar_json=lambda *a:{},numero_visual=str,presentar_atributos=lambda *a:[],presentar_variantes=lambda *a:[])
    exec(compile(ast.Module(body=[funcion],type_ignores=[]),'consulta','exec'),entorno)
    resultado=entorno['obtener_datos_panel_comercial'](1,2,modelos=modelos)
    assert len(resultado['control_comercial'])==1 and not resultado['bloqueos_enlace_economico']
    assert modelos['PerfilCosteoProducto'].query.filtros==[{'organizacion_id':1,'unidad_negocio_id':2}]
    d['costos'][0].costo_total_centavos+=1
    resultado=entorno['obtener_datos_panel_comercial'](1,2,modelos=modelos)
    assert not resultado['simulaciones_canal'] and not resultado['control_comercial']
    assert resultado['bloqueos_enlace_economico']


def test_catalogo_inactivo_no_hace_ambiguo_un_destino_activo():
    d=fuentes();anterior=deepcopy(d['inclusiones'][0]);anterior.id+=10;anterior.activo=False
    d['inclusiones'].append(anterior)
    assert ejecutar(d)[1] and not ejecutar(d)[2]


def test_panel_completo_contiene_modal_y_pendientes_en_seccion_existente():
    from flask import Flask
    from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
    app=Flask(__name__)
    app.jinja_loader=ChoiceLoader([DictLoader({'base.html':'{% block extra_head %}{% endblock %}{% block content %}{% endblock %}'}),FileSystemLoader('templates')])
    fila=ejecutar()[1][0]
    with app.test_request_context():
        html=app.jinja_env.get_template('admin_comercial.html').render(
            url_for=lambda *a,**k:'#',organizacion=Obj(nombre='UAT'),unidad_activa=Obj(id=2,nombre='UAT'),unidades=[],
            simulaciones_canal=[fila],bloqueos_enlace_economico=[{'sku':'OTRO','lista_id':6,'motivo':'Revisar fuente'}],
            resumen_control_comercial={},resumen_preparacion={},control_motores={'resumen':{}},
            plan_transicion_motores={'resumen':{}},ensayo_transicion_motores={'resumen':{}})
    assert 'Simulación sin publicar' in html and 'Cálculos pendientes de revisión · 1' in html
    assert 'data-open-catalog-dialog="enlace-economico-10-14"' in html
    assert 'id="enlace-economico-10-14"' in html and 'Revisar fuente' in html
