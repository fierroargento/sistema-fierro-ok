from flask import Blueprint,redirect,render_template,request,send_file,session,url_for
from services.tenant_context import TenantError,resolver_tenant_usuario
from services.contabilidad_nucleo import crear_cuenta,crear_borrador
from services.contabilidad_consultas import obtener_panel
from services.importacion_borradores_contables import importar_borradores
from services.gestion_borradores_contables import anular_borrador,generar_reportes,exportar_reportes

def crear_blueprint_contabilidad(*,dependencias):
    bp=Blueprint("admin_contabilidad",__name__);db=dependencias["db"];modelos=dependencias["modelos"]
    def acceso():
        usuario=dependencias["usuario_actual"]()
        try:membresia=resolver_tenant_usuario(usuario,UsuarioOrganizacion=dependencias["UsuarioOrganizacion"],organizacion_id=session.get("organizacion_id"))
        except TenantError as error:return None,None,None,redirect(url_for("inicio",error=str(error)))
        if membresia.rol!="admin":return None,None,None,redirect(url_for("inicio"))
        unidad=modelos["UnidadNegocio"].query.filter_by(id=session.get("unidad_negocio_id"),organizacion_id=membresia.organizacion_id,activa=True).first()
        if unidad is None:unidad=modelos["UnidadNegocio"].query.filter_by(organizacion_id=membresia.organizacion_id,activa=True).order_by(modelos["UnidadNegocio"].id.asc()).first()
        if unidad is None:return usuario,membresia.organizacion,None,redirect(url_for("admin_estructura.panel"))
        session["organizacion_id"]=membresia.organizacion_id;session["unidad_negocio_id"]=unidad.id
        return usuario,membresia.organizacion,unidad,None
    @bp.route("/admin/contabilidad")
    @dependencias["login_required"]
    def panel():
        _u,o,u,r=acceso()
        if r is not None:return r
        return render_template("admin_contabilidad.html",organizacion=o,unidad_activa=u,ok_feedback=request.args.get("ok"),error=request.args.get("error"),**obtener_panel(o.id,u.id,modelos=modelos))
    @bp.route("/admin/contabilidad/guardar",methods=["POST"])
    @dependencias["login_required"]
    def guardar():
        usuario,o,u,r=acceso()
        if r is not None:return r
        try:
            if request.form.get("accion")=="crear_cuenta":
                objeto=crear_cuenta(request.form,organizacion_id=o.id,unidad_negocio_id=u.id,Cuenta=modelos["CuentaContable"],db_session=db.session,usuario_id=getattr(usuario,"id",None));mensaje=f"Cuenta {objeto.codigo} creada inactiva."
            elif request.form.get("accion")=="crear_borrador":
                debe=modelos["CuentaContable"].query.filter_by(id=int(request.form.get("cuenta_debe_id")),organizacion_id=o.id,unidad_negocio_id=u.id).first()
                haber=modelos["CuentaContable"].query.filter_by(id=int(request.form.get("cuenta_haber_id")),organizacion_id=o.id,unidad_negocio_id=u.id).first()
                if debe is None or haber is None:raise ValueError("Las cuentas no pertenecen al contexto activo.")
                objeto=crear_borrador(request.form,cuenta_debe=debe,cuenta_haber=haber,organizacion_id=o.id,unidad_negocio_id=u.id,Asiento=modelos["AsientoContableBorrador"],db_session=db.session,usuario_id=getattr(usuario,"id",None));mensaje=f"Asiento {objeto.id} guardado solo como borrador."
            elif request.form.get("accion")=="anular_borrador":
                objeto=modelos["AsientoContableBorrador"].query.filter_by(id=int(request.form.get("asiento_id")),organizacion_id=o.id,unidad_negocio_id=u.id).first()
                if objeto is None:raise ValueError("El asiento no pertenece al contexto activo.")
                anular_borrador(objeto,organizacion_id=o.id,unidad_negocio_id=u.id,motivo=request.form.get("motivo"),db_session=db.session);mensaje=f"Asiento {objeto.id} anulado sin borrar historial."
            else:raise ValueError("Accion contable invalida.")
            dependencias["registrar_auditoria"]("Contabilidad preparatoria",entidad="contabilidad",detalle=mensaje)
            return redirect(url_for("admin_contabilidad.panel",ok=mensaje))
        except Exception as error:db.session.rollback();return redirect(url_for("admin_contabilidad.panel",error=str(error)))
    @bp.route("/admin/contabilidad/reportes-borrador")
    @dependencias["login_required"]
    def reportes_borrador():
        _usuario,o,u,r=acceso()
        if r is not None:return r
        cuentas=modelos["CuentaContable"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).all()
        asientos=modelos["AsientoContableBorrador"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).all()
        lineas=modelos["LineaAsientoContableBorrador"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).all()
        resultado=generar_reportes(organizacion_id=o.id,unidad_negocio_id=u.id,cuentas=cuentas,asientos=asientos,lineas=lineas,
            desde=request.args.get("desde"),hasta=request.args.get("hasta"))
        return send_file(exportar_reportes(resultado),as_attachment=True,download_name="reportes_contables_borrador.json",mimetype="application/json")
    @bp.route("/admin/contabilidad/importar-borradores",methods=["POST"])
    @dependencias["login_required"]
    def importar():
        usuario,o,u,r=acceso()
        if r is not None:return r
        archivo=request.files.get("borradores")
        if archivo is None:return redirect(url_for("admin_contabilidad.panel",error="Debe seleccionar un CSV o JSON."))
        try:
            cuentas=modelos["CuentaContable"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).all()
            creados=importar_borradores(organizacion_id=o.id,unidad_negocio_id=u.id,contenido=archivo.read(),nombre_archivo=archivo.filename,
                cuentas=cuentas,Asiento=modelos["AsientoContableBorrador"],Linea=modelos["LineaAsientoContableBorrador"],db_session=db.session,usuario_id=getattr(usuario,"id",None))
            mensaje=f"{len(creados)} asientos importados exclusivamente como borradores."
            dependencias["registrar_auditoria"]("Importacion contable preparatoria",entidad="contabilidad",detalle=mensaje)
            return redirect(url_for("admin_contabilidad.panel",ok=mensaje))
        except Exception as error:db.session.rollback();return redirect(url_for("admin_contabilidad.panel",error=str(error)))
    return bp
