"""Ficha de fabricación dentro del maestro, sobre la composición existente."""
from decimal import Decimal
from hashlib import sha256
import json
from types import SimpleNamespace
from sqlalchemy import inspect


def modelos():
    from models.perfil_costeo_producto import PerfilCosteoProducto
    from models.composicion_costo_producto import ProductoInsumoCosteo, ProductoOperacionCosteo, ProductoMaquinaCosteo, ProductoCostoFijoCosteo
    from models.fuentes_costo_productivo import (InsumoProductivo, EmpleadoProductivo, MaquinaProductiva, CostoFijoProductivo,
        InsumoPrecioVersion, EmpleadoCostoVersion, MaquinaCostoVersion, CostoFijoVersion, CostoFijoDistribucionVersion)
    grupos = {
        'insumos':(ProductoInsumoCosteo,InsumoProductivo,'insumo_id'),
        'operaciones':(ProductoOperacionCosteo,EmpleadoProductivo,'empleado_id'),
        'maquinas':(ProductoMaquinaCosteo,MaquinaProductiva,'maquina_id'),
        'fijos':(ProductoCostoFijoCosteo,CostoFijoProductivo,'costo_fijo_id'),
    }
    tablas=[PerfilCosteoProducto.__table__]+[m.__table__ for g in grupos.values() for m in g[:2]]
    tablas += [m.__table__ for m in (InsumoPrecioVersion,EmpleadoCostoVersion,MaquinaCostoVersion,CostoFijoVersion,CostoFijoDistribucionVersion)]
    return PerfilCosteoProducto,grupos,tablas


def disponible(session):
    # Evita repetir la inspección de tablas en cada lectura/huella de una petición.
    from flask import has_request_context, g
    clave=id(session.get_bind())
    cache=getattr(g,'_ficha_fabricacion_esquema',{}) if has_request_context() else {}
    if clave in cache:return cache[clave]
    _,_,tablas=modelos();i=inspect(session.connection())
    resultado=all(i.has_table(t.name) and set(t.c.keys()) <= {c['name'] for c in i.get_columns(t.name)} for t in tablas)
    if has_request_context():
        cache[clave]=resultado;g._ficha_fabricacion_esquema=cache
    return resultado


def leer_producciones(productos,session,org):
    if not productos or not disponible(session):return {}
    Perfil,grupos,_=modelos()
    perfiles=session.query(Perfil).filter(Perfil.organizacion_id==org,Perfil.producto_id.in_([p.id for p in productos]),Perfil.tipo=='produccion').populate_existing().all()
    salida={};por_id={}
    for p in perfiles:
        d={'perfil_id':p.id,'unidad_id':p.unidad_negocio_id,'activo':p.activo,**{g:[] for g in grupos}}
        salida.setdefault(p.producto_id,[]).append(d);por_id[p.id]=d
    for nombre,(Modelo,_,clave) in grupos.items():
        if not por_id:continue
        for r in session.query(Modelo).filter(Modelo.perfil_costeo_id.in_(por_id)).order_by(Modelo.id).populate_existing():
            campos=['id',clave,'observacion']+({'insumos':['cantidad','porcentaje_merma'],'operaciones':['nombre','minutos','orden'],
                'maquinas':['nombre','minutos','orden'],'fijos':['porcentaje_asignacion','unidades_mensuales']}[nombre])
            por_id[r.perfil_costeo_id][nombre].append({c:format(getattr(r,c),'f') if isinstance(getattr(r,c),Decimal) else getattr(r,c) for c in campos})
    from services.productos_despiece import cargar
    for p in perfiles:
        despiece=cargar(p)
        if despiece is not None:por_id[p.id]['despiece']=despiece
    return salida


def _id(v,opcional=False):
    if opcional and v in (None,''):return None
    if isinstance(v,bool) or not str(v).isdigit() or int(v)<=0:raise ValueError('Seleccioná un recurso o una unidad válidos.')
    return int(v)


def preparar(valor,session,org,producto_id=None):
    if not disponible(session):raise ValueError('La ficha de fabricación todavía no está preparada en este entorno.')
    if isinstance(valor,str):
        if len(valor)>100000:raise ValueError('La ficha de fabricación supera el tamaño permitido.')
        try:valor=json.loads(valor)
        except ValueError as e:raise ValueError('Revisá la ficha de fabricación.') from e
    if not isinstance(valor,dict):raise ValueError('Revisá la ficha de fabricación.')
    unidad=_id(valor.get('unidad_id'),True)
    from models.unidad_negocio import UnidadNegocio
    if unidad is not None and session.query(UnidadNegocio).filter_by(id=unidad,organizacion_id=org,activa=True).first() is None:
        raise ValueError('La unidad de fabricación no está activa o no pertenece a tu organización.')
    from models.producto import Producto
    if producto_id is not None and session.query(Producto).filter_by(id=producto_id,organizacion_id=org).first() is None:
        raise ValueError('El producto no pertenece a tu organización.')
    Perfil,grupos,_=modelos()
    perfil=session.query(Perfil).filter_by(organizacion_id=org,producto_id=producto_id,unidad_negocio_id=unidad).first() if producto_id else None
    if perfil and (perfil.tipo!='produccion' or not perfil.activo):raise ValueError('El perfil de fabricación no está activo o tiene otro tipo.')
    from services.productos_despiece import expandir
    valor,despiece=expandir(valor,session,org,perfil)
    plan={'unidad_id':unidad,'perfil':perfil,'lineas':{},'despiece':despiece}
    from services.productos_costo_maestro import _decimal
    from services.composicion_costo_producto import _alcance
    from services.producto_habilitaciones import exigir_uso_insumo
    contexto=SimpleNamespace(tipo='produccion',organizacion_id=org,unidad_negocio_id=unidad)
    for grupo,(Modelo,Recurso,clave) in grupos.items():
        filas=valor.get(grupo,[])
        if not isinstance(filas,list) or len(filas)>100:raise ValueError('Cada sección admite hasta 100 filas de fabricación.')
        plan['lineas'][grupo]=[];vistos=set();ids=set()
        for n,f in enumerate(filas):
            if not isinstance(f,dict):raise ValueError('Revisá las filas de fabricación.')
            rid=_id(f.get(clave));recurso=session.query(Recurso).filter_by(id=rid,organizacion_id=org).first()
            _alcance(contexto,recurso)
            if not recurso.activo:raise ValueError(f'{recurso.nombre}: el recurso está inactivo.')
            if grupo=='insumos':exigir_uso_insumo(recurso,'insumo',session,unidad)
            if grupo=='fijos' and not recurso.integra_costo_produccion:raise ValueError('El costo fijo no está marcado como productivo.')
            ident=_id(f.get('id'),True)
            if ident is not None:
                anterior=session.query(Modelo).filter_by(id=ident,perfil_costeo_id=perfil.id if perfil else -1).first()
                if anterior is None or ident in ids:raise ValueError('La fila de fabricación no pertenece al perfil seleccionado o está repetida.')
                ids.add(ident)
                if grupo in {'insumos','fijos'} and getattr(anterior,clave)!=rid:raise ValueError('Volvé a seleccionar el recurso en una fila nueva.')
            d={'id':ident,clave:rid,'recurso':recurso,'observacion':str(f.get('observacion') or '').strip()}
            if len(d['observacion'])>500:raise ValueError('La observación de fabricación supera 500 caracteres.')
            if grupo in {'operaciones','maquinas'}:
                d['nombre']=str(f.get('nombre') or '').strip()
                if not d['nombre'] or len(d['nombre'])>160:raise ValueError('Completá el nombre de cada operación (hasta 160 caracteres).')
                campos={'minutos':(Decimal('99999999.9999'),4)};d['orden']=n
            elif grupo=='insumos':campos={'cantidad':(Decimal('999999999999.999999'),6),'porcentaje_merma':(Decimal('100'),6)}
            else:campos={'porcentaje_asignacion':(Decimal('100'),6),'unidades_mensuales':(Decimal('999999999999.999999'),6)}
            for campo,(limite,precision) in campos.items():
                numero=_decimal(f.get(campo,'0' if campo=='porcentaje_merma' else ''),campo.replace('_',' '),limite,precision)
                if numero is None or (numero<=0 and campo!='porcentaje_merma'):raise ValueError(f'{campo.replace("_"," ")}: ingresá un valor mayor que cero.')
                d[campo]=numero
            unica=(rid,d.get('nombre')) if grupo=='maquinas' else rid
            if grupo!='operaciones' and unica in vistos:raise ValueError(f'Hay recursos repetidos en {grupo}.')
            vistos.add(unica);plan['lineas'][grupo].append(d)
    if not any(plan['lineas'].values()):raise ValueError('Agregá los insumos, operaciones o recursos que construyen el costo de fabricación.')
    return plan


def calcular(plan,org):
    from services.composicion_costo_producto import construir_detalles
    from services.costos_productos import preparar_detalles
    from services.motor_costeo_productos import huella_detalles
    nombres={'insumos':('insumos_costeo','insumo'),'operaciones':('operaciones_costeo','empleado'),
        'maquinas':('maquinas_costeo','maquina'),'fijos':('costos_fijos_costeo','costo_fijo')}
    perfil=SimpleNamespace(tipo='produccion',organizacion_id=org,unidad_negocio_id=plan['unidad_id'],despiece_preparado=plan.get('despiece'))
    for g,(attr,rel) in nombres.items():
        setattr(perfil,attr,[SimpleNamespace(**{k:v for k,v in d.items() if k!='recurso'},**{rel:d['recurso']}) for d in plan['lineas'][g]])
    detalles=preparar_detalles(construir_detalles(perfil))
    return {'detalles':detalles,'total_centavos':sum(d['subtotal_centavos'] for d in detalles),'huella':huella_detalles(detalles),'moneda':'ARS',
        'consumos':[{'nombre':d['recurso'].nombre,'cantidad':str(d['cantidad']),'unidad':d['recurso'].unidad_medida} for d in plan['lineas']['insumos']],
        'tiempo_segundos':str(sum((Decimal(t['segundos']) for t in (plan.get('despiece') or {}).get('tareas',[])),Decimal(0)))}


def guardar(producto,plan,session,usuario=None,huella_calculo=''):
    Perfil,grupos,_=modelos()
    from services.perfiles_costeo import crear_o_actualizar_perfil
    from models.producto import Producto
    from models.unidad_negocio import UnidadNegocio
    perfil=plan['perfil'] or crear_o_actualizar_perfil(organizacion_id=producto.organizacion_id,
        unidad_negocio_id=plan['unidad_id'],producto_id=producto.id,tipo='produccion',PerfilCosteoProducto=Perfil,
        UnidadNegocio=UnidadNegocio,Producto=Producto,db_session=session,commit=False)
    from services import composicion_costo_producto as servicio
    for g,(Modelo,_,clave) in grupos.items():
        conservar=[d['id'] for d in plan['lineas'][g] if d['id']]
        for r in session.query(Modelo).filter_by(perfil_costeo_id=perfil.id).all():
            if r.id not in conservar:session.delete(r)
        session.flush()
        for d in plan['lineas'][g]:
            base=dict(Modelo=Modelo,db_session=session,commit=False,observacion=d['observacion'])
            if g=='insumos':r=servicio.guardar_insumo(perfil,d['recurso'],cantidad=d['cantidad'],merma=d['porcentaje_merma'],**base)
            elif g=='fijos':r=servicio.guardar_costo_fijo(perfil,d['recurso'],porcentaje=d['porcentaje_asignacion'],unidades_mensuales=d['unidades_mensuales'],**base)
            else:
                funcion=servicio.guardar_operacion if g=='operaciones' else servicio.guardar_maquina
                r=funcion(perfil,d['recurso'],nombre=d['nombre'],minutos=d['minutos'],registro_id=d['id'],**base)
                r.orden=d['orden']
    session.flush()
    from services.productos_despiece import guardar as guardar_despiece
    guardar_despiece(perfil,plan.get("despiece"),session)
    try:resultado=calcular(plan,producto.organizacion_id)
    except ValueError as e:
        if huella_calculo:raise ValueError('El costo cambió desde el cálculo. Volvé a calcular: '+str(e)) from e
        return 'Fabricación guardada; costo pendiente: '+str(e)
    if huella_calculo and huella_calculo!=resultado['huella']:raise ValueError('Los costos cambiaron desde la simulación. Volvé a calcular antes de guardar.')
    from services.costos_productos import crear_version_costo
    from services.motor_costeo_productos import huella_detalles
    from models.costo_producto_version import CostoProductoVersion
    from models.costo_producto_detalle import CostoProductoDetalle
    from models.organizacion import Organizacion
    ultima=session.query(CostoProductoVersion).filter_by(organizacion_id=producto.organizacion_id,producto_id=producto.id,
        unidad_negocio_id=plan['unidad_id'],moneda='ARS',tipo='calculado').order_by(CostoProductoVersion.numero_version.desc()).first()
    if ultima is None or ultima.estado=='cancelado' or huella_detalles(ultima.detalles)!=resultado['huella']:
        crear_version_costo(organizacion_id=producto.organizacion_id,unidad_negocio_id=plan['unidad_id'],producto_id=producto.id,
            moneda='ARS',tipo='calculado',detalles=resultado['detalles'],creado_por_username=getattr(usuario,'username',None),
            observacion='Calculado desde la ficha de fabricación del maestro.',Organizacion=Organizacion,UnidadNegocio=UnidadNegocio,
            Producto=Producto,CostoProductoVersion=CostoProductoVersion,CostoProductoDetalle=CostoProductoDetalle,db_session=session,commit=False)
    return 'Costo de fabricación calculado en ARS y registrado en el historial; no se activa automáticamente.'
