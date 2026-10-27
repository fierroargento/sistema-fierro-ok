"""Clientes compartidos explícitamente; el seguimiento permanece en su unidad."""
from sqlalchemy import or_
from models.cliente_unidad import ClienteUnidad
from scripts.preparar_clientes_unidad import preparado


def exigir_preparado(session):
    if not preparado(session.connection()):raise ValueError('Falta preparar Clientes por unidad en staging. No se guardaron cambios.')


def consulta(Cliente,org,unidad,session):
    q=session.query(Cliente).filter(Cliente.organizacion_id==org)
    if not preparado(session.connection()):return q.filter(Cliente.id==-1)
    ids=session.query(ClienteUnidad.cliente_id).filter_by(organizacion_id=org,unidad_negocio_id=unidad)
    return q.filter(Cliente.id.in_(ids))


def vincular(cliente,org,unidad,session):
    exigir_preparado(session)
    from models.unidad_negocio import UnidadNegocio
    u=session.query(UnidadNegocio).filter_by(id=unidad,organizacion_id=org,activa=True).with_for_update().first()
    if u is None or cliente.organizacion_id!=org:raise ValueError('El cliente no pertenece a la empresa o la unidad no está activa.')
    session.flush()
    v=session.query(ClienteUnidad).filter_by(cliente_id=cliente.id,unidad_negocio_id=unidad).first()
    if v is None:
        v=ClienteUnidad(organizacion_id=org,cliente_id=cliente.id,unidad_negocio_id=unidad,activo=False);session.add(v)
    session.flush();return v


def validar_accion(form,*,org,unidad,modelos,session):
    exigir_preparado(session)
    for campo,clave in [('cliente_id','ClienteCRM'),('identidad_id','ClienteIdentidadCanal'),('oportunidad_id','OportunidadCRM'),('oportunidad_crm_id','OportunidadCRM'),('actividad_id','ActividadCRM')]:
        ident=form.get(campo)
        if not ident:continue
        if not str(ident).isdecimal():raise ValueError('Referencia de CRM inválida.')
        M=modelos[clave];q=M.query.filter_by(id=int(ident),organizacion_id=org)
        if clave=='ClienteCRM':q=consulta(M,org,unidad,session).filter(M.id==int(ident))
        else:q=q.filter_by(unidad_negocio_id=unidad)
        if q.first() is None:raise ValueError('El registro de CRM no pertenece a la unidad activa.')
    solicitada=form.get('unidad_negocio_id')
    if solicitada and str(solicitada)!=str(unidad):raise ValueError('La unidad del formulario no coincide con la activa.')


def existente(codigo,Cliente,org,unidad,session):
    exigir_preparado(session)
    valor=str(codigo or '').strip().lower()
    if not valor:raise ValueError('Ingresá el código exacto del cliente.')
    c=session.query(Cliente).filter_by(organizacion_id=org,codigo=valor).first()
    if c is None:raise ValueError('No se encontró ese cliente en la empresa.')
    vincular(c,org,unidad,session);return c


def procesar(accion,formulario,*,organizacion,unidad_negocio_id,modelos,db_session,usuario):
    from services.crm_admin import procesar_accion_crm_admin
    from models.cliente_unidad import ClienteUnidad
    unidad_id=unidad_negocio_id
    exigir_preparado(db_session)
    if accion=='vincular_cliente':
        cliente=existente(formulario.get('codigo_existente'),modelos['ClienteCRM'],organizacion.id,unidad_id,db_session)
        mensaje='Cliente vinculado a la unidad activa sin copiar operaciones.'
    else:
        validar_accion(formulario,org=organizacion.id,unidad=unidad_id,modelos=modelos,session=db_session)
        if accion=='toggle_cliente':
            v=ClienteUnidad.query.filter_by(organizacion_id=organizacion.id,unidad_negocio_id=unidad_id,cliente_id=int(formulario['cliente_id'])).with_for_update().one()
            v.activo=not v.activo
            mensaje='Estado del cliente actualizado sólo en esta unidad.'
        else:
            form=formulario.copy()
            if accion in {'crear_cliente','crear_oportunidad'}:form['unidad_negocio_id']=str(unidad_id)
            mensaje=procesar_accion_crm_admin(accion,form,organizacion=organizacion,modelos=modelos,
                db_session=db_session,usuario=getattr(usuario,'username',None) or 'admin',commit=False,unidad_activa_id=unidad_id)
            if accion=='crear_cliente':
                cliente=modelos['ClienteCRM'].query.filter_by(organizacion_id=organizacion.id,codigo=form.get('codigo','').strip().lower()).one()
                vincular(cliente,organizacion.id,unidad_id,db_session)
    db_session.commit()
    return mensaje


def obtener_lote(ident,org,unidad,modelos,session):
    return modelos['LoteImportacionCRM'].query.filter_by(id=ident,organizacion_id=org,unidad_negocio_id=unidad).first()
