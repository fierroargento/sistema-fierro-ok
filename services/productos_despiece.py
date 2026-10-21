"""Piezas físicas y tiempos alimentan la composición de Costos existente."""
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from sqlalchemy import inspect


def disponible(session):
    from models.producto_despiece_costeo import ProductoDespieceCosteo as Modelo
    i=inspect(session.connection())
    return i.has_table(Modelo.__tablename__) and set(Modelo.__table__.c.keys()) <= {c['name'] for c in i.get_columns(Modelo.__tablename__)}


def huella_perfil(perfil):
    datos={}
    for g,campos in {
      'insumos_costeo':['insumo_id','cantidad','porcentaje_merma','observacion'],
      'operaciones_costeo':['empleado_id','nombre','minutos','orden','observacion']}.items():
        datos[g]=[{c:str(getattr(r,c) or '') for c in campos} for r in sorted(getattr(perfil,g),key=lambda r:r.id or 0)]
    return sha256(json.dumps(datos,sort_keys=True).encode()).hexdigest()


def cargar(perfil):
    estado=inspect(perfil,raiseerr=False)
    session=estado.session if estado is not None else None
    if session is None or not disponible(session):return None
    from models.producto_despiece_costeo import ProductoDespieceCosteo as Modelo
    r=session.query(Modelo).filter_by(perfil_costeo_id=perfil.id,organizacion_id=perfil.organizacion_id).populate_existing().first()
    if r is None:return None
    datos=json.loads(r.contenido)
    return {'datos':datos,'revision':r.revision,'actual':r.huella_composicion==huella_perfil(perfil)}


def cargar_lote(perfiles,session):
    """Lee despieces de los perfiles ya autorizados sin una consulta por producto."""
    if not perfiles or not disponible(session):return {}
    from models.producto_despiece_costeo import ProductoDespieceCosteo as Modelo
    autorizados={p.id:p for p in perfiles}
    registros=session.query(Modelo).filter(Modelo.perfil_costeo_id.in_(autorizados),Modelo.organizacion_id.in_({p.organizacion_id for p in perfiles})).populate_existing().all()
    return {r.perfil_costeo_id:{'datos':json.loads(r.contenido),'revision':r.revision,
        'actual':r.huella_composicion==huella_perfil(autorizados[r.perfil_costeo_id])}
        for r in registros if r.organizacion_id==autorizados[r.perfil_costeo_id].organizacion_id}


def expandir(valor,session,org,perfil,*,lectura=None):
    if lectura is not None:lectura.comprobar(session,org)
    if 'piezas' not in valor:return valor,None
    if not (lectura.esquema(disponible) if lectura is not None else disponible(session)):raise ValueError('Falta preparar el despiece de Productos en staging.')
    from services.productos_costo_maestro import _decimal
    from models.fuentes_costo_productivo import InsumoProductivo
    piezas=valor.get('piezas');tareas=valor.get('tareas',[])
    if not isinstance(piezas,list) or len(piezas)>100 or not isinstance(tareas,list) or len(tareas)>100:
        raise ValueError('Se admiten hasta 100 componentes y 100 tareas.')
    # La base es consumo neto; no se agrega merma ni se divide por el bulto de compra.
    salida=dict(valor);salida['insumos']=[];salida['operaciones']=[]
    despiece={'piezas':[],'tareas':[],'tarifa_id':valor.get('tarifa_id') or None}
    consumos={}
    for p in piezas:
        if not isinstance(p,dict):raise ValueError('Revisá los componentes del producto.')
        ident=str(p.get('insumo_id') or '')
        if not ident.isdigit():raise ValueError('Seleccioná el material del componente.')
        recurso=lectura.recurso(InsumoProductivo,int(ident)) if lectura is not None else session.query(InsumoProductivo).filter_by(id=int(ident),organizacion_id=org).first()
        if recurso is None:raise ValueError('El material no pertenece a la organización.')
        nombre=str(p.get('nombre') or '').strip()
        if not nombre or len(nombre)>160:raise ValueError('Cada componente requiere un nombre de hasta 160 caracteres.')
        cantidad=_decimal(p.get('cantidad'),'Cantidad de piezas',Decimal('999999999999.999999'),6)
        if cantidad is None or cantidad<=0:raise ValueError('La cantidad del componente debe ser mayor que cero.')
        modo=p.get('modo','directo');largo=None;rendimiento=None
        if modo=='longitud':
            if recurso.unidad_medida.strip().lower() not in {'m','metro','metros'}:raise ValueError('El cálculo por centímetros requiere un material cotizado por metro.')
            largo=_decimal(p.get('largo_cm'),'Medida en cm',Decimal('999999999999.999999'),6)
            if largo is None or largo<=0:raise ValueError('Ingresá la medida del componente en centímetros.')
            consumo=cantidad*largo/100
        elif modo=='rendimiento':
            rendimiento=_decimal(p.get('rendimiento'),'Piezas por unidad de material',Decimal('999999999999.999999'),6)
            if rendimiento is None or rendimiento<=0:raise ValueError('Ingresá cuántas piezas se obtienen por unidad de material.')
            consumo=cantidad/rendimiento
        elif modo=='directo':consumo=cantidad
        else:raise ValueError('Elegí cómo se calcula el consumo del componente.')
        if consumo<Decimal('0.000001') or consumo>Decimal('999999999999.999999'):raise ValueError('El consumo resultante del componente está fuera de rango.')
        consumos[int(ident)]=consumos.get(int(ident),Decimal(0))+consumo
        despiece['piezas'].append({'insumo_id':int(ident),'nombre':nombre,'cantidad':str(cantidad),'modo':modo,
            'largo_cm':str(largo) if largo is not None else '', 'rendimiento':str(rendimiento) if rendimiento is not None else ''})
    previos={r.insumo_id:r for r in perfil.insumos_costeo} if perfil else {}
    for ident,consumo in consumos.items():
        consumo=consumo.quantize(Decimal('0.000001'),rounding=ROUND_HALF_UP)
        if consumo>Decimal('999999999999.999999'):raise ValueError('El consumo total del material está fuera de rango.')
        anterior=previos.get(ident)
        salida['insumos'].append({'id':anterior.id if anterior else None,'insumo_id':ident,'cantidad':str(consumo),
            'porcentaje_merma':'0','observacion':anterior.observacion if anterior else ''})
    if tareas:
        tarifa=str(valor.get('tarifa_id') or '')
        if not tarifa.isdigit():raise ValueError('Seleccioná la tarifa de mano de obra para las tareas del producto.')
        despiece['tarifa_id']=int(tarifa)
        anteriores=sorted(perfil.operaciones_costeo,key=lambda r:(r.orden,r.id)) if perfil else []
        for n,t in enumerate(tareas):
            if not isinstance(t,dict):raise ValueError('Revisá las tareas.')
            nombre=str(t.get('nombre') or '').strip()
            segundos=_decimal(t.get('segundos'),'Segundos por unidad',Decimal('99999999.999999'),6)
            if not nombre or len(nombre)>160 or segundos is None or segundos<=0:raise ValueError('Completá tarea y segundos por una unidad fabricada.')
            minutos=(segundos/60).quantize(Decimal('0.0001'),rounding=ROUND_HALF_UP)
            if minutos<=0:raise ValueError('El tiempo de la tarea es demasiado pequeño.')
            ant=anteriores[n] if n<len(anteriores) else None
            obs=ant.observacion if ant else ''
            salida['operaciones'].append({'id':ant.id if ant else None,'empleado_id':int(tarifa),'nombre':nombre,'minutos':str(minutos),'observacion':obs})
            despiece['tareas'].append({'nombre':nombre,'segundos':str(segundos)})
    if not piezas and not tareas:raise ValueError('Agregá los componentes o las tareas del producto.')
    return salida,despiece


def guardar(perfil,despiece,session):
    from models.producto_despiece_costeo import ProductoDespieceCosteo as Modelo
    # No conserva una representación desactualizada si una interfaz anterior edita los consumos.
    r=session.query(Modelo).filter_by(perfil_costeo_id=perfil.id,organizacion_id=perfil.organizacion_id).first() if disponible(session) else None
    if despiece is None:
        if r is not None:session.delete(r)
        return
    session.expire(perfil,['insumos_costeo','operaciones_costeo'])
    firma=huella_perfil(perfil)
    if r is None:
        r=Modelo(perfil_costeo_id=perfil.id,organizacion_id=perfil.organizacion_id,revision=1);session.add(r)
    else:r.revision+=1
    r.contenido=json.dumps(despiece,ensure_ascii=False,sort_keys=True)
    r.huella_composicion=firma;session.flush()
