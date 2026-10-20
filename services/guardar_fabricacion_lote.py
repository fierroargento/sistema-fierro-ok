"""Persistencia agrupada de ALTAS de fabricación ya validadas por el maestro.

Sólo el importador la utiliza: sin actualizaciones, identidades de insumo, combos,
relaciones comerciales ni costos manuales. Una sola transacción del llamador.
"""
import json
from types import SimpleNamespace
from sqlalchemy import insert


def _insertar(session, tabla, filas, devolver=()):
    if not filas:
        return []
    sentencia = insert(tabla)
    if devolver:
        return list(session.execute(sentencia.returning(*devolver), filas).mappings())
    session.execute(sentencia, filas)
    return []


def guardar_nuevas(preparadas, *, Producto, session, organizacion_id, usuario):
    from services.productos_ficha_maestra import CAMPOS_BASE
    from services.producto_habilitaciones import CAMPOS_FICHA
    from models.producto_ficha_maestra import ProductoFichaMaestra as Ficha
    from models.producto_datos_generales import ProductoDatosGenerales as General
    from models.producto_despiece_costeo import ProductoDespieceCosteo as Despiece
    from models.perfil_costeo_producto import PerfilCosteoProducto as Perfil
    from models.costo_producto_version import CostoProductoVersion as Version
    from models.costo_producto_detalle import CostoProductoDetalle as Detalle
    from services.productos_produccion_maestro import modelos
    from services.productos_despiece import huella_perfil
    if not preparadas:
        return
    for fila, plan, adicional, costo in preparadas:
        datos = fila['datos']
        if (datos['tipo'] != 'produccion' or datos['insumo_id'] is not None or datos.get('componentes_combo')
                or plan['perfil'] is not None or plan['despiece'] is None
                or adicional.get('precio_costo_centavos') is not None or adicional.get('moneda_costo') != 'ARS'
                or not adicional.get('costo_presentado') or not adicional.get('iibb_presentado')
                or any(adicional.get(k) for k in ('proveedores','sucursales','depositos','codigos_barras','imagenes_nuevas','imagenes_conservar'))):
            raise ValueError('El lote agrupado admite sólo altas nuevas de fabricación sin relaciones adicionales.')
    # RETURNING incluye la clave natural: no depende del orden de respuesta SQL.
    ids = {r['sku']:r['id'] for r in _insertar(session, Producto.__table__,
        [dict(organizacion_id=organizacion_id, **{c:f['datos'][c] for c in CAMPOS_BASE}) for f,_,_,_ in preparadas],
        (Producto.__table__.c.id, Producto.__table__.c.sku))}
    _insertar(session, Ficha.__table__, [dict(producto_id=ids[f['sku']],organizacion_id=organizacion_id,revision=1,
        **{c:f['datos'][c] for c in CAMPOS_FICHA}) for f,_,_,_ in preparadas])
    campos = ('rubro','subrubro','marca','iva_pct','iibb_pct','utilidad_pct','utilidad_base','sucursales_definidas','depositos_definidos')
    _insertar(session, General.__table__, [dict(producto_id=ids[f['sku']],organizacion_id=organizacion_id,
        revision=1,moneda_costo='ARS',costo_carga_id=None,**{c:a[c] for c in campos}) for f,_,a,_ in preparadas])
    perfiles = {r['producto_id']:r['id'] for r in _insertar(session, Perfil.__table__,
        [dict(organizacion_id=organizacion_id,producto_id=ids[f['sku']],unidad_negocio_id=p['unidad_id'],tipo='produccion',activo=True,observacion=None) for f,p,_,_ in preparadas],
        (Perfil.__table__.c.id, Perfil.__table__.c.producto_id))}
    datos_huella = {pid:dict(insumos_costeo=[],operaciones_costeo=[]) for pid in perfiles.values()}
    for grupo,(Modelo,_,_) in modelos()[1].items():
        filas=[]
        for f,p,_,_ in preparadas:
            for linea in p['lineas'][grupo]:
                d={k:v for k,v in linea.items() if k not in ('id','recurso')}
                d['observacion']=d['observacion'].strip() or None
                filas.append(dict(perfil_costeo_id=perfiles[ids[f['sku']]],**d))
        devolver=tuple(Modelo.__table__.c) if grupo in ('insumos','operaciones') else ()
        guardadas=_insertar(session, Modelo.__table__, filas, devolver)
        if devolver:
            destino='insumos_costeo' if grupo=='insumos' else 'operaciones_costeo'
            for r in guardadas:datos_huella[r['perfil_costeo_id']][destino].append(SimpleNamespace(**r))
    _insertar(session, Despiece.__table__, [dict(perfil_costeo_id=perfiles[ids[f['sku']]],organizacion_id=organizacion_id,
        revision=1,contenido=json.dumps(p['despiece'],ensure_ascii=False,sort_keys=True),
        huella_composicion=huella_perfil(SimpleNamespace(**datos_huella[perfiles[ids[f['sku']]]]))) for f,p,_,_ in preparadas])
    versiones = {r['producto_id']:r['id'] for r in _insertar(session, Version.__table__,
        [dict(organizacion_id=organizacion_id,producto_id=ids[f['sku']],unidad_negocio_id=p['unidad_id'],moneda='ARS',
            tipo='calculado',numero_version=1,costo_total_centavos=c['total_centavos'],estado='preparatorio',vigente=False,
            creado_por_username=str(getattr(usuario,'username',None) or '').strip() or None,
            observacion='Calculado desde la ficha de fabricación del maestro.') for f,p,_,c in preparadas],
        (Version.__table__.c.id,Version.__table__.c.producto_id))}
    _insertar(session, Detalle.__table__, [dict(costo_producto_version_id=versiones[ids[f['sku']]],**d)
        for f,_,_,c in preparadas for d in c['detalles']])
