from flask import Blueprint,redirect,render_template,request,send_file,session,url_for
from services.tenant_context import TenantError,resolver_tenant_usuario
from services.personas_preparatorias import crear_turno,crear_novedad,cancelar,controlar_personas,exportar_control
from services.cierre_personas_preparatorio import registrar_competencia,expediente_personas,exportar_expediente
def crear_blueprint_personas(*,dependencias):
 bp=Blueprint("admin_personas",__name__);db=dependencias["db"];m=dependencias["modelos"]
 def acceso():
  usuario=dependencias["usuario_actual"]()
  try:mem=resolver_tenant_usuario(usuario,UsuarioOrganizacion=dependencias["UsuarioOrganizacion"],organizacion_id=session.get("organizacion_id"))
  except TenantError as e:return None,None,None,redirect(url_for("inicio",error=str(e)))
  if mem.rol!="admin":return None,None,None,redirect(url_for("inicio"))
  unidad=m["UnidadNegocio"].query.filter_by(id=session.get("unidad_negocio_id"),organizacion_id=mem.organizacion_id,activa=True).first() or m["UnidadNegocio"].query.filter_by(organizacion_id=mem.organizacion_id,activa=True).order_by(m["UnidadNegocio"].id.asc()).first()
  if unidad is None:return usuario,mem.organizacion,None,redirect(url_for("admin_estructura.panel"))
  session["organizacion_id"]=mem.organizacion_id;session["unidad_negocio_id"]=unidad.id;return usuario,mem.organizacion,unidad,None
 def datos(o,u):
  empleados=m["EmpleadoProductivo"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id,tipo_registro="empleado").order_by(m["EmpleadoProductivo"].nombre.asc()).all();turnos=m["TurnoLaboralPlanificado"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).order_by(m["TurnoLaboralPlanificado"].inicio.asc()).all();novedades=m["NovedadLaboralPreparatoria"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).order_by(m["NovedadLaboralPreparatoria"].fecha_desde.asc()).all();competencias=m["CompetenciaEmpleadoPreparatoria"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).order_by(m["CompetenciaEmpleadoPreparatoria"].vence_el.asc()).all();return empleados,turnos,novedades,competencias
 @bp.route("/admin/personas")
 @dependencias["login_required"]
 def panel():
  _x,o,u,r=acceso()
  if r is not None:return r
  e,t,n,c=datos(o,u);control=controlar_personas(organizacion_id=o.id,unidad_negocio_id=u.id,empleados=e,turnos=t,novedades=n);expediente=expediente_personas(organizacion_id=o.id,unidad_negocio_id=u.id,empleados=e,turnos=t,novedades=n,competencias=c);return render_template("admin_personas.html",organizacion=o,unidad_activa=u,empleados=e,turnos=t,novedades=n,competencias=c,control=control,expediente=expediente,ok_feedback=request.args.get("ok"),error=request.args.get("error"))
 @bp.route("/admin/personas/guardar",methods=["POST"])
 @dependencias["login_required"]
 def guardar():
  usuario,o,u,r=acceso()
  if r is not None:return r
  try:
   accion=request.form.get("accion")
   if accion in {"crear_turno","crear_novedad"}:
    empleado=m["EmpleadoProductivo"].query.filter_by(id=int(request.form.get("empleado_id")),organizacion_id=o.id,unidad_negocio_id=u.id,tipo_registro="empleado").first()
    if accion=="crear_turno":obj=crear_turno(request.form,empleado=empleado,organizacion_id=o.id,unidad_negocio_id=u.id,Turno=m["TurnoLaboralPlanificado"],db_session=db.session,usuario_id=getattr(usuario,"id",None));mensaje=f"Turno {obj.id} planificado sin fichaje."
    else:obj=crear_novedad(request.form,empleado=empleado,organizacion_id=o.id,unidad_negocio_id=u.id,Novedad=m["NovedadLaboralPreparatoria"],db_session=db.session,usuario_id=getattr(usuario,"id",None));mensaje=f"Novedad {obj.id} propuesta sin aprobar."
   elif accion=="registrar_competencia":
    empleado=m["EmpleadoProductivo"].query.filter_by(id=int(request.form.get("empleado_id")),organizacion_id=o.id,unidad_negocio_id=u.id,tipo_registro="empleado").first();obj=registrar_competencia(request.form,empleado=empleado,organizacion_id=o.id,unidad_negocio_id=u.id,Competencia=m["CompetenciaEmpleadoPreparatoria"],db_session=db.session);mensaje=f"Competencia {obj.id} registrada sin habilitar asignaciones."
   elif accion in {"cancelar_turno","cancelar_novedad"}:
    Modelo=m["TurnoLaboralPlanificado"] if accion=="cancelar_turno" else m["NovedadLaboralPreparatoria"];obj=Modelo.query.filter_by(id=int(request.form.get("registro_id")),organizacion_id=o.id,unidad_negocio_id=u.id).first()
    if obj is None:raise ValueError("El registro no pertenece al contexto activo.")
    cancelar(obj,organizacion_id=o.id,unidad_negocio_id=u.id,motivo=request.form.get("motivo"),db_session=db.session);mensaje=f"Registro {obj.id} cancelado sin borrar historial."
   else:raise ValueError("Accion de personas invalida.")
   dependencias["registrar_auditoria"]("Personas preparatorio",entidad="personas",detalle=mensaje);return redirect(url_for("admin_personas.panel",ok=mensaje))
  except Exception as error:db.session.rollback();return redirect(url_for("admin_personas.panel",error=str(error)))
 @bp.route("/admin/personas/control")
 @dependencias["login_required"]
 def control():
  _x,o,u,r=acceso()
  if r is not None:return r
  e,t,n,_c=datos(o,u);resultado=controlar_personas(organizacion_id=o.id,unidad_negocio_id=u.id,empleados=e,turnos=t,novedades=n);return send_file(exportar_control(resultado),as_attachment=True,download_name="control_personas_preparatorio.json",mimetype="application/json")
 @bp.route("/admin/personas/expediente")
 @dependencias["login_required"]
 def expediente():
  _x,o,u,r=acceso()
  if r is not None:return r
  e,t,n,c=datos(o,u);resultado=expediente_personas(organizacion_id=o.id,unidad_negocio_id=u.id,empleados=e,turnos=t,novedades=n,competencias=c);return send_file(exportar_expediente(resultado),as_attachment=True,download_name="expediente_personas_preparatorio.json",mimetype="application/json")
 return bp
