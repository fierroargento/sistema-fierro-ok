"""Mano de obra central: asignación por unidad/área y costos sin duplicar nómina."""
from decimal import Decimal
from pathlib import Path
import pytest
from extensions import db
from models.fuentes_costo_productivo import EmpleadoProductivo,EmpleadoCostoVersion,EmpleadoDistribucionVersion,RecursoEmpleadoProductivo
from services.personal_areas import huella_asignacion
from test_personal_admin import personal,entorno,nuevo
from test_personal_actualizacion_costos import sueldo


def preparar(personal):
    c,org,otra,base,m,*_=personal
    U=m['UnidadNegocio'];nautica=U(organizacion_id=org.id,codigo='nautica',nombre='Náutica',activa=True);taller=U(organizacion_id=org.id,codigo='taller',nombre='Taller Fierro',activa=True)
    ajena=U(organizacion_id=otra.id,codigo='ajena',nombre='Ajena');db.session.add_all([nautica,taller,ajena]);db.session.commit()
    areas=[]
    for codigo,nombre,u in [('naut','Náutica',nautica),('herr','Taller Herrería',taller),('laser','Taller Láser',taller)]:
        with c.session_transaction() as ses:ses['unidad_negocio_id']=u.id
        c.environ_base['HTTP_X_FIERRO_UNIDAD']=str(u.id)
        r=c.post('/admin/personal/mano-obra',data=dict(_csrf_token='csrf-personal',accion='crear_area',area_unidad_id=str(u.id),codigo=codigo,nombre=nombre,sector=nombre))
        assert r.status_code==302,r.text
        areas.append(EmpleadoProductivo.query.filter_by(codigo=codigo).one())
    with c.session_transaction() as ses:ses['unidad_negocio_id']=base.id
    c.environ_base['HTTP_X_FIERRO_UNIDAD']=str(base.id)
    return areas,ajena


def asignar(c,e,porcentajes,**kw):
    # El escenario compartido declara los vínculos que antes eran implícitos.
    from models.personal_unidad import PersonalUnidad
    for r,_ in porcentajes:
        if r.organizacion_id==e.organizacion_id and not PersonalUnidad.query.filter_by(empleado_id=e.id,unidad_negocio_id=r.unidad_negocio_id).first():
            db.session.add(PersonalUnidad(organizacion_id=e.organizacion_id,empleado_id=e.id,unidad_negocio_id=r.unidad_negocio_id))
    db.session.commit()
    f=dict(_csrf_token='csrf-personal',seccion='areas',accion='guardar_areas_personal',huella_areas=huella_asignacion(e),tareas_habituales='Coordinar tareas')
    f.update({f'area_porcentaje_{r.id}':str(p) for r,p in porcentajes});f.update(kw)
    r=c.post(f'/admin/personal/{e.id}',data=f)
    if r.status_code==302 and porcentajes:
        unidad=porcentajes[0][0].unidad_negocio_id
        with c.session_transaction() as ses:ses['unidad_negocio_id']=unidad
        c.environ_base['HTTP_X_FIERRO_UNIDAD']=str(unidad)
    return r


def test_asignacion_dos_unidades_tres_areas_calcula_costo_y_proyeccion_sin_doble_conteo(personal):
    c,*_=personal;areas,_=preparar(personal);e=nuevo(personal);sueldo(e)
    r=asignar(c,e,[(areas[0],20),(areas[1],30),(areas[2],50)])
    assert r.status_code==302,r.text
    db.session.expire_all();assert e.observacion=='Coordinar tareas' and len(e.participaciones_recurso)==3 and e.unidad_negocio_id is None
    distrib=EmpleadoDistribucionVersion.query.filter_by(empleado_id=e.id,vigente=True).all()
    assert sorted(x.porcentaje_asignacion for x in distrib)==[20,80]
    versiones=EmpleadoCostoVersion.query.filter(EmpleadoCostoVersion.empleado_id.in_([r.id for r in areas]),EmpleadoCostoVersion.vigente.is_(True)).all()
    assert len(versiones)==3 and abs(sum(v.costo_mensual_total_centavos for v in versiones)-112345)<=1 # redondeo de cada tarifa a centavos
    assert sum(v.horas_productivas for v in versiones)==160 # toda la jornada existente se computa para costo
    assert {v.empleado_id for v in versiones}=={r.id for r in areas}
    assert c.get('/admin/personal/mano-obra').status_code==200
    html=c.get('/admin/personal').text.split('<thead>')[1].split('</table>')[0]
    assert '<th>Nombre y apellido</th>' in html and '<th>Unidad</th>' in html
    assert 'Sueldo' not in html and 'Sector / Puesto' not in html and '1123' not in html
    assert 'Náutica / Taller Fierro' in html


def test_reasignar_actualiza_todas_las_tarifas_y_archiva_la_vacia(personal):
    c,*_=personal;areas,_=preparar(personal);e=nuevo(personal);sueldo(e)
    assert asignar(c,e,[(areas[1],100)]).status_code==302
    viejo=EmpleadoCostoVersion.query.filter_by(empleado_id=areas[1].id,vigente=True).one();anterior_id=viejo.id
    assert asignar(c,e,[(areas[2],100)]).status_code==302
    db.session.expire_all();assert not db.session.get(EmpleadoCostoVersion,anterior_id).vigente
    assert e.unidad_negocio_id==areas[2].unidad_negocio_id
    assert RecursoEmpleadoProductivo.query.filter_by(empleado_id=e.id).count()==1
    antes=EmpleadoCostoVersion.query.count();revision=EmpleadoDistribucionVersion.query.count()
    assert asignar(c,e,[(areas[2],100)],tareas_habituales='Cortar piezas').status_code==302
    assert EmpleadoCostoVersion.query.count()==antes and EmpleadoDistribucionVersion.query.count()==revision
    assert e.observacion=='Cortar piezas'


def test_error_de_calculo_revierte_tareas_asignaciones_y_distribucion(personal,monkeypatch):
    import services.personal_areas as servicio
    c,*_=personal;areas,_=preparar(personal);e=nuevo(personal);sueldo(e)
    assert asignar(c,e,[(areas[1],100)]).status_code==302
    antes=EmpleadoCostoVersion.query.count();revisiones=EmpleadoDistribucionVersion.query.count()
    def falla(*a,**kw):raise ValueError('Error de tarifa de prueba')
    monkeypatch.setattr(servicio,'recalcular_tarifa_recurso',falla)
    assert asignar(c,e,[(areas[2],100)],tareas_habituales='No guardar').status_code==400
    db.session.expire_all();assert e.observacion=='Coordinar tareas'
    assert RecursoEmpleadoProductivo.query.filter_by(empleado_id=e.id).one().recurso_id==areas[1].id
    assert EmpleadoCostoVersion.query.count()==antes and EmpleadoDistribucionVersion.query.count()==revisiones


def test_porcentajes_contexto_concurrencia_y_csrf(personal):
    c,org,otra,u,m,mem=personal;areas,ajena=preparar(personal);e=nuevo(personal);sueldo(e)
    assert asignar(c,e,[(areas[1],60)]).status_code==400
    assert asignar(c,e,[(areas[1],60),(areas[2],60)]).status_code==400
    assert asignar(c,e,[],area_porcentaje_999999='100').status_code==400
    assert asignar(c,e,[(areas[1],100)],_csrf_token='otra').status_code==400
    huella=huella_asignacion(e);assert asignar(c,e,[(areas[1],100)]).status_code==302
    assert asignar(c,e,[(areas[2],100)],huella_areas=huella).status_code==400
    r=c.post('/admin/personal/mano-obra',data=dict(_csrf_token='csrf-personal',accion='crear_area',area_unidad_id=ajena.id,codigo='fuera',nombre='Ajena',sector='Ajena'))
    assert r.status_code==400
    mem.rol='carga';assert c.get('/admin/personal/mano-obra').status_code==302
    assert asignar(c,e,[(areas[2],100)]).status_code==302
    assert RecursoEmpleadoProductivo.query.filter_by(empleado_id=e.id).one().recurso_id==areas[1].id


def test_sin_sueldo_no_inventa_tarifa_y_sin_asignaciones_es_pendiente(personal):
    c,*_=personal;areas,_=preparar(personal);e=nuevo(personal)
    assert asignar(c,e,[(areas[1],100)]).status_code==400
    html=c.get('/admin/personal/mano-obra').text
    assert 'pendientes' in html.lower() and e.nombre in html
    assert f'area={areas[1].id}' not in html  # no abrir áreas de unidades ajenas a la activa
    assert RecursoEmpleadoProductivo.query.count()==0


def test_fuentes_de_costo_solo_enlaza_a_personal_sin_otro_formulario():
    plantilla=Path('templates/admin_fuentes_costos.html').read_text()
    assert "url_for('admin_personal.mano_obra')" in plantilla
    assert 'name="integrante_seleccionado"' not in plantilla
    assert 'name="accion" value="crear_recurso_productivo"' not in plantilla


def test_datos_del_area_se_gestionan_en_personal_con_concurrencia_y_contexto(personal):
    from services.personal_areas import huella_area
    c,*_=personal;areas,_=preparar(personal);r=areas[1]
    with c.session_transaction() as ses:ses['unidad_negocio_id']=r.unidad_negocio_id
    c.environ_base['HTTP_X_FIERRO_UNIDAD']=str(r.unidad_negocio_id)
    vista=c.get(f'/admin/personal/mano-obra?area={r.id}')
    assert vista.status_code==200 and 'Gestionar área' in vista.text
    f=dict(_csrf_token='csrf-personal',accion='editar_area',registro_area=str(r.id),huella_area=huella_area(r),nombre='Herrería',sector='Taller Herrería')
    assert c.post('/admin/personal/mano-obra',data=f).status_code==302
    assert r.nombre=='Herrería'
    assert c.post('/admin/personal/mano-obra',data=f|{'nombre':'Viejo'}).status_code==400
    assert r.nombre=='Herrería'
    assert c.get('/admin/personal/mano-obra?area=99999').status_code==404


def test_exportacion_refleja_areas_y_repartos_reales(personal):
    from test_personal_exportacion import libro
    c,*_=personal;areas,_=preparar(personal);e=nuevo(personal);sueldo(e)
    assert asignar(c,e,[(areas[1],40),(areas[2],60)]).status_code==302
    with c.session_transaction() as ses:ses['unidad_negocio_id']=areas[1].unidad_negocio_id
    wb,_=libro(c)
    assert wb['Áreas mano de obra'].max_row==3 and wb['Equipos'].max_row==3
    assert wb['Distribución de costos'].max_row==2
    assert list(wb['Personal'].values)[1][3]=='Taller Fierro'
    wb.close()
