"""Contexto explícito de unidad para las pantallas administrativas."""
from flask import request, session


def resolver(organizacion_id, Unidad):
    from services.unidad_negocio_contexto import resolver_unidad_activa
    ident=session.get('unidad_negocio_id')
    unidad,_=resolver_unidad_activa(organizacion_id,ident,UnidadNegocio=Unidad)
    if str(ident or '')!=str(unidad.id):
        raise ValueError('Seleccioná una unidad activa válida antes de continuar.')
    return unidad



def validar_formulario(unidad_id):
    if request.method not in {'POST','PUT','PATCH','DELETE'}:return
    valor=request.form.get('unidad_contexto_id') or request.headers.get('X-Fierro-Unidad')
    if str(valor or '')!=str(unidad_id):
        raise ValueError('La unidad activa cambió o falta el contexto. Volvé a abrir el formulario antes de guardar.')
