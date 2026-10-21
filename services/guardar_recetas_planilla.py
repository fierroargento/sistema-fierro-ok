"""Guarda en grupo recetas EXISTENTES ya validadas; no activa costos."""
import json
from collections import defaultdict
from types import SimpleNamespace
from sqlalchemy import select,update,delete,bindparam
from services.guardar_fabricacion_lote import _insertar


def guardar_recetas(preparadas,session,org,usuario):
    if not preparadas:return
    from services.productos_produccion_maestro import modelos
    from services.productos_despiece import huella_perfil
    from services.motor_costeo_productos import huella_detalles
    from models.producto_despiece_costeo import ProductoDespieceCosteo as Despiece
    from models.costo_producto_version import CostoProductoVersion as Version
    from models.costo_producto_detalle import CostoProductoDetalle as Detalle
    perfiles={p['perfil'].id for _,p,_ in preparadas}
    if len(perfiles)!=len(preparadas) or any(p['perfil'].organizacion_id!=org or p['perfil'].producto_id!=producto.id for producto,p,_ in preparadas):raise ValueError('La receta no pertenece al producto y organización.')
    datos_huella={ident:dict(insumos_costeo=[],operaciones_costeo=[]) for ident in perfiles}
    for grupo,(Modelo,_,_) in modelos()[1].items():
        t=Modelo.__table__;altas=[];ediciones=[];conservar=[]
        for _,p,_ in preparadas:
            for linea in p['lineas'][grupo]:
                d={k:v for k,v in linea.items() if k not in ('id','recurso')};d['observacion']=d['observacion'].strip() or None
                if linea['id']:
                    conservar.append(linea['id']);ediciones.append(dict(_id=linea['id'],_perfil=p['perfil'].id,**{'v_'+k:v for k,v in d.items()}))
                else:altas.append(dict(perfil_costeo_id=p['perfil'].id,**d))
        session.execute(delete(t).where(t.c.perfil_costeo_id.in_(perfiles),t.c.id.not_in(conservar)))
        if ediciones:
            campos={k[2:]:bindparam(k) for k in ediciones[0] if k.startswith('v_')}
            session.execute(update(t).where(t.c.id==bindparam('_id'),t.c.perfil_costeo_id==bindparam('_perfil')).values(**campos),ediciones)
        _insertar(session,t,altas)
        if grupo in ('insumos','operaciones'):
            destino='insumos_costeo' if grupo=='insumos' else 'operaciones_costeo'
            for r in session.execute(select(t).where(t.c.perfil_costeo_id.in_(perfiles))).mappings():datos_huella[r['perfil_costeo_id']][destino].append(SimpleNamespace(**r))
    tabla=Despiece.__table__;existentes={r.perfil_costeo_id for r in session.query(Despiece).filter(Despiece.organizacion_id==org,Despiece.perfil_costeo_id.in_(perfiles))}
    nuevos=[];cambios=[]
    for _,p,_ in preparadas:
        ident=p['perfil'].id
        if p['despiece'] is None:
            session.execute(delete(tabla).where(tabla.c.organizacion_id==org,tabla.c.perfil_costeo_id==ident));continue
        d=dict(contenido=json.dumps(p['despiece'],ensure_ascii=False,sort_keys=True),huella_composicion=huella_perfil(SimpleNamespace(**datos_huella[ident])))
        if ident in existentes:cambios.append(dict(_id=ident,**{'v_'+k:v for k,v in d.items()}))
        else:nuevos.append(dict(perfil_costeo_id=ident,organizacion_id=org,revision=1,**d))
    if cambios:session.execute(update(tabla).where(tabla.c.organizacion_id==org,tabla.c.perfil_costeo_id==bindparam('_id')).values(contenido=bindparam('v_contenido'),huella_composicion=bindparam('v_huella_composicion'),revision=tabla.c.revision+1),cambios)
    _insertar(session,tabla,nuevos)
    productos={p.id for p,_,_ in preparadas};ultimas={};maximos=defaultdict(int)
    for v in session.query(Version).filter(Version.organizacion_id==org,Version.producto_id.in_(productos),Version.moneda=='ARS').order_by(Version.numero_version.desc()):
        clave=(v.producto_id,v.unidad_negocio_id);maximos[clave]=max(maximos[clave],v.numero_version)
        if v.tipo=='calculado':ultimas.setdefault(clave,v)
    detalles=defaultdict(list)
    for r in session.execute(select(Detalle.__table__).where(Detalle.costo_producto_version_id.in_([v.id for v in ultimas.values()])).order_by(Detalle.orden)).mappings():detalles[r['costo_producto_version_id']].append(dict(r))
    nuevas=[];por_producto={}
    for producto,p,costo in preparadas:
        clave=(producto.id,p['unidad_id']);v=ultimas.get(clave)
        if v is not None and v.estado!='cancelado' and huella_detalles(detalles[v.id])==costo['huella']:continue
        nuevas.append(dict(organizacion_id=org,producto_id=producto.id,unidad_negocio_id=p['unidad_id'],moneda='ARS',tipo='calculado',numero_version=maximos[clave]+1,costo_total_centavos=costo['total_centavos'],estado='preparatorio',vigente=False,creado_por_username=str(getattr(usuario,'username',None) or '').strip() or None,observacion='Calculado desde la ficha de fabricación del maestro.'))
        por_producto[clave]=costo['detalles']
    resultado=_insertar(session,Version.__table__,nuevas,(Version.__table__.c.id,Version.__table__.c.producto_id,Version.__table__.c.unidad_negocio_id))
    _insertar(session,Detalle.__table__,[dict(costo_producto_version_id=r['id'],**d) for r in resultado for d in por_producto[(r['producto_id'],r['unidad_negocio_id'])]])
    session.expire_all()
