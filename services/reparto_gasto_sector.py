"""Una fuente de gasto, reparto por áreas y aplicación según minutos laborales."""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import inspect, func
from sqlalchemy.orm import object_session
from models.reparto_gasto_sector import RepartoGastoSector as Reparto
from services.distribucion_costos_fijos import _porcentaje, registrar_distribucion_costo_fijo

def preparado(session):
    return inspect(session.connection()).has_table(Reparto.__tablename__)

def actuales(session, org):
    if not preparado(session): return []
    return session.query(Reparto).filter_by(organizacion_id=org,vigente=True).all()

def contexto(session,org):
    from models.fuentes_costo_productivo import EmpleadoProductivo
    return dict(reparto_sector_preparado=preparado(session),
        repartos_sector={r.costo_fijo_id:r for r in actuales(session,org)},
        areas_reparto=session.query(EmpleadoProductivo).filter_by(organizacion_id=org,tipo_registro='recurso',activo=True).all())

def guardar(costo, datos, *, org, unidad, session, modelos, usuario_id=None):
    if not preparado(session): raise ValueError('Prepará el reparto por sectores antes de guardar.')
    if costo.organizacion_id != org or costo.unidad_negocio_id != unidad:
        raise ValueError('El reparto se gestiona desde la unidad responsable del gasto.')
    # Serializa cambios de reparto y verifica la revisión presentada.
    session.query(type(costo)).filter_by(id=costo.id).with_for_update().populate_existing().one()
    anterior=session.query(Reparto).filter_by(costo_fijo_id=costo.id,vigente=True).populate_existing().first()
    if str(anterior.id if anterior else '') != str(datos.get('reparto_version','')):
        raise ValueError('El reparto cambió. Recargá la página antes de guardar.')
    columnas=[datos.getlist(k) for k in ('sector_unidad','sector_area','sector_porcentaje')]
    if len(set(map(len,columnas)))!=1 or not 1<=len(columnas[0])<=50:
        raise ValueError('Revisá las filas del reparto.')
    filas=[];claves=set();unidades={u.id:u for u in modelos['UnidadNegocio'].query.filter_by(organizacion_id=org).all()}
    for uid,area,pct in zip(*columnas):
        p=_porcentaje(pct,'La participación')
        if p != p.quantize(Decimal('0.0001')): raise ValueError('Usá hasta cuatro decimales en la participación.')
        if not p: continue
        try: uid=int(uid)
        except (ValueError,TypeError): raise ValueError('Elegí una unidad válida.')
        if uid not in unidades or not unidades[uid].activa: raise ValueError('Elegí una unidad activa de esta empresa.')
        if area=='deposito': nombre='Depósito';rid=None
        else:
            try: rid=int(area)
            except (ValueError,TypeError): raise ValueError('Elegí un área o depósito.')
            r=modelos['EmpleadoProductivo'].query.filter_by(id=rid,organizacion_id=org,unidad_negocio_id=uid,tipo_registro='recurso',activo=True).first()
            if r is None: raise ValueError('El área no corresponde a la unidad elegida.')
            nombre=r.nombre
        clave=(uid,rid)
        if clave in claves: raise ValueError('Unificá las filas del mismo sector.')
        claves.add(clave);filas.append(dict(unidad_id=uid,area_id=rid,nombre=nombre,porcentaje=str(p)))
    if sum((Decimal(f['porcentaje']) for f in filas),Decimal(0))!=100:
        raise ValueError('El reparto debe sumar 100%.')
    if anterior and anterior.filas==filas:return anterior
    agregados=defaultdict(lambda: [Decimal(0),Decimal(0)])
    for f in filas:
        p=Decimal(f['porcentaje']);agregados[f['unidad_id']][0]+=p
        if f['area_id'] is not None:agregados[f['unidad_id']][1]+=p
    resumen=[dict(unidad_negocio_id=uid,porcentaje_asignacion=p,ubicacion_costo='Reparto por sectores',
        porcentaje_productivo=prod/p*100) for uid,(p,prod) in agregados.items()]
    registrar_distribucion_costo_fijo(costo,resumen,organizacion_id=org,unidades_validas=list(unidades.values()),
        Modelo=modelos['CostoFijoDistribucionVersion'],db_session=session,usuario_id=usuario_id,
        observacion='Reparto por sectores. Depósito pendiente de asignación a productos.',commit=False)
    if anterior:anterior.vigente=False;session.flush()
    revision=(session.query(func.max(Reparto.numero_revision)).filter_by(costo_fijo_id=costo.id).scalar() or 0)+1
    nuevo=Reparto(organizacion_id=org,costo_fijo_id=costo.id,numero_revision=revision,filas=filas,creado_por_usuario_id=usuario_id)
    session.add(nuevo);session.flush();return nuevo

def detalles(perfil):
    session=object_session(perfil) if inspect(perfil,raiseerr=False) is not None else None
    if session is None:
        session=next((object_session(l.empleado) for l in perfil.operaciones_costeo if inspect(l.empleado,raiseerr=False) is not None),None)
    if session is None:return []
    from models.fuentes_costo_productivo import CostoFijoProductivo
    resultado=[]
    for reparto in actuales(session,perfil.organizacion_id):
        filas=[f for f in reparto.filas if f['unidad_id']==perfil.unidad_negocio_id and f['area_id'] is not None]
        usos=defaultdict(lambda:Decimal(0));recursos={}
        for l in perfil.operaciones_costeo:
            rid=l.empleado.id
            usos[rid]+=Decimal(l.minutos);recursos[rid]=l.empleado
        aplicables=[f for f in filas if usos[f['area_id']]>0]
        if not aplicables:continue
        costo=session.get(CostoFijoProductivo,reparto.costo_fijo_id)
        if not costo.activo:continue
        if any(l.costo_fijo.id==costo.id for l in perfil.costos_fijos_costeo):
            raise ValueError(f'{costo.nombre}: quitá la asignación manual; ya se aplica por sector para evitar duplicaciones.')
        v=next((v for v in costo.versiones if v.vigente and v.moneda=='ARS'),None)
        if v is None:raise ValueError(f'{costo.nombre}: falta importe vigente en ARS.')
        for f in aplicables:
            recurso=recursos[f['area_id']]
            tarifa=next((v for v in recurso.versiones_costo if v.vigente and v.moneda=='ARS'),None)
            if tarifa is None or tarifa.horas_productivas<=0:raise ValueError(f'{f["nombre"]}: faltan horas productivas de Personal para repartir el gasto.')
            por_minuto=(Decimal(v.importe_mensual_centavos)*Decimal(f['porcentaje'])/100/(Decimal(tarifa.horas_productivas)*60)).quantize(Decimal(1),rounding=ROUND_HALF_UP)
            resultado.append(dict(tipo='elaboracion',codigo=costo.codigo,concepto=costo.nombre+' · '+f['nombre'],
                cantidad=usos[f['area_id']],unidad_medida='minuto',costo_unitario_centavos=int(por_minuto),porcentaje_merma=0,
                observacion=f'Reparto r{reparto.numero_revision}; importe v{v.numero_version}; {f["porcentaje"]}% del gasto; horas productivas {tarifa.horas_productivas}, tarifa laboral v{tarifa.numero_version}. Depósito excluido: pendiente de reparto.'))
    return resultado
