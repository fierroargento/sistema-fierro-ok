"""La auditoría enumera relaciones por unidad y no modifica datos."""
import json
import os
import subprocess
import sys
import pytest
from sqlalchemy import create_engine,text
from scripts.auditar_traslado_unidad import auditar


def test_auditoria_cuenta_todas_las_unidades_sin_escrituras():
    engine=create_engine('sqlite://')
    with engine.begin() as c:
        c.execute(text('CREATE TABLE unidad_negocio (id INTEGER PRIMARY KEY, organizacion_id INTEGER, codigo TEXT, nombre TEXT, activa BOOLEAN)'))
        c.execute(text("INSERT INTO unidad_negocio VALUES (1,1,'UAT','Ensayo UAT',1),(2,1,'FIERRO','Fierro',1),(3,1,'NAUTICA','Náutica',1)"))
        c.execute(text('CREATE TABLE materiales (id INTEGER PRIMARY KEY, unidad_negocio_id INTEGER REFERENCES unidad_negocio(id), codigo TEXT, UNIQUE(unidad_negocio_id,codigo))'))
        c.execute(text("INSERT INTO materiales VALUES (1,1,'1955'),(2,2,'1955'),(3,1,'PRUEBA')"))
        c.execute(text('CREATE TABLE sucursales (id INTEGER PRIMARY KEY, unidad_responsable INTEGER REFERENCES unidad_negocio(id))'))
        c.execute(text('INSERT INTO sucursales VALUES (1,1)'))
    r=auditar(engine)
    assert r['solo_lectura'] is True and len(r['unidades'])==3
    assert r['referencias'][0]['por_unidad']==[{'unidad_id':1,'cantidad':2},{'unidad_id':2,'cantidad':1}]
    assert r['referencias'][1]['columna']=='unidad_responsable'
    with engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM materiales')).scalar_one()==3
        assert c.execute(text('SELECT activa FROM unidad_negocio WHERE id=1')).scalar_one()==1
        with pytest.raises(Exception):c.execute(text('UPDATE unidad_negocio SET activa=0'))
    assert 'password' not in json.dumps(r)


def test_cli_rechaza_servicio_o_rama_ajena():
    env=os.environ|{'MODO_LABORATORIO_DESCONECTADO':'true','RENDER_GIT_BRANCH':'main','RENDER_EXTERNAL_URL':'https://staging.example','DATABASE_URL':'sqlite://'}
    p=subprocess.run([sys.executable,'-m','scripts.auditar_traslado_unidad','--staging'],env=env,capture_output=True,text=True)
    assert p.returncode!=0 and 'integración' in p.stderr
    env['RENDER_GIT_BRANCH']='integracion-saas-2026-09';env['RENDER_EXTERNAL_URL']='https://produccion.example'
    p=subprocess.run([sys.executable,'-m','scripts.auditar_traslado_unidad','--staging'],env=env,capture_output=True,text=True)
    assert p.returncode!=0 and 'staging' in p.stderr
