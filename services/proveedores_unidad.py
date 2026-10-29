"""Alcance de proveedores. Ausencia de esquema nunca habilita un listado general."""
import re
from sqlalchemy import or_
from models.proveedor_unidad import ProveedorUnidad
from scripts.preparar_proveedores_unidad import preparado


def exigir_preparado(session):
    if not preparado(session.connection()):
        raise ValueError('Falta preparar proveedores por unidad en staging. No se guardaron cambios.')


def consulta(Proveedor, organizacion_id, unidad_id, session):
    base = session.query(Proveedor).filter(Proveedor.organizacion_id == organizacion_id)
    if not preparado(session.connection()):
        # No mostrar proveedores globales mientras falta la preparación.
        return base.filter(Proveedor.id == -1)
    ids = session.query(ProveedorUnidad.proveedor_id).filter_by(organizacion_id=organizacion_id, unidad_negocio_id=unidad_id)
    return base.filter(Proveedor.id.in_(ids))


def exigir(proveedor, organizacion_id, unidad_id, session):
    exigir_preparado(session)
    vinculo = session.query(ProveedorUnidad).filter_by(organizacion_id=organizacion_id, unidad_negocio_id=unidad_id,
        proveedor_id=getattr(proveedor,'id',None)).first() if proveedor is not None else None
    if proveedor is None or proveedor.organizacion_id != organizacion_id or vinculo is None:
        raise ValueError('El proveedor no está vinculado a la unidad activa.')
    return proveedor


def vincular(proveedor, organizacion_id, unidad_id, session, estado=None):
    exigir_preparado(session)
    from models.unidad_negocio import UnidadNegocio
    unidad=session.query(UnidadNegocio).filter_by(id=unidad_id,organizacion_id=organizacion_id,activa=True).with_for_update().first()
    if unidad is None or proveedor.organizacion_id != organizacion_id:
        raise ValueError('El proveedor o la unidad no pertenecen a la empresa activa.')
    session.flush()
    v=session.query(ProveedorUnidad).filter_by(proveedor_id=proveedor.id,unidad_negocio_id=unidad_id).first()
    if v is None:
        v=ProveedorUnidad(organizacion_id=organizacion_id,proveedor_id=proveedor.id,unidad_negocio_id=unidad_id,estado=estado or 'activo')
        session.add(v)
    if estado is not None:
        if estado not in {'activo','inactivo'}:raise ValueError('Estado del proveedor inválido.')
        v.estado=estado
    session.flush()


def vincular_por_identidad(valor, Proveedor, organizacion_id, unidad_id, session):
    exigir_preparado(session)
    valor=str(valor or '').strip()
    if not valor: raise ValueError('Ingresá el código o CUIT exacto del proveedor existente.')
    cuit=re.sub(r'\D','',valor)
    condiciones=[Proveedor.codigo == valor.upper()]
    if len(cuit)==11: condiciones.append(Proveedor.cuit == cuit)
    filas=session.query(Proveedor).filter(Proveedor.organizacion_id==organizacion_id,or_(*condiciones)).all()
    if len(filas)!=1: raise ValueError('No se encontró un único proveedor con ese código o CUIT en la empresa.')
    vincular(filas[0],organizacion_id,unidad_id,session)
    return filas[0]


def previsualizar(filas,mapeo,*,Proveedor,organizacion_id,unidad_id,session):
    from services.importacion_proveedores_compra import previsualizar_proveedores
    visibles=consulta(Proveedor,organizacion_id,unidad_id,session).all()
    vista=previsualizar_proveedores(filas,mapeo,proveedores=para_importacion(visibles,organizacion_id,unidad_id,session))
    # Las coincidencias no asignadas se rechazan sin copiar datos de otra unidad.
    identidades=session.query(Proveedor.id,Proveedor.codigo,Proveedor.cuit).filter_by(organizacion_id=organizacion_id).all()
    ids={p.id for p in visibles}
    codigos={str(p.codigo or '').upper():p.id for p in identidades}
    cuits={p.cuit:p.id for p in identidades if p.cuit}
    for f in vista:
        d=f['datos']; coincidencias={codigos.get(str(d.get('codigo') or '').upper()),cuits.get(d.get('cuit'))}-{None}
        if coincidencias-ids:
            f['accion']='rechazado';f['proveedor_id']=None
            f['errores'].append('El proveedor ya existe fuera de esta unidad. Vinculalo explícitamente antes de importarlo.')
    return vista


def estados(organizacion_id,unidad_id,session):
    if not preparado(session.connection()):return {}
    return {v.proveedor_id:v.estado for v in session.query(ProveedorUnidad).filter_by(organizacion_id=organizacion_id,unidad_negocio_id=unidad_id).all()}


def para_importacion(proveedores,organizacion_id,unidad_id,session):
    from types import SimpleNamespace
    from services.importacion_proveedores_compra import CAMPOS_PROVEEDORES
    propios=estados(organizacion_id,unidad_id,session)
    return [SimpleNamespace(id=p.id,**({k:getattr(p,k,None) for k in CAMPOS_PROVEEDORES}|{'estado':propios.get(p.id,'inactivo')})) for p in proveedores]


def operativo(proveedor,organizacion_id,unidad_id,session):
    from types import SimpleNamespace
    exigir(proveedor,organizacion_id,unidad_id,session)
    return SimpleNamespace(id=proveedor.id,organizacion_id=proveedor.organizacion_id,
        estado=estados(organizacion_id,unidad_id,session).get(proveedor.id,'inactivo'))


def buscar_para_vincular(texto, Proveedor, organizacion_id, session):
    """Sólo identidades de la empresa para una vinculación explícita del admin."""
    from sqlalchemy import func
    texto=str(texto or '').strip()[:120]
    if len(texto)<2:return []
    valor=texto.lower()
    condiciones=[func.lower(Proveedor.razon_social).contains(valor,autoescape=True),func.lower(Proveedor.codigo).contains(valor,autoescape=True)]
    cuit=re.sub(r'\D','',texto)
    if len(cuit)>=2:condiciones.append(Proveedor.cuit.contains(cuit,autoescape=True))
    return session.query(Proveedor).filter(Proveedor.organizacion_id==organizacion_id,or_(*condiciones)).order_by(Proveedor.razon_social,Proveedor.id).limit(20).all()
