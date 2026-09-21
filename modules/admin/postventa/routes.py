from flask import Blueprint,redirect,render_template,request,send_file,session,url_for
from services.tenant_context import TenantError,resolver_tenant_usuario
from services.postventa_preparatoria import crear_caso,proponer_resolucion,cambiar_estado,expediente_postventa,exportar
def crear_blueprint_postventa(*,dependencias):
 bp=Blueprint("admin_postventa",__name__);db=dependencias["db"];m=dependencias["modelos"]
 def acceso():
  usuario=dependencias["usuario_actual"]()
  try:mem=resolver_tenant_usuario(usuario,UsuarioOrganizacion=dependencias["UsuarioOrganizacion"],organizacion_id=session.get("organizacion_id"))
  except TenantError as e:return None,None,None,redirect(url_for("inicio",error=str(e)))
  if mem.rol!="admin":return None,None,None,redirect(url_for("inicio"))
  u=m["UnidadNegocio"].query.filter_by(id=session.get("unidad_negocio_id"),organizacion_id=mem.organizacion_id,activa=True).first() or m["UnidadNegocio"].query.filter_by(organizacion_id=mem.organizacion_id,activa=True).order_by(m["UnidadNegocio"].id.asc()).first()
  if u is None:return usuario,mem.organizacion,None,redirect(url_for("admin_estructura.panel"))
  session["organizacion_id"]=mem.organizacion_id;session["unidad_negocio_id"]=u.id;return usuario,mem.organizacion,u,None
 def datos(o,u):
  pedidos=m["Pedido"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).order_by(m["Pedido"].id.desc()).limit(200).all();casos=m["CasoPostventa"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).order_by(m["CasoPostventa"].id.desc()).all();propuestas=m["PropuestaResolucionPostventa"].query.filter_by(organizacion_id=o.id,unidad_negocio_id=u.id).order_by(m["PropuestaResolucionPostventa"].id.desc()).all();return pedidos,casos,propuestas
 @bp.route("/admin/postventa")
 @dependencias["login_required"]
 def panel():
  _x,o,u,r=acceso()
  if r is not None:return r
  p,c,pr=datos(o,u);control=expediente_postventa(organizacion_id=o.id,unidad_negocio_id=u.id,casos=c,propuestas=pr);return render_template("admin_postventa.html",organizacion=o,unidad_activa=u,pedidos=p,casos=c,propuestas=pr,control=control,ok_feedback=request.args.get("ok"),error=request.args.get("error"))
 @bp.route("/admin/postventa/guardar",methods=["POST"])
 @dependencias["login_required"]
 def guardar():
  usuario,o,u,r=acceso()
  if r is not None:return r
  try:
   accion=request.form.get("accion")
   if accion=="crear_caso":
    pedido=m["Pedido"].query.filter_by(id=int(request.form.get("pedido_id")),organizacion_id=o.id,unidad_negocio_id=u.id).first();obj=crear_caso(request.form,pedido=pedido,organizacion_id=o.id,unidad_negocio_id=u.id,Caso=m["CasoPostventa"],db_session=db.session,usuario_id=getattr(usuario,"id",None));mensaje=f"Caso {obj.id} abierto sin efectos externos."
   elif accion=="proponer":
    caso=m["CasoPostventa"].query.filter_by(id=int(request.form.get("caso_id")),organizacion_id=o.id,unidad_negocio_id=u.id).first();obj=proponer_resolucion(request.form,caso=caso,organizacion_id=o.id,unidad_negocio_id=u.id,Propuesta=m["PropuestaResolucionPostventa"],db_session=db.session);mensaje=f"Resolucion {obj.id} propuesta sin ejecutar."
   elif accion=="estado":
    caso=m["CasoPostventa"].query.filter_by(id=int(request.form.get("caso_id")),organizacion_id=o.id,unidad_negocio_id=u.id).first();obj=cambiar_estado(caso,organizacion_id=o.id,unidad_negocio_id=u.id,estado=request.form.get("estado"),db_session=db.session);mensaje=f"Caso {obj.id} actualizado a {obj.estado}."
   else:raise ValueError("Accion de postventa invalida.")
   dependencias["registrar_auditoria"]("Postventa preparatoria",entidad="postventa",detalle=mensaje);return redirect(url_for("admin_postventa.panel",ok=mensaje))
  except Exception as e:db.session.rollback();return redirect(url_for("admin_postventa.panel",error=str(e)))
 @bp.route("/admin/postventa/expediente")
 @dependencias["login_required"]
 def expediente():
  _x,o,u,r=acceso()
  if r is not None:return r
  _p,c,pr=datos(o,u);resultado=expediente_postventa(organizacion_id=o.id,unidad_negocio_id=u.id,casos=c,propuestas=pr);return send_file(exportar(resultado),as_attachment=True,download_name="expediente_postventa.json",mimetype="application/json")
 return bp
