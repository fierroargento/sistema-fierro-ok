"""Datos, sueldos, horarios y ausencias en el mismo legajo de Personal."""
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
import re
from models.fuentes_costo_productivo import EmpleadoProductivo
from models.personas import NovedadLaboralPreparatoria
from models.unidad_negocio import UnidadNegocio
from models.personal_administrativo import PersonalDetalle, HorarioPersonal, AusenciaPersonal
from services.fuentes_costo_productivo import registrar_costo_empleado
from services.catalogos_comerciales import importe_a_centavos
from services.configuracion_costo_laboral import configuracion_vigente, validar_porcentaje
from services.recursos_productivos import recalcular_recursos_del_empleado

TEXTOS = {'dni':20,'cuil':20,'telefono':40,'email':200,'domicilio':300,'localidad':120,'provincia':120,'contacto_emergencia':200,'categoria':120,'convenio':160,'modalidad':120}
FECHAS = ('fecha_nacimiento','fecha_ingreso','fecha_egreso')
DIAS = ('Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo')


def fecha(valor, nombre, obligatorio=False):
    if not valor and not obligatorio:return None
    try:return date.fromisoformat(str(valor))
    except ValueError as error:raise ValueError(f'{nombre}: indicá una fecha válida.') from error


def datos_detalle(detalle):
    return {**{c:getattr(detalle,c) or '' for c in TEXTOS}, **{c:getattr(detalle,c).isoformat() if getattr(detalle,c) else '' for c in FECHAS}} if detalle else {c:'' for c in (*TEXTOS,*FECHAS)}


def guardar_detalle(e, form, db_session):
    valores = {}
    for campo,limite in TEXTOS.items():
        valor = str(form.get(campo) or '').strip()
        if len(valor)>limite:raise ValueError(f'{campo}: máximo {limite} caracteres.')
        valores[campo]=valor or None
    for campo in FECHAS:valores[campo]=fecha(form.get(campo),campo)
    if valores['fecha_egreso'] and not valores['fecha_ingreso']:raise ValueError('Completá la fecha de ingreso antes de la de egreso.')
    if valores['fecha_ingreso'] and valores['fecha_egreso'] and valores['fecha_egreso']<valores['fecha_ingreso']:raise ValueError('El egreso no puede ser anterior al ingreso.')
    if valores['fecha_nacimiento'] and valores['fecha_ingreso'] and valores['fecha_nacimiento']>valores['fecha_ingreso']:raise ValueError('Revisá las fechas de nacimiento e ingreso.')
    if valores['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',valores['email']):raise ValueError('Revisá el correo electrónico.')
    for campo,largo in [('dni',(7,8)),('cuil',(11,))]:
        if valores[campo]:
            numero=re.sub(r'[.\-\s]','',valores[campo])
            if not numero.isdecimal() or len(numero) not in largo:raise ValueError(f'Revisá {campo.upper()}: usá sólo números, puntos o guiones.')
            valores[campo]=numero
            ajeno=db_session.query(PersonalDetalle).join(EmpleadoProductivo).filter(
                EmpleadoProductivo.organizacion_id==e.organizacion_id,
                PersonalDetalle.empleado_id!=e.id,getattr(PersonalDetalle,campo)==numero).first()
            if ajeno:raise ValueError(f'{campo.upper()} ya está cargado en otro legajo de la organización.')
    detalle=db_session.get(PersonalDetalle,e.id)
    if detalle is None:detalle=PersonalDetalle(empleado_id=e.id,organizacion_id=e.organizacion_id);db_session.add(detalle)
    for campo,valor in valores.items():setattr(detalle,campo,valor)
    db_session.flush();return detalle


def version_actual(e):
    return next((v for v in e.versiones_costo if v.vigente and v.moneda=='ARS'),None)


def guardar_salario(e, form, *, modelos, db_session, usuario_id):
    actual=version_actual(e)
    if str(form.get('version_actual') or '') != str(actual.id if actual else ''):
        raise ValueError('El sueldo cambió mientras lo editabas. Recargá el legajo antes de guardar.')
    excepcion=str(form.get('porcentaje_cargas') or '').strip()
    general=configuracion_vigente(e.organizacion_id,e.unidad_negocio_id,Modelo=modelos['ConfiguracionCostoLaboralVersion']) if e.unidad_negocio_id else None
    porcentaje=validar_porcentaje(excepcion if excepcion else general.porcentaje_cargas if general else 0)
    observacion=str(form.get('observacion_sueldo') or '').strip()
    if len(observacion)>500:raise ValueError('La observación salarial supera 500 caracteres.')
    version=registrar_costo_empleado(e, moneda='ARS',
        sueldo_base_centavos=importe_a_centavos(form.get('sueldo_base')),
        adicionales_centavos=importe_a_centavos(form.get('adicionales') or 0),
        otros_costos_centavos=importe_a_centavos(form.get('otros_costos') or 0),
        porcentaje_cargas=porcentaje,usa_porcentaje_general=not bool(excepcion),
        horas_mensuales=form.get('horas_mensuales'),horas_productivas=form.get('horas_productivas'),
        ubicacion_trabajo=form.get('ubicacion_trabajo'),tipo_funcion=form.get('tipo_funcion'),
        porcentaje_productivo=form.get('porcentaje_productivo'),observacion=observacion,
        creado_por_usuario_id=usuario_id,EmpleadoCostoVersion=modelos['EmpleadoCostoVersion'],
        db_session=db_session,commit=False)
    # Todas las tarifas dependientes se actualizan en la misma transacción.
    db_session.expire(e,['versiones_costo'])
    recalcular_recursos_del_empleado(e,EmpleadoCostoVersion=modelos['EmpleadoCostoVersion'],db_session=db_session,usuario_id=usuario_id,commit=False)
    return version


def guardar_horario(e, form, db_session):
    try:
        dia=int(form.get('dia_semana'));entrada=time.fromisoformat(str(form.get('entrada')));salida=time.fromisoformat(str(form.get('salida')));pausa=int(form.get('pausa_minutos') or 0)
    except (ValueError,TypeError) as error:raise ValueError('Revisá el día, las horas y los minutos de pausa.') from error
    if entrada.tzinfo or salida.tzinfo:raise ValueError('Usá horarios locales sin zona horaria.')
    nocturno=form.get('nocturno')=='1'
    desde=fecha(form.get('desde'),'Vigente desde',True);hasta=fecha(form.get('hasta'),'Vigente hasta')
    a=entrada.hour*60+entrada.minute;b=salida.hour*60+salida.minute+(1440 if nocturno else 0)
    if not 0<=dia<=6 or not 0<b-a<=16*60 or not 0<=pausa<b-a or (hasta and hasta<desde):raise ValueError('El horario debe durar hasta 16 horas y la pausa debe ser menor que el turno. Revisá su vigencia.')
    if entrada.second or salida.second or entrada.microsecond or salida.microsecond:raise ValueError('Usá horas y minutos completos.')
    obs=str(form.get('observacion_horario') or '').strip()
    if len(obs)>500:raise ValueError('La observación supera 500 caracteres.')
    # Detectar cruces incluso entre domingo/lunes y los horarios nocturnos.
    for otro in db_session.query(HorarioPersonal).filter_by(empleado_id=e.id,estado='vigente').all():
        if otro.hasta and otro.hasta<desde or hasta and hasta<otro.desde:continue
        oa=otro.dia_semana*1440+otro.entrada.hour*60+otro.entrada.minute
        ob=otro.dia_semana*1440+otro.salida.hour*60+otro.salida.minute+(1440 if otro.nocturno else 0)
        na=dia*1440+a;nb=dia*1440+b
        if any(na<ob+desfase and oa+desfase<nb for desfase in (-10080,0,10080)):raise ValueError('El horario se superpone con otro vigente para este empleado.')
    obj=HorarioPersonal(empleado_id=e.id,dia_semana=dia,entrada=entrada,salida=salida,nocturno=nocturno,pausa_minutos=pausa,desde=desde,hasta=hasta,observacion=obs or None)
    db_session.add(obj);db_session.flush();return obj


def guardar_ausencia(e, form, db_session, usuario_id=None):
    tipo=form.get('tipo');desde=fecha(form.get('desde'),'Desde',True);hasta=fecha(form.get('hasta'),'Hasta',True)
    detalle=str(form.get('detalle') or '').strip();periodo=str(form.get('periodo') or '').strip()
    if tipo not in {'vacaciones','licencia','ausencia'} or hasta<desde or not detalle or len(detalle)>500 or len(periodo)>40:raise ValueError('Revisá tipo, fechas, período y detalle de la ausencia.')
    texto=str(form.get('dias_computados') or '').strip();dias=None
    if texto:
        try:dias=Decimal(texto.replace(',','.'))
        except InvalidOperation as error:raise ValueError('Los días computados no son válidos.') from error
        if not dias.is_finite() or dias<0 or dias>3660 or dias.as_tuple().exponent<-2:raise ValueError('Los días computados deben ser positivos o cero, con hasta dos decimales.')
    if db_session.query(NovedadLaboralPreparatoria.id).filter(
        NovedadLaboralPreparatoria.organizacion_id==e.organizacion_id,
        NovedadLaboralPreparatoria.empleado_id==e.id,
        NovedadLaboralPreparatoria.tipo.in_(['licencia','ausencia']),
        NovedadLaboralPreparatoria.estado=='propuesta',
        NovedadLaboralPreparatoria.fecha_desde<=hasta,
        NovedadLaboralPreparatoria.fecha_hasta>=desde).first():
        raise ValueError('Ya hay vacaciones o una licencia planificada en esas fechas.')
    unidad=e.unidad_negocio or db_session.query(UnidadNegocio).filter_by(organizacion_id=e.organizacion_id,activa=True).order_by(UnidadNegocio.id).first()
    if unidad is None:raise ValueError('Configurá una unidad activa para registrar vacaciones y licencias.')
    from services.personas_preparatorias import crear_novedad
    novedad=crear_novedad({'tipo':'ausencia' if tipo=='ausencia' else 'licencia',
        'fecha_desde':desde.isoformat(),'fecha_hasta':hasta.isoformat(),'detalle':detalle},
        empleado=e,organizacion_id=e.organizacion_id,unidad_negocio_id=unidad.id,
        Novedad=NovedadLaboralPreparatoria,db_session=db_session,usuario_id=usuario_id,commit=False)
    obj=AusenciaPersonal(empleado_id=e.id,novedad_id=novedad.id,novedad=novedad,tipo=tipo,periodo=periodo or None,dias_computados=dias)
    db_session.add(obj);db_session.flush();return obj
