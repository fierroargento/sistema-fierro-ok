"""Recorrido APB: gestión del legajo conserva secciones y contexto modal."""
from test_personal_admin import personal,nuevo,editar
from test_producto_ficha_maestra import entorno

def test_gestion_empleado_y_secciones(personal):
    c,*_=personal;e=nuevo(personal)
    for s in ['sueldos','areas','vacaciones','novedades','competencias']:
        r=c.get(f'/admin/personal/{e.id}?seccion={s}&gestionar=1')
        assert r.status_code==200
        assert 'id="personal-gestion"' in r.text
        assert 'data-personal-seccion="areas"' in r.text
        assert 'data-personal-seccion="accesos"' in r.text
        assert 'personal_gestion.js' in r.text
    r=c.get(f'/admin/personal/{e.id}/horarios?modo=editar&gestionar=1')
    assert r.status_code==200 and 'id="personal-gestion"' in r.text and 'id="semana-form"' in r.text
    r=c.get('/admin/personal/mano-obra')
    assert r.status_code==200 and 'Configurar unidades' not in r.text
    r=c.post('/admin/personal',data=editar(e,volver_ficha=str(e.id)))
    assert 'editar=1' in r.location
    assert c.get(r.location).status_code==200
    from services.personal_areas import huella_asignacion
    r=c.post(f'/admin/personal/{e.id}?gestionar=1',data={'_csrf_token':'csrf-personal','seccion':'areas','accion':'guardar_areas_personal','huella_areas':huella_asignacion(e),'tareas_habituales':'Prueba de gestión'})
    assert r.status_code==302 and 'gestionar=1' in r.location
    assert 'id="personal-gestion"' in c.get(r.location).text
