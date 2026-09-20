from flask import Blueprint,redirect,render_template,request,send_file,session,url_for
from services.tenant_context import TenantError,resolver_tenant_usuario
from services.tesoreria_nucleo import crear_cuenta,crear_proyeccion
from services.tesoreria_consultas import obtener_panel,exportar_flujo,archivo_flujo
from services.origenes_proyectados_tesoreria import consolidar_origenes,exportar_origenes
from services.confirmacion_origen_tesoreria import confirmar_candidato
from services.gestion_proyecciones_tesoreria import cancelar_proyeccion
from services.control_liquidez_tesoreria import controlar_liquidez,exportar_liquidez

def crear_blueprint_tesoreria(*,dependencias):
    bp=Blueprint("admin_tesoreria",__name__);db=dependencias["db"];modelos=dependencias["modelos"]
    def acceso():
        usuario=dependencias["usuario_actual"]()
        try: membresia=resolver_tenant_usuario(usuario,UsuarioOrganizacion=dependencias["UsuarioOrganizacion"],organizacion_id=session.get("organizacion_id"))
        except TenantError as error:return None,None,None,redirect(url_for("inicio",error=str(error)))
        if membresia.rol!="admin":return None,None,None,redirect(url_for("inicio"))
        unidad=modelos["UnidadNegocio"].query.filter_by(id=session.get("unidad_negocio_id"),organizacion_id=membresia.organizacion_id,activa=True).first()
        if unidad is None:unidad=modelos["UnidadNegocio"].query.filter_by(organizacion_id=membresia.organizacion_id,activa=True).order_by(modelos["UnidadNegocio"].id.asc()).first()
        if unidad is None:return usuario,membresia.organizacion,None,redirect(url_for("admin_estructura.panel"))
        session["organizacion_id"]=membresia.organizacion_id;session["unidad_negocio_id"]=unidad.id
        return usuario,membresia.organizacion,unidad,None
    @bp.route("/admin/tesoreria")
    @dependencias["login_required"]
    def panel():
        _u,o,u,r=acceso()
        if r is not None:return r
        datos=obtener_panel(o.id,u.id,modelos=modelos)
        origenes=consolidar_origenes(organizacion_id=o.id,unidad_negocio_id=u.id,
            obligaciones=modelos["ObligacionCostoProductivo"].query.filter_by(organizacion_id=o.id).all(),
            facturas=modelos["FacturaProveedorCompra"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).all(),
            ventas=modelos["VentaCanalItem"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).all(),
            proyecciones_existentes=datos["movimientos_tesoreria"])
        return render_template("admin_tesoreria.html",organizacion=o,unidad_activa=u,
            ok_feedback=request.args.get("ok"),error=request.args.get("error"),
            candidatos_origen=[x for x in origenes["candidatos"] if not x["ya_proyectado"]],
            hallazgos_origen=origenes["hallazgos"],**datos)
    @bp.route("/admin/tesoreria/guardar",methods=["POST"])
    @dependencias["login_required"]
    def guardar():
        usuario,o,u,r=acceso()
        if r is not None:return r
        try:
            if request.form.get("accion")=="crear_cuenta":
                cuenta=crear_cuenta(request.form,organizacion_id=o.id,unidad_negocio_id=u.id,CuentaTesoreria=modelos["CuentaTesoreria"],db_session=db.session,usuario_id=getattr(usuario,"id",None));mensaje=f"Cuenta {cuenta.codigo} creada desconectada."
            elif request.form.get("accion")=="crear_proyeccion":
                cuenta=modelos["CuentaTesoreria"].query.filter_by(id=int(request.form.get("cuenta_id")),organizacion_id=o.id,unidad_negocio_id=u.id).first()
                if cuenta is None:raise ValueError("La cuenta no pertenece al contexto activo.")
                mov=crear_proyeccion(request.form,cuenta=cuenta,organizacion_id=o.id,unidad_negocio_id=u.id,Movimiento=modelos["MovimientoTesoreriaProyectado"],db_session=db.session,usuario_id=getattr(usuario,"id",None));mensaje=f"Proyección {mov.concepto} registrada sin afectar saldo."
            elif request.form.get("accion")=="confirmar_origen":
                cuenta=modelos["CuentaTesoreria"].query.filter_by(id=int(request.form.get("cuenta_id")),organizacion_id=o.id,unidad_negocio_id=u.id).first()
                if cuenta is None:raise ValueError("La cuenta no pertenece al contexto activo.")
                origen=str(request.form.get("origen") or "");origen_id=int(request.form.get("origen_id"))
                candidatos=consolidar_origenes(organizacion_id=o.id,unidad_negocio_id=u.id,
                    obligaciones=modelos["ObligacionCostoProductivo"].query.filter_by(organizacion_id=o.id).all(),
                    facturas=modelos["FacturaProveedorCompra"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).all(),
                    ventas=modelos["VentaCanalItem"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).all(),
                    proyecciones_existentes=modelos["MovimientoTesoreriaProyectado"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).all())["candidatos"]
                candidato=next((x for x in candidatos if x["origen"]==origen and int(x["origen_id"])==origen_id),None)
                if candidato is None:raise ValueError("El origen ya no está disponible o no pertenece al contexto activo.")
                mov=confirmar_candidato(candidato,cuenta=cuenta,organizacion_id=o.id,unidad_negocio_id=u.id,
                    Movimiento=modelos["MovimientoTesoreriaProyectado"],db_session=db.session,usuario_id=getattr(usuario,"id",None))
                mensaje=f"Origen {mov.referencia} confirmado solo como proyección."
            elif request.form.get("accion")=="cancelar_proyeccion":
                mov=modelos["MovimientoTesoreriaProyectado"].query.filter_by(id=int(request.form.get("movimiento_id")),organizacion_id=o.id,unidad_negocio_id=u.id).first()
                if mov is None:raise ValueError("La proyección no pertenece al contexto activo.")
                cancelar_proyeccion(mov,organizacion_id=o.id,unidad_negocio_id=u.id,motivo=request.form.get("motivo"),db_session=db.session)
                mensaje=f"Proyección {mov.id} cancelada sin borrar historial ni afectar saldo."
            else:raise ValueError("La acción de tesorería no es válida.")
            dependencias["registrar_auditoria"]("Tesorería preparatoria",entidad="tesoreria",detalle=mensaje)
            return redirect(url_for("admin_tesoreria.panel",ok=mensaje))
        except Exception as error:db.session.rollback();return redirect(url_for("admin_tesoreria.panel",error=str(error)))
    @bp.route("/admin/tesoreria/flujo")
    @dependencias["login_required"]
    def flujo():
        _u,o,u,r=acceso()
        if r is not None:return r
        panel=obtener_panel(o.id,u.id,modelos=modelos);resultado=exportar_flujo(organizacion_id=o.id,unidad_negocio_id=u.id,cuentas=panel["cuentas_tesoreria"],movimientos=panel["movimientos_tesoreria"])
        return send_file(archivo_flujo(resultado),as_attachment=True,download_name="flujo_tesoreria_proyectado.json",mimetype="application/json")
    @bp.route("/admin/tesoreria/origenes")
    @dependencias["login_required"]
    def origenes():
        _u,o,u,r=acceso()
        if r is not None:return r
        obligaciones=modelos["ObligacionCostoProductivo"].query.filter_by(organizacion_id=o.id).all()
        facturas=modelos["FacturaProveedorCompra"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).all()
        ventas=modelos["VentaCanalItem"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).all()
        existentes=modelos["MovimientoTesoreriaProyectado"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).all()
        resultado=consolidar_origenes(organizacion_id=o.id,unidad_negocio_id=u.id,obligaciones=obligaciones,
            facturas=facturas,ventas=ventas,proyecciones_existentes=existentes)
        return send_file(exportar_origenes(resultado),as_attachment=True,
                         download_name="origenes_proyectados_tesoreria.json",mimetype="application/json")
    @bp.route("/admin/tesoreria/liquidez")
    @dependencias["login_required"]
    def liquidez():
        _u,o,u,r=acceso()
        if r is not None:return r
        datos=obtener_panel(o.id,u.id,modelos=modelos)
        resultado=controlar_liquidez(organizacion_id=o.id,unidad_negocio_id=u.id,
            cuentas=datos["cuentas_tesoreria"],movimientos=datos["movimientos_tesoreria"])
        return send_file(exportar_liquidez(resultado),as_attachment=True,
                         download_name="control_liquidez_tesoreria.json",mimetype="application/json")
    return bp
