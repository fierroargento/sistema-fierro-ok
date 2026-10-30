"""Cotización general de empresa; sólo administración y carga manual."""
from datetime import date
from flask import Blueprint,request,session,redirect,url_for,render_template
from sqlalchemy.exc import IntegrityError
from services.tenant_context import resolver_tenant_usuario,TenantError

def crear_blueprint_cotizaciones(*,dependencias):
    bp=Blueprint('admin_cotizaciones',__name__)
    db=dependencias['db']
    @bp.route('/admin/cotizaciones',methods=['GET','POST'])
    @dependencias['login_required']
    def panel():
        from services import cotizaciones as s
        from scripts.preparar_cotizaciones import preparado
        usuario=dependencias['usuario_actual']()
        try:
            mem=resolver_tenant_usuario(usuario,UsuarioOrganizacion=dependencias['UsuarioOrganizacion'],organizacion_id=session.get('organizacion_id'))
        except TenantError as e:return redirect(url_for('inicio',error=str(e)))
        if mem.rol!='admin':return redirect(url_for('inicio'))
        from services.alcance_unidad import resolver,validar_formulario
        try:unidad=resolver(mem.organizacion_id,dependencias['UnidadNegocio']);validar_formulario(unidad.id)
        except ValueError as e:return redirect(url_for('inicio',error=str(e)))
        session['organizacion_id']=mem.organizacion_id
        listo=preparado(db.session.connection());error='';status=200
        if request.method=='POST':
            try:
                if request.form.get('unidad_contexto_id',type=int)!=unidad.id:raise ValueError('La unidad activa cambió. Volvé a abrir el formulario.')
                if request.form.get('accion')=='guardar_dolar':s.guardar_dolar(request.form,mem.organizacion_id,usuario.id,db.session)
                elif request.form.get('accion')=='guardar_laser':s.guardar_laser(request.form,mem.organizacion_id,unidad.id,usuario.id,db.session)
                else:raise ValueError('Acción inválida.')
                db.session.commit()
                dependencias['registrar_auditoria']('Cotizaciones: '+request.form['accion'],entidad='cotizacion',detalle='Empresa '+str(mem.organizacion_id)+'. Unidad '+str(unidad.id)+'. Sin movimientos ni publicaciones.')
                return redirect(url_for('admin_cotizaciones.panel',ok='Datos guardados. Los cálculos nuevos usan el dólar general; el historial de productos se conserva.'))
            except (ValueError,IntegrityError) as e:
                db.session.rollback();error=str(e) if isinstance(e,ValueError) else 'Los datos cambiaron mientras editabas. Volvé a abrir el formulario.';status=400
        dolar=s.actual(mem.organizacion_id,db.session) if listo else None
        config=s.configuracion(mem.organizacion_id,unidad.id,db.session) if listo else None
        tarifa=s.calcular(config,dolar) if config and dolar else None
        historia=db.session.query(s.D).filter_by(organizacion_id=mem.organizacion_id).order_by(s.D.numero_version.desc()).limit(20).all() if listo else []
        historias_laser=db.session.query(s.L).filter_by(organizacion_id=mem.organizacion_id,unidad_negocio_id=unidad.id).order_by(s.L.numero_version.desc()).limit(20).all() if listo else []
        valores=[dict(nombre=r['nombre'],usd=str(s.Decimal(r['usd_centavos'])/100),horas=r['horas']) for r in config.consumibles] if config else s.PREDETERMINADOS
        if error and request.form.get('accion')=='guardar_laser':
            valores=[dict(nombre=b['nombre'],usd=v,horas=h) for b,v,h in zip(s.PREDETERMINADOS,request.form.getlist('consumible_usd'),request.form.getlist('vida_horas'))]
        return render_template('admin_cotizaciones.html',organizacion=mem.organizacion,unidad_activa=unidad,listo=listo,dolar=dolar,config=config,tarifa=tarifa,historia=historia,historias_laser=historias_laser,valores=valores,hoy=s.hoy().isoformat(),error=error,ok=request.args.get('ok',''),abrir=request.form.get('accion') if error else '',formulario=request.form if error else {},dinero=lambda n:format(s.Decimal(n)/100,',.2f').replace(',','_').replace('.',',').replace('_','.')),status
    return bp
