"""Administración de la identidad del personal, compartida con Producción."""
from flask import Blueprint, redirect, render_template, request, session, url_for, jsonify, abort
from sqlalchemy import or_, func
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from services.tenant_context import TenantError, resolver_tenant_usuario
from services.personal_admin import datos_empleado, guardar_personal, huella_empleado
from scripts.preparar_personal import preparado, preparar
from models.personal_administrativo import PersonalDetalle, HorarioPersonal, AusenciaPersonal, PersonalAcceso
from services.personal_accesos import estado_accesos, guardar_accesos, leer_codigo_alarma, formulario_publico
from services.personal_alta_integral import completar_alta
from services.personal_legajo import datos_detalle, guardar_salario, guardar_horario, guardar_ausencia, version_actual, DIAS
from services.seguridad_entorno import laboratorio_forzado, entorno_actual
import os


def crear_blueprint_personal(*, dependencias):
    bp = Blueprint('admin_personal', __name__)
    db = dependencias['db']
    m = dependencias['modelos']

    def acceso():
        usuario = dependencias['usuario_actual']()
        try:
            mem = resolver_tenant_usuario(usuario,
                UsuarioOrganizacion=dependencias['UsuarioOrganizacion'],
                organizacion_id=session.get('organizacion_id'))
        except TenantError as error:
            return None, None, redirect(url_for('inicio', error=str(error)))
        if mem.rol != 'admin':
            return None, None, redirect(url_for('inicio'))
        session['organizacion_id'] = mem.organizacion_id
        return usuario, mem.organizacion, None

    def usuarios_disponibles(o):
        return m['UsuarioOrganizacion'].query.filter_by(organizacion_id=o.id).join(m['UsuarioSistema']).order_by(m['UsuarioSistema'].username).all()

    def resumenes(empleados, listo):
        ids=[e.id for e in empleados]
        salarios=m['EmpleadoCostoVersion'].query.filter(m['EmpleadoCostoVersion'].empleado_id.in_(ids),m['EmpleadoCostoVersion'].vigente.is_(True),m['EmpleadoCostoVersion'].moneda=='ARS').all() if ids else []
        sueldos={v.empleado_id:'ARS '+format(Decimal(v.sueldo_base_centavos)/100,'.2f') for v in salarios}
        horarios={i:[] for i in ids}
        if listo and ids:
            for h in HorarioPersonal.query.filter(HorarioPersonal.empleado_id.in_(ids),HorarioPersonal.estado=='vigente').order_by(HorarioPersonal.dia_semana,HorarioPersonal.entrada).all():
                horarios[h.empleado_id].append(f"{DIAS[h.dia_semana]} {h.entrada.strftime('%H:%M')}–{h.salida.strftime('%H:%M')}"+(' (+1 día)' if h.nocturno else ''))
        return {i:{'sueldo_resumen':sueldos.get(i,'Sin sueldo cargado'),'horario_resumen':' · '.join(horarios[i]) or 'Sin horario cargado'} for i in ids}

    def pintar(o, *, error='', formulario=None):
        unidades = m['UnidadNegocio'].query.filter_by(organizacion_id=o.id).order_by(m['UnidadNegocio'].nombre).all()
        filtro = (request.values.get('buscar') or '').strip()[:120]
        consulta = m['EmpleadoProductivo'].query.filter_by(organizacion_id=o.id, tipo_registro='empleado')
        if filtro:
            consulta = consulta.filter(or_(*(func.lower(getattr(m['EmpleadoProductivo'], c)).contains(filtro.lower(), autoescape=True)
                                            for c in ('codigo', 'nombre', 'sector', 'puesto'))))
        try:
            pagina = max(1, int(request.values.get('pagina', 1)))
        except (ValueError, TypeError):
            pagina = 1
        total = consulta.count()
        paginas = max(1, (total + 24) // 25)
        pagina = min(pagina, paginas)
        empleados = consulta.order_by(m['EmpleadoProductivo'].nombre, m['EmpleadoProductivo'].id).offset((pagina-1)*25).limit(25).all()
        listo = preparado(db.engine)
        detalles = {d.empleado_id:d for d in db.session.query(PersonalDetalle).filter(PersonalDetalle.empleado_id.in_([e.id for e in empleados])).all()} if listo and empleados else {}
        laborales=resumenes(empleados,listo)
        filas = [dict(datos_empleado(e), **datos_detalle(detalles.get(e.id)), **laborales[e.id], **estado_accesos(e,db.session), huella=huella_empleado(e,detalle=detalles.get(e.id),preparado=listo)) for e in empleados]
        return render_template('admin_personal.html', organizacion=o, empleados=empleados,
            filas_personal=filas, resumenes_laborales=laborales, usuarios_personal=usuarios_disponibles(o), unidades=unidades, unidad_inicial=session.get('unidad_negocio_id'),
            buscar=filtro, pagina=pagina, paginas=paginas, total=total,
            preparado=listo, puede_preparar=entorno_actual()=='staging' and laboratorio_forzado(),
            formulario_error=formulario, error=error, ok_feedback=request.args.get('ok', ''))

    @bp.route('/admin/personal', methods=['GET', 'POST'])
    @dependencias['login_required']
    def panel():
        usuario, o, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        if request.method == 'POST':
            try:
                if any(request.form.get(c)=='1' for c in ('datos_ampliados_presentados','accesos_presentados','cargar_sueldo_inicial','cargar_horario_inicial')) and not preparado(db.engine):
                    raise ValueError('Prepará el módulo Personal antes de guardar los datos ampliados.')
                empleado = guardar_personal(request.form, organizacion_id=o.id, modelos=m, db_session=db.session)
                completar_alta(empleado,request.form,modelos=m,db_session=db.session,usuario_id=getattr(usuario,'id',None))
                guardar_accesos(empleado,request.form,organizacion=o,modelos=m,db_session=db.session,creador=usuario)
                db.session.commit()
                # El registrador central de auditoría administra su propio commit.
                dependencias['registrar_auditoria']('Guardó ficha de Personal', entidad='empleado',
                    entidad_id=empleado.id, detalle=f"Ficha administrativa: {empleado.codigo}. Acción: {request.form.get('accion')}.")
                if str(request.form.get('volver_ficha') or '') == str(empleado.id):
                    return redirect(url_for('admin_personal.ficha',empleado_id=empleado.id,ok='Datos generales guardados correctamente.'))
                return redirect(url_for('admin_personal.panel', buscar=request.form.get('buscar', '')[:120],
                    pagina=request.form.get('pagina', 1), ok='Ficha de personal guardada correctamente.'))
            except (ValueError, IntegrityError) as error:
                db.session.rollback()
                mensaje = 'El legajo, DNI o CUIL ya existe en la organización. Revisá los empleados cargados.' if isinstance(error, IntegrityError) else str(error)
                return pintar(o, error=mensaje, formulario=formulario_publico(request.form)), 400
        return pintar(o)

    @bp.route('/admin/personal/preparar', methods=['POST'])
    @dependencias['login_required']
    def preparar_modulo():
        _, o, respuesta = acceso()
        if respuesta is not None:return respuesta
        if not (entorno_actual() == 'staging' and laboratorio_forzado()):
            return pintar(o,error='La preparación web sólo está disponible en staging desconectado.'),400
        rama=os.getenv('RENDER_GIT_BRANCH','');url=os.getenv('RENDER_EXTERNAL_URL','')
        if rama and rama != 'integracion-saas-2026-09' or url and 'staging' not in url:
            return pintar(o,error='El servicio no corresponde al staging de integración.'),400
        try:
            db.session.rollback()
            mensaje=preparar(db.engine)
            return redirect(url_for('admin_personal.panel',ok=mensaje))
        except ValueError as error:return pintar(o,error=str(error)),400

    def empleado_de_org(o, ident, bloquear=False):
        q=m['EmpleadoProductivo'].query.filter_by(id=ident,organizacion_id=o.id,tipo_registro='empleado')
        return (q.with_for_update() if bloquear else q).first()

    @bp.route('/admin/personal/costos', methods=['POST'])
    @dependencias['login_required']
    def costos():
        _,o,respuesta=acceso()
        if respuesta is not None:return respuesta
        ident=str(request.form.get('empleado_id') or '')
        e=empleado_de_org(o,int(ident)) if ident.isdecimal() else None
        if e is None:return redirect(url_for('admin_personal.panel',error='El empleado no pertenece a la organización.'))
        return redirect(url_for('admin_personal.ficha',empleado_id=e.id,seccion='sueldos'))

    @bp.route('/admin/personal/<int:empleado_id>', methods=['GET','POST'])
    @dependencias['login_required']
    def ficha(empleado_id):
        usuario,o,respuesta=acceso()
        if respuesta is not None:return respuesta
        e=empleado_de_org(o,empleado_id,request.method=='POST')
        if e is None:
            from flask import abort
            abort(404)
        seccion=request.values.get('seccion','datos')
        if seccion not in {'datos','sueldos','horarios','vacaciones','novedades'}:seccion='datos'
        error='';status=200
        listo=preparado(db.engine)
        if request.method=='POST':
            try:
                accion=request.form.get('accion')
                if accion=='guardar_sueldo':
                    guardar_salario(e,request.form,modelos=m,db_session=db.session,usuario_id=getattr(usuario,'id',None))
                elif accion in {'configurar_distribucion_laboral','configurar_porcentaje_costo_laboral'}:
                    from services.fuentes_costo_admin import procesar_accion_fuente_costo
                    unidad=e.unidad_negocio or m['UnidadNegocio'].query.filter_by(organizacion_id=o.id,activa=True).order_by(m['UnidadNegocio'].id).first()
                    if unidad is None:raise ValueError('Configurá una unidad activa para el costo laboral.')
                    formulario=request.form.copy();formulario['empleado_id']=str(e.id)
                    if accion=='configurar_porcentaje_costo_laboral':
                        from services.configuracion_costo_laboral import registrar_configuracion,recalcular_empleados_generales
                        config=registrar_configuracion(organizacion_id=o.id,unidad_negocio_id=unidad.id,
                            porcentaje=formulario.get('porcentaje_cargas_general'),observacion=formulario.get('observacion'),
                            usuario_id=getattr(usuario,'id',None),Modelo=m['ConfiguracionCostoLaboralVersion'],db_session=db.session,commit=False)
                        empleados=m['EmpleadoProductivo'].query.filter_by(organizacion_id=o.id,unidad_negocio_id=unidad.id,tipo_registro='empleado').with_for_update().all()
                        recalcular_empleados_generales(empleados,config.porcentaje_cargas,EmpleadoCostoVersion=m['EmpleadoCostoVersion'],
                            db_session=db.session,usuario_id=getattr(usuario,'id',None),commit=False)
                    else:procesar_accion_fuente_costo(accion,formulario,organizacion=o,unidad_activa=unidad,modelos=m,db_session=db.session,usuario=usuario)
                elif accion in {'crear_horario','crear_ausencia','cancelar_horario','cancelar_ausencia'}:
                    if not listo:raise ValueError('Prepará el módulo Personal antes de cargar horarios y ausencias.')
                    if accion=='crear_horario':guardar_horario(e,request.form,db.session)
                    elif accion=='crear_ausencia':guardar_ausencia(e,request.form,db.session,usuario_id=getattr(usuario,'id',None))
                    else:
                        Modelo=HorarioPersonal if accion=='cancelar_horario' else AusenciaPersonal
                        ident=str(request.form.get('registro_id') or '')
                        obj=Modelo.query.filter_by(id=int(ident),empleado_id=e.id).with_for_update().first() if ident.isdecimal() else None
                        if obj is None:raise ValueError('El registro no pertenece al empleado.')
                        obj.estado='cancelado' if accion=='cancelar_horario' else 'cancelada'
                elif accion in {'crear_turno','crear_novedad'}:
                    from services.personas_preparatorias import crear_turno,crear_novedad
                    unidad=e.unidad_negocio_id
                    if unidad is None:raise ValueError('Para un empleado compartido, usá Turnos y novedades de la unidad correspondiente.')
                    if accion=='crear_turno':crear_turno(request.form,empleado=e,organizacion_id=o.id,unidad_negocio_id=unidad,Turno=m['TurnoLaboralPlanificado'],db_session=db.session,usuario_id=getattr(usuario,'id',None))
                    else:crear_novedad(request.form,empleado=e,organizacion_id=o.id,unidad_negocio_id=unidad,Novedad=m['NovedadLaboralPreparatoria'],db_session=db.session,usuario_id=getattr(usuario,'id',None))
                else:raise ValueError('Acción de Personal no válida.')
                db.session.commit()
                dependencias['registrar_auditoria']('Actualizó legajo de Personal',entidad='empleado',entidad_id=e.id,detalle=f'Acción: {accion}.')
                return redirect(url_for('admin_personal.ficha',empleado_id=e.id,seccion=seccion,ok='Información guardada correctamente.'))
            except (ValueError,IntegrityError) as exc:
                db.session.rollback();error=str(exc) if isinstance(exc,ValueError) else 'El registro ya existe o cambió. Recargá el legajo y revisá los datos.';status=400
        detalle=db.session.get(PersonalDetalle,e.id) if listo else None
        unidades=m['UnidadNegocio'].query.filter_by(organizacion_id=o.id).order_by(m['UnidadNegocio'].nombre).all()
        extras={'ausencias_anteriores':[]}
        if seccion=='vacaciones':
            existentes=m['NovedadLaboralPreparatoria'].query.filter_by(organizacion_id=o.id,empleado_id=e.id).filter(m['NovedadLaboralPreparatoria'].tipo.in_(['licencia','ausencia'])).order_by(m['NovedadLaboralPreparatoria'].fecha_desde.desc()).all()
            vinculadas={a.novedad_id for a in AusenciaPersonal.query.filter_by(empleado_id=e.id).all()} if listo else set()
            extras['ausencias_anteriores']=[n for n in existentes if n.id not in vinculadas]
        if seccion=='novedades':
            from sqlalchemy import inspect
            for nombre,clave,orden in [('TurnoLaboralPlanificado','turnos','inicio'),('NovedadLaboralPreparatoria','novedades','fecha_desde'),('CompetenciaEmpleadoPreparatoria','competencias','codigo')]:
                Modelo=m[nombre]
                extras[clave]=Modelo.query.filter_by(organizacion_id=o.id,empleado_id=e.id).order_by(getattr(Modelo,orden).desc()).all() if inspect(db.engine).has_table(Modelo.__tablename__) else []
        from services.distribucion_laboral import distribuciones_vigentes
        from services.configuracion_costo_laboral import configuracion_vigente
        unidad=e.unidad_negocio or next((u for u in unidades if u.activa),None)
        distribuciones=distribuciones_vigentes([e],Modelo=m['EmpleadoDistribucionVersion']) if seccion=='sueldos' else {}
        config=configuracion_vigente(o.id,unidad.id,Modelo=m['ConfiguracionCostoLaboralVersion']) if unidad and seccion=='sueldos' else None
        laboral=resumenes([e],listo)[e.id]
        acceso_actual=estado_accesos(e,db.session)
        fila=dict(datos_empleado(e),**datos_detalle(detalle),**laboral,**acceso_actual,huella=huella_empleado(e,detalle=detalle,preparado=listo))
        return render_template('admin_personal_ficha.html',empleado=e,organizacion=o,unidades=unidades,
            seccion=seccion,detalle=datos_detalle(detalle),vigente=version_actual(e) if seccion=='sueldos' else None,
            empleados=[e],unidad_activa=unidad,distribuciones_laborales=distribuciones,configuracion_costo_laboral=config,
            money=lambda centavos: format(Decimal(centavos)/100,'.2f'),
            horarios=HorarioPersonal.query.filter_by(empleado_id=e.id).order_by(HorarioPersonal.dia_semana,HorarioPersonal.entrada).all() if listo and seccion=='horarios' else [],
            ausencias=AusenciaPersonal.query.join(m['NovedadLaboralPreparatoria']).filter(AusenciaPersonal.empleado_id==e.id,m['NovedadLaboralPreparatoria'].organizacion_id==o.id).order_by(m['NovedadLaboralPreparatoria'].fecha_desde.desc()).all() if listo and seccion=='vacaciones' else [],
            filas_personal=[fila],usuarios_personal=usuarios_disponibles(o),laboral=laboral,acceso_actual=acceso_actual,unidad_inicial=e.unidad_negocio_id,buscar='',pagina=1,
            formulario_error=None,formulario_accion=request.form if error else {},error=error,
            preparado=listo,dias_semana=DIAS,ok_feedback=request.args.get('ok',''),**extras),status

    @bp.route('/admin/personal/<int:empleado_id>/alarma',methods=['POST'])
    @dependencias['login_required']
    def mostrar_alarma(empleado_id):
        _,o,respuesta=acceso()
        if respuesta is not None:return jsonify(error='Acceso no autorizado.'),403
        e=empleado_de_org(o,empleado_id)
        if e is None:abort(404)
        if not preparado(db.engine):return jsonify(error='Prepará Personal antes de consultar el código.'),400
        try:
            respuesta=jsonify(codigo=leer_codigo_alarma(e,db.session))
        except ValueError as error:
            respuesta=jsonify(error=str(error));respuesta.status_code=400
        respuesta.headers['Cache-Control']='no-store, private'
        return respuesta

    return bp
