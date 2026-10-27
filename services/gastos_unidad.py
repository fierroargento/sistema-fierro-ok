"""Gasto único: visibilidad por reparto, obligaciones sólo de la unidad responsable."""
from sqlalchemy import or_


def consulta(Costo,Distribucion,org,unidad):
    ids=Distribucion.query.filter_by(organizacion_id=org,unidad_negocio_id=unidad,vigente=True).with_entities(Distribucion.costo_fijo_id)
    return Costo.query.filter(Costo.organizacion_id==org,or_(Costo.unidad_negocio_id==unidad,Costo.id.in_(ids)))


def validar_accion(accion,form,org,unidad,modelos):
    # El reparto para costeo no autoriza a pagar otra vez la misma obligación.
    referencias=[('obligacion_id','ObligacionCostoProductivo'),('pago_id','PagoObligacionCostoProductivo')]
    for campo,clave in referencias:
        ident=form.get(campo)
        if not ident or clave not in modelos:continue
        M=modelos[clave]
        if not hasattr(M,'__table__'):continue
        objeto=M.query.filter_by(id=int(ident)).first()
        obligacion=getattr(objeto,'obligacion',None) if campo=='pago_id' else objeto
        costo=getattr(obligacion,'costo_fijo',None)
        if costo is None or costo.organizacion_id!=org or costo.unidad_negocio_id!=unidad:
            raise ValueError('La obligación o el pago no corresponde a la unidad responsable activa.')
    if form.get('propuesta_id') and 'PropuestaAjusteIPCProductivo' in modelos and hasattr(modelos['PropuestaAjusteIPCProductivo'],'__table__'):
        propuesta=modelos['PropuestaAjusteIPCProductivo'].query.filter_by(id=int(form['propuesta_id'])).first()
        c=propuesta.regla.costo_fijo if propuesta else None
        if c is None or c.organizacion_id!=org or c.unidad_negocio_id!=unidad:raise ValueError('El ajuste no pertenece a la unidad responsable activa.')
    ident=form.get('costo_fijo_id')
    if ident and 'CostoFijoProductivo' in modelos and hasattr(modelos['CostoFijoProductivo'],'__table__'):
        c=modelos['CostoFijoProductivo'].query.filter_by(id=int(ident),organizacion_id=org).first()
        if c is None:raise ValueError('El gasto no pertenece a la empresa.')
        de_unidad=c.unidad_negocio_id==unidad or any(d.vigente and d.unidad_negocio_id==unidad for d in c.distribuciones_versionadas)
        if not de_unidad:raise ValueError('El gasto no está relacionado con la unidad activa.')
        if accion in {'crear_obligacion_costo','configurar_obligaciones_recurrentes','configurar_ajuste_ipc','actualizar_importe_costo_fijo'} and c.unidad_negocio_id!=unidad:
            raise ValueError('La obligación se registra desde la unidad responsable del gasto.')


def asignar_responsable(codigo,org,unidad,modelos,session):
    C=modelos['CostoFijoProductivo']
    costo=C.query.filter_by(organizacion_id=org,codigo=str(codigo or '').strip().lower()).with_for_update().first()
    if costo is None:raise ValueError('No se encontró ese código de gasto en la empresa.')
    if costo.unidad_negocio_id not in (None,unidad):raise ValueError('El gasto ya tiene otra unidad responsable; conservá su reparto existente.')
    costo.unidad_negocio_id=unidad
    session.flush();return costo
