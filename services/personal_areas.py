"""Áreas de mano de obra sobre los recursos e integrantes existentes."""
import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from services.recursos_productivos import _decimal_porcentaje, recalcular_tarifa_recurso
from services.personal_legajo import version_actual, actualizar_horas_sueldo
from services.distribucion_laboral import registrar_distribucion
from services.fechas import ahora_utc_naive


def huella_asignacion(e):
    datos=[e.id,e.unidad_negocio_id,e.sector,e.activo,e.observacion,sorted((v.recurso_id,str(v.porcentaje_dedicacion)) for v in e.participaciones_recurso)]
    return hashlib.sha256(json.dumps(datos,ensure_ascii=False).encode()).hexdigest()


def huella_area(r):
    return hashlib.sha256(json.dumps([r.id,r.organizacion_id,r.unidad_negocio_id,r.codigo,r.nombre,r.sector,r.activo],ensure_ascii=False).encode()).hexdigest()


def unidades_asignadas(empleados):
    return {e.id:' / '.join(sorted({v.recurso.unidad_negocio.nombre for v in e.participaciones_recurso if v.recurso.organizacion_id==e.organizacion_id and v.recurso.unidad_negocio_id})) or (e.unidad_negocio.nombre if e.unidad_negocio else 'Compartido') for e in empleados}


def guardar_asignacion(e,form,*,organizacion,modelos,db_session,usuario_id,unidades_permitidas=None):
    if form.get('huella_areas')!=huella_asignacion(e):raise ValueError('La asignación o las tareas cambiaron. Recargá la ficha antes de guardar.')
    tareas=str(form.get('tareas_habituales') or '').strip()
    if len(tareas)>500:raise ValueError('Las tareas habituales admiten hasta 500 caracteres.')
    recursos=modelos['EmpleadoProductivo'].query.filter_by(organizacion_id=organizacion.id,tipo_registro='recurso').order_by(modelos['EmpleadoProductivo'].id).with_for_update().all()
    editables=[r for r in recursos if unidades_permitidas is None or r.unidad_negocio_id in unidades_permitidas]
    permitidas={str(r.id) for r in editables}
    if any(k.startswith('area_porcentaje_') and k.removeprefix('area_porcentaje_') not in permitidas for k in form):raise ValueError('La asignación contiene un área ajena o inexistente.')
    nuevas={v.recurso_id:v.porcentaje_dedicacion for v in e.participaciones_recurso if str(v.recurso_id) not in permitidas}
    for recurso in editables:
        porcentaje=_decimal_porcentaje(form.get(f'area_porcentaje_{recurso.id}') or '0','La dedicación')
        if porcentaje:
            if not recurso.activo or recurso.unidad_negocio_id is None or not recurso.unidad_negocio.activa:raise ValueError('Elegí áreas activas con unidad de negocio activa.')
            nuevas[recurso.id]=porcentaje
    if nuevas and not e.activo:raise ValueError('Activá el empleado antes de asignarle áreas.')
    if nuevas and sum(nuevas.values(),Decimal(0))!=100:raise ValueError('El reparto entre todas las áreas debe sumar 100%.')
    if nuevas and version_actual(e) is None:raise ValueError('Cargá el sueldo antes de calcular el costo por área.')
    anteriores={v.recurso_id:v for v in e.participaciones_recurso}
    if any(v.recurso.organizacion_id!=organizacion.id for v in anteriores.values()):raise ValueError('Una asignación anterior requiere revisión de la organización.')
    normalizada=actualizar_horas_sueldo(e,modelos=modelos,db_session=db_session,usuario_id=usuario_id,usar_horas_existentes=True,recalcular_dependientes=False) if nuevas else None
    registro={'antes':{str(k):str(v.porcentaje_dedicacion) for k,v in anteriores.items()},'despues':{str(k):str(v) for k,v in nuevas.items()},'unidad_anterior':e.unidad_negocio_id}
    cambio=any(anteriores[k].porcentaje_dedicacion!=nuevas.get(k) for k in anteriores) or any(k not in anteriores for k in nuevas)
    unidades_efectivas={r.unidad_negocio_id for r in recursos if r.id in nuevas}
    unidad_base=next(iter(unidades_efectivas)) if len(unidades_efectivas)==1 else None
    sector_base=' / '.join(sorted({r.sector for r in recursos if r.id in nuevas}))[:120]
    cambio_unidad=bool(nuevas) and (e.unidad_negocio_id!=unidad_base or e.sector!=sector_base)
    if nuevas:e.unidad_negocio_id=unidad_base;e.sector=sector_base
    e.observacion=tareas or None
    registro['unidad_actual']=e.unidad_negocio_id
    if not cambio and normalizada is None and not cambio_unidad:return registro
    Vinculo=modelos['RecursoEmpleadoProductivo']
    for recurso_id,v in anteriores.items():
        if recurso_id not in nuevas:db_session.delete(v)
    for recurso_id,p in nuevas.items():
        v=anteriores.get(recurso_id)
        if v is None:v=Vinculo(recurso_id=recurso_id,empleado_id=e.id);db_session.add(v)
        v.porcentaje_dedicacion=p
    db_session.flush();db_session.expire(e,['participaciones_recurso'])
    # Proyección por unidad para los consumidores existentes, sin otra carga manual.
    Modelo=modelos['EmpleadoDistribucionVersion'];vigentes=Modelo.query.filter_by(empleado_id=e.id,vigente=True).all()
    previo={v.unidad_negocio_id:v for v in vigentes};por_unidad=defaultdict(lambda:Decimal(0));sectores=defaultdict(set)
    for r in recursos:
        if r.id in nuevas:por_unidad[r.unidad_negocio_id]+=nuevas[r.id];sectores[r.unidad_negocio_id].add(r.sector)
    if nuevas:
        actual=version_actual(e)
        filas=[dict(unidad_negocio_id=uid,porcentaje_asignacion=p,ubicacion_trabajo=', '.join(sorted(sectores[uid]))[:120],tipo_funcion=previo[uid].tipo_funcion if uid in previo else actual.tipo_funcion) for uid,p in por_unidad.items()]
        registrar_distribucion(e,filas,organizacion_id=organizacion.id,unidades_validas=modelos['UnidadNegocio'].query.filter_by(organizacion_id=organizacion.id).all(),
            Modelo=Modelo,db_session=db_session,usuario_id=usuario_id,observacion='Derivada de la asignación de áreas del legajo.',commit=False)
    else:
        for v in vigentes:v.vigente=False;v.vigente_hasta=ahora_utc_naive()
    for r in recursos:
        if r.id not in set(anteriores)|set(nuevas):continue
        db_session.expire(r,['miembros_recurso','versiones_costo'])
        if r.miembros_recurso:
            recalcular_tarifa_recurso(r,EmpleadoCostoVersion=modelos['EmpleadoCostoVersion'],db_session=db_session,usuario_id=usuario_id,commit=False)
        else:
            for v in r.versiones_costo:
                if v.vigente:v.vigente=False;v.vigente_hasta=ahora_utc_naive()

    return registro


def resumen_areas(recursos):
    filas=[]
    for r in recursos:
        v=version_actual(r);faltantes=[x.empleado.nombre for x in r.miembros_recurso if version_actual(x.empleado) is None or not x.empleado.activo]
        filas.append(dict(recurso=r,version=v,integrantes=len(r.miembros_recurso),pendiente=not r.activo or not v or not r.miembros_recurso or bool(faltantes),faltantes=faltantes))
    return filas
