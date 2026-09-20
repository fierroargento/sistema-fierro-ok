from flask import Blueprint,redirect,render_template,request,send_file,session,url_for
from services.tenant_context import TenantError,resolver_tenant_usuario
from services.mantenimiento_nucleo import crear_plan,crear_orden,cancelar_orden,controlar_mantenimiento,exportar_control

def crear_blueprint_mantenimiento(*,dependencias):
    bp=Blueprint("admin_mantenimiento",__name__);db=dependencias["db"];m=dependencias["modelos"]
    def acceso():
        usuario=dependencias["usuario_actual"]()
        try:mem=resolver_tenant_usuario(usuario,UsuarioOrganizacion=dependencias["UsuarioOrganizacion"],organizacion_id=session.get("organizacion_id"))
        except TenantError as error:return None,None,None,redirect(url_for("inicio",error=str(error)))
        if mem.rol!="admin":return None,None,None,redirect(url_for("inicio"))
        unidad=m["UnidadNegocio"].query.filter_by(id=session.get("unidad_negocio_id"),organizacion_id=mem.organizacion_id,activa=True).first()
        if unidad is None:unidad=m["UnidadNegocio"].query.filter_by(organizacion_id=mem.organizacion_id,activa=True).order_by(m["UnidadNegocio"].id.asc()).first()
        if unidad is None:return usuario,mem.organizacion,None,redirect(url_for("admin_estructura.panel"))
        session["organizacion_id"]=mem.organizacion_id;session["unidad_negocio_id"]=unidad.id;return usuario,mem.organizacion,unidad,None
    def datos(o,u):
        maquinas=m["MaquinaProductiva"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).order_by(m["MaquinaProductiva"].codigo.asc()).all()
        planes=m["PlanMantenimiento"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).order_by(m["PlanMantenimiento"].proxima_fecha.asc()).all()
        ordenes=m["OrdenMantenimientoPreparatoria"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).order_by(m["OrdenMantenimientoPreparatoria"].fecha_prevista.asc()).all()
        return maquinas,planes,ordenes
    @bp.route("/admin/mantenimiento")
    @dependencias["login_required"]
    def panel():
        _x,o,u,r=acceso()
        if r is not None:return r
        maquinas,planes,ordenes=datos(o,u);control=controlar_mantenimiento(organizacion_id=o.id,unidad_negocio_id=u.id,planes=planes,ordenes=ordenes)
        return render_template("admin_mantenimiento.html",organizacion=o,unidad_activa=u,maquinas=maquinas,planes=planes,ordenes=ordenes,control=control,ok_feedback=request.args.get("ok"),error=request.args.get("error"))
    @bp.route("/admin/mantenimiento/guardar",methods=["POST"])
    @dependencias["login_required"]
    def guardar():
        usuario,o,u,r=acceso()
        if r is not None:return r
        try:
            accion=request.form.get("accion")
            if accion=="crear_plan":
                maquina=m["MaquinaProductiva"].query.filter_by(id=int(request.form.get("maquina_id")),organizacion_id=o.id,unidad_negocio_id=u.id).first()
                obj=crear_plan(request.form,maquina=maquina,organizacion_id=o.id,unidad_negocio_id=u.id,Plan=m["PlanMantenimiento"],db_session=db.session,usuario_id=getattr(usuario,"id",None));mensaje=f"Plan {obj.codigo} creado inactivo."
            elif accion=="crear_orden":
                maquina=m["MaquinaProductiva"].query.filter_by(id=int(request.form.get("maquina_id")),organizacion_id=o.id,unidad_negocio_id=u.id).first();plan_id=request.form.get("plan_id")
                plan=m["PlanMantenimiento"].query.filter_by(id=int(plan_id),organizacion_id=o.id,unidad_negocio_id=u.id).first() if plan_id else None
                obj=crear_orden(request.form,maquina=maquina,plan=plan,organizacion_id=o.id,unidad_negocio_id=u.id,Orden=m["OrdenMantenimientoPreparatoria"],db_session=db.session,usuario_id=getattr(usuario,"id",None));mensaje=f"Orden {obj.id} planificada sin ejecucion."
            elif accion=="cancelar_orden":
                obj=m["OrdenMantenimientoPreparatoria"].query.filter_by(id=int(request.form.get("orden_id")),organizacion_id=o.id,unidad_negocio_id=u.id).first()
                if obj is None:raise ValueError("La orden no pertenece al contexto activo.")
                cancelar_orden(obj,organizacion_id=o.id,unidad_negocio_id=u.id,motivo=request.form.get("motivo"),db_session=db.session);mensaje=f"Orden {obj.id} cancelada sin borrar historial."
            else:raise ValueError("Accion de mantenimiento invalida.")
            dependencias["registrar_auditoria"]("Mantenimiento preparatorio",entidad="mantenimiento",detalle=mensaje);return redirect(url_for("admin_mantenimiento.panel",ok=mensaje))
        except Exception as error:db.session.rollback();return redirect(url_for("admin_mantenimiento.panel",error=str(error)))
    @bp.route("/admin/mantenimiento/control")
    @dependencias["login_required"]
    def control():
        _x,o,u,r=acceso()
        if r is not None:return r
        _maquinas,planes,ordenes=datos(o,u);resultado=controlar_mantenimiento(organizacion_id=o.id,unidad_negocio_id=u.id,planes=planes,ordenes=ordenes)
        return send_file(exportar_control(resultado),as_attachment=True,download_name="control_mantenimiento_preparatorio.json",mimetype="application/json")
    return bp
