"""Fuente única de USD/ARS y desgaste de consumibles, sin mano de obra ni red."""
from datetime import date,datetime
from zoneinfo import ZoneInfo
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from types import SimpleNamespace
from sqlalchemy import inspect
from sqlalchemy.orm import object_session
from models.cotizaciones import CotizacionDolar as D,DesgasteLaserVersion as L
from models.organizacion import Organizacion
from models.unidad_negocio import UnidadNegocio
from models.fuentes_costo_productivo import MaquinaProductiva as M,MaquinaCostoVersion as V
from services.catalogos_comerciales import importe_a_centavos
from scripts.preparar_cotizaciones import preparado

PREDETERMINADOS=[dict(nombre='Tubo láser',usd='1500.00',horas='8000'),dict(nombre='Espejos',usd='20.00',horas='8000'),dict(nombre='Lente',usd='70.00',horas='8000')]
CODIGO_LASER='laser-comun'

def hoy():return datetime.now(ZoneInfo('America/Buenos_Aires')).date()

def limpiar_cache():
    from flask import has_request_context,g
    if has_request_context():g.pop('_tarifas_laser_dolar',None)

def exigir(session):
    if not preparado(session.connection()):raise ValueError('Falta preparar Cotizaciones en staging.')

def actual(org,session):return session.query(D).filter_by(organizacion_id=org,vigente=True).populate_existing().first()

def configuracion(org,unidad,session):return session.query(L).filter_by(organizacion_id=org,unidad_negocio_id=unidad,vigente=True).populate_existing().first()

def bloquear(org,session):
    if session.query(Organizacion).filter_by(id=org).with_for_update().first() is None:raise ValueError('La empresa no existe.')

def importe(valor,nombre):
    try:n=importe_a_centavos(str(valor or ''))
    except (ValueError,InvalidOperation,OverflowError):raise ValueError(nombre+': usá un importe como 1500,25, sin símbolos.') from None
    if not 0<n<=100000000000:raise ValueError(nombre+' debe ser positivo y estar dentro de rango.')
    return n

def guardar_dolar(datos,org,usuario,session):
    exigir(session);bloquear(org,session)
    previo=actual(org,session)
    if str(previo.id if previo else '')!=str(datos.get('version_dolar') or ''):raise ValueError('La cotización cambió. Volvé a abrir el formulario.')
    valor=importe(datos.get('valor_dolar'),'Cotización')
    try:fecha=date.fromisoformat(str(datos.get('fecha_cotizacion') or ''))
    except ValueError:raise ValueError('Ingresá una fecha válida.') from None
    if fecha>hoy() or (previo and fecha<previo.fecha_cotizacion):raise ValueError('La fecha no puede ser futura ni anterior a la cotización vigente.')
    referencia=str(datos.get('observacion',datos.get('referencia')) or '').strip().upper()
    if not referencia or len(referencia)>200:raise ValueError('Completá una referencia de hasta 200 caracteres.')
    if previo and (previo.valor_centavos,previo.fecha_cotizacion,previo.referencia)==(valor,fecha,referencia):return previo
    candidato=SimpleNamespace(valor_centavos=valor,id=0,numero_version=(previo.numero_version+1 if previo else 1),fecha_cotizacion=fecha)
    for config in session.query(L).filter_by(organizacion_id=org,vigente=True):calcular(config,candidato)
    if previo:previo.vigente=False;session.flush()
    n=(session.query(D.numero_version).filter_by(organizacion_id=org).order_by(D.numero_version.desc()).first() or (0,))[0]+1
    r=D(organizacion_id=org,numero_version=n,valor_centavos=valor,fecha_cotizacion=fecha,referencia=referencia,creado_por_usuario_id=usuario)
    session.add(r);session.flush();limpiar_cache();return r

def consumibles(valores,horas):
    if len(valores)!=3 or len(horas)!=3:raise ValueError('Completá tubo, espejos y lente.')
    salida=[]
    for base,v,h in zip(PREDETERMINADOS,valores,horas):
        centavos=importe(v,base['nombre'])
        try:n=Decimal(str(h).strip().replace(',','.'))
        except InvalidOperation:raise ValueError('Vida útil inválida.') from None
        if not n.is_finite() or not 0<n<=1000000 or n.as_tuple().exponent < -6:raise ValueError('La vida útil debe ser positiva, hasta seis decimales.')
        salida.append(dict(nombre=base['nombre'],usd_centavos=centavos,horas=str(n)))
    return salida

def calcular(config,dolar):
    if dolar is None:raise ValueError('Cargá la cotización general del dólar antes de calcular el desgaste láser.')
    valor=Decimal(dolar.valor_centavos)/100
    hora=sum((Decimal(r['usd_centavos'])*valor/Decimal(r['horas']) for r in config.consumibles),Decimal(0))
    minuto=hora/60
    if hora>Decimal('99999999999999'):raise ValueError('El desgaste calculado está fuera de rango.')
    redondear=lambda n:int(n.quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    return SimpleNamespace(vigente=True,numero_version=config.numero_version,modo_dolar=True,
        costo_minuto_centavos=redondear(minuto),costo_hora_centavos=redondear(hora),
        cotizacion_id=dolar.id,configuracion_id=config.id,
        observacion=f'Desgaste láser: USD/ARS v{dolar.numero_version}, {valor}, fecha {dolar.fecha_cotizacion}; configuración v{config.numero_version} (id {config.id}). Sólo tubo, espejos y lente; energía y mantenimiento pendientes; sin mano de obra.')

def guardar_laser(datos,org,unidad,usuario,session):
    exigir(session);bloquear(org,session)
    u=session.query(UnidadNegocio).filter_by(id=unidad,organizacion_id=org,activa=True).first()
    if u is None:raise ValueError('La unidad no pertenece a la empresa o está inactiva.')
    dolar=actual(org,session)
    if dolar is None:raise ValueError('Primero cargá el dólar general. No se utiliza el valor histórico de $1.500.')
    anterior=configuracion(org,unidad,session)
    if str(anterior.id if anterior else '')!=str(datos.get('version_laser') or ''):raise ValueError('La configuración láser cambió. Volvé a abrir el formulario.')
    if str(dolar.id)!=str(datos.get('version_dolar') or ''):raise ValueError('El dólar cambió. Volvé a revisar el desgaste.')
    valores=consumibles(datos.getlist('consumible_usd'),datos.getlist('vida_horas'))
    calcular(SimpleNamespace(consumibles=valores,numero_version=1,id=0),dolar)
    maquina=session.query(M).filter_by(id=anterior.maquina_id,organizacion_id=org,unidad_negocio_id=unidad,activo=True).first() if anterior else None
    if anterior and maquina is None:raise ValueError('El recurso común fue modificado o desactivado; revisalo antes de continuar.')
    if not anterior:
        if session.query(M).filter_by(organizacion_id=org,codigo=CODIGO_LASER+'-'+str(unidad)).first():raise ValueError('El código laser-comun ya existe; revisá su identidad antes de configurar otra unidad.')
        maquina=M(organizacion_id=org,unidad_negocio_id=unidad,codigo=CODIGO_LASER+'-'+str(unidad),nombre='Corte láser — Mega Láser / Benelli',categoria='Desgaste de consumibles láser',activo=True,observacion='Recurso de costo común. Sólo consumibles; energía y mantenimiento pendientes. Mano de obra desde Personal.')
        session.add(maquina);session.flush()
    if session.query(V).filter_by(maquina_id=maquina.id,vigente=True).first():raise ValueError('Este recurso tiene otra tarifa vigente; resolvé la superposición antes de guardar.')
    if anterior and anterior.consumibles==valores:return anterior
    if anterior:anterior.vigente=False;session.flush()
    numero=(session.query(L.numero_version).filter_by(organizacion_id=org,unidad_negocio_id=unidad).order_by(L.numero_version.desc()).first() or (0,))[0]+1
    r=L(organizacion_id=org,unidad_negocio_id=unidad,maquina_id=maquina.id,numero_version=numero,consumibles=valores,creado_por_usuario_id=usuario)
    session.add(r);session.flush();limpiar_cache();return r

def tarifa_maquina(maquina):
    # Los dobles de prueba y las máquinas convencionales conservan su cálculo.
    estado=inspect(maquina,raiseerr=False)
    if estado is None:return None
    session=object_session(maquina)
    if session is None:return None
    from flask import has_request_context,g
    cache=getattr(g,'_tarifas_laser_dolar',{}) if has_request_context() else {}
    clave=(id(session),maquina.organizacion_id,maquina.id)
    if clave in cache:return cache[clave]
    resultado=None
    if preparado(session.connection()):
        c=session.query(L).filter_by(organizacion_id=maquina.organizacion_id,maquina_id=maquina.id,vigente=True).first()
        if c:
            if not maquina.activo or c.unidad_negocio_id!=maquina.unidad_negocio_id:raise ValueError('El recurso láser no corresponde a su unidad activa.')
            resultado=calcular(c,actual(maquina.organizacion_id,session))
    if has_request_context():cache[clave]=resultado;g._tarifas_laser_dolar=cache
    return resultado
