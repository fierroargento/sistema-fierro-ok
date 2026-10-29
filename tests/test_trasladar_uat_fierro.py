import json
import pytest
from sqlalchemy import create_engine,text,event
from scripts.trasladar_uat_fierro import ejecutar
from services.listas_codimat import DESCUENTOS

@pytest.fixture
def base():
    e=create_engine('sqlite://')
    ddl=[
      'CREATE TABLE unidad_negocio(id INTEGER PRIMARY KEY,organizacion_id INTEGER,codigo TEXT,activa BOOLEAN)',
      'CREATE TABLE insumo_productivo(id INTEGER PRIMARY KEY,organizacion_id INTEGER,unidad_negocio_id INTEGER,codigo TEXT,nombre TEXT,activo BOOLEAN)',
      'CREATE TABLE producto(id INTEGER PRIMARY KEY,organizacion_id INTEGER,sku TEXT)',
      'CREATE TABLE producto_ficha_maestra(producto_id INTEGER PRIMARY KEY,organizacion_id INTEGER,linea TEXT)',
      'CREATE TABLE perfil_costeo_producto(id INTEGER PRIMARY KEY,organizacion_id INTEGER,unidad_negocio_id INTEGER,producto_id INTEGER,tipo TEXT)',
      'CREATE TABLE costo_producto_version(id INTEGER PRIMARY KEY,organizacion_id INTEGER,unidad_negocio_id INTEGER,producto_id INTEGER,vigente BOOLEAN,estado TEXT)',
      'CREATE TABLE producto_insumo_costeo(id INTEGER PRIMARY KEY,perfil_costeo_id INTEGER,insumo_id INTEGER,cantidad INTEGER,porcentaje_merma INTEGER,observacion TEXT)',
      'CREATE TABLE producto_operacion_costeo(id INTEGER PRIMARY KEY,perfil_costeo_id INTEGER,empleado_id INTEGER,nombre TEXT,minutos INTEGER,orden INTEGER,observacion TEXT)',
      'CREATE TABLE producto_maquina_costeo(id INTEGER PRIMARY KEY,perfil_costeo_id INTEGER,maquina_id INTEGER)',
      'CREATE TABLE producto_costo_fijo_costeo(id INTEGER PRIMARY KEY,perfil_costeo_id INTEGER,costo_fijo_id INTEGER)',
      'CREATE TABLE combo_producto_componente(id INTEGER PRIMARY KEY,combo_perfil_id INTEGER,componente_perfil_id INTEGER)',
      'CREATE TABLE producto_despiece_costeo(perfil_costeo_id INTEGER PRIMARY KEY,contenido TEXT,revision INTEGER,huella_composicion TEXT)',
      'CREATE TABLE proveedor_compra(id INTEGER PRIMARY KEY,organizacion_id INTEGER,codigo TEXT,razon_social TEXT)',
      'CREATE TABLE proveedor_unidad(id INTEGER PRIMARY KEY,organizacion_id INTEGER,unidad_negocio_id INTEGER,proveedor_id INTEGER,estado TEXT)',
      'CREATE TABLE material_proveedor_compra(id INTEGER PRIMARY KEY,organizacion_id INTEGER,unidad_negocio_id INTEGER,proveedor_id INTEGER,insumo_id INTEGER,codigo TEXT,codigo_clave TEXT,UNIQUE(proveedor_id,unidad_negocio_id,codigo_clave),UNIQUE(proveedor_id,unidad_negocio_id,insumo_id))'
    ]
    for recurso in ['empleado_productivo','maquina_productiva','costo_fijo_productivo']:
        ddl.append(f'CREATE TABLE {recurso}(id INTEGER PRIMARY KEY,organizacion_id INTEGER,unidad_negocio_id INTEGER,codigo TEXT,nombre TEXT,activo BOOLEAN)')
    codigos=tuple('1985' if c=='3951' else c for c in DESCUENTOS)
    with e.begin() as c:
        for sql in ddl:c.execute(text(sql))
        c.execute(text("INSERT INTO unidad_negocio VALUES (3,1,'ensayo-uat',1),(1,1,'fierro-100-argento',1),(4,2,'ajeno',1)"))
        c.execute(text("INSERT INTO insumo_productivo VALUES(1,1,3,'uat-ins-001','Sintético',1)"))
        for ident,codigo in enumerate(codigos,2):c.execute(text('INSERT INTO insumo_productivo VALUES(:id,1,3,:codigo,:codigo,1)'),dict(id=ident,codigo=codigo))
        c.execute(text("INSERT INTO producto(id,organizacion_id,sku) VALUES(1,1,'UAT-001'),(5,1,'REAL')"))
        c.execute(text("INSERT INTO producto_ficha_maestra VALUES(1,1,'UAT'),(5,1,'HERRERIA')"))
        c.execute(text("INSERT INTO perfil_costeo_producto VALUES(1,1,3,1,'produccion'),(5,1,3,5,'produccion')"))
        c.execute(text("INSERT INTO costo_producto_version VALUES(1,1,3,1,1,'vigente'),(5,1,3,5,0,'preparatorio')"))
        c.execute(text('INSERT INTO producto_insumo_costeo VALUES(1,5,2,6,0,NULL)'))
        c.execute(text("INSERT INTO producto_operacion_costeo VALUES(1,5,1,'Cortar',10,0,NULL)"))
        c.execute(text('INSERT INTO producto_maquina_costeo VALUES(1,5,1)'))
        c.execute(text('INSERT INTO producto_despiece_costeo VALUES(5,:datos,1,:huella)'),dict(datos=json.dumps({'piezas':[{'insumo_id':2,'cantidad':'6'}],'tareas':[{'nombre':'Cortar','segundos':'600'}],'tarifa_id':1}),huella='anterior'))
        for recurso in ['empleado_productivo','maquina_productiva','costo_fijo_productivo']:
            c.execute(text(f"INSERT INTO {recurso} VALUES(1,1,3,'UAT','Sintético',1),(2,1,1,'REAL','Real',1)"))
        c.execute(text("INSERT INTO proveedor_compra VALUES(2,1,'PROV-001','CODIMAT S.A.')"))
        c.execute(text("INSERT INTO proveedor_unidad VALUES(1,1,1,2,'activo')"))
    yield e,codigos
    e.dispose()


def correr(base,**kw):
    e,codigos=base
    return ejecutar(e,3,1,skus=('REAL',),codigos=codigos,**kw)

MAPA={'empleado_productivo':{'1':2},'maquina_productiva':{'1':2}}


def test_simulacion_no_escribe_y_enumera_bloqueos(base):
    e,_=base;escrituras=[]
    def registrar(c,cursor,s,p,ctx,many):
        if s.lstrip().upper().startswith(('UPDATE','DELETE','INSERT')):escrituras.append(s)
    event.listen(e,'before_cursor_execute',registrar)
    r=correr(base)
    assert not r['aplicado'] and len(r['dependencias'])==2 and r['bloqueos']
    assert r['disponibles']['proveedores_codimat'][0]['id']==2
    assert escrituras==[]


def test_aplicar_bloqueado_no_mueve_nada(base):
    r=correr(base,aplicar=True,bases_separadas=True,proveedor=2)
    assert not r['aplicado'] and len(r['bloqueos'])==2
    with base[0].connect() as c:assert c.execute(text('SELECT unidad_negocio_id FROM insumo_productivo WHERE id=2')).scalar_one()==3
    with pytest.raises(ValueError,match='separadas'):correr(base,aplicar=True,mapa=MAPA,proveedor=2)


def test_traslado_preserva_identidades_tiempos_y_pruebas(base):
    r=correr(base,aplicar=True,bases_separadas=True,mapa=MAPA,proveedor=2)
    assert r['aplicado'] and not r['bloqueos'] and r['cantidades']['vinculos_codimat']==13
    with base[0].connect() as c:
        assert c.execute(text('SELECT unidad_negocio_id FROM insumo_productivo WHERE id=2')).scalar_one()==1
        assert c.execute(text('SELECT unidad_negocio_id FROM insumo_productivo WHERE id=1')).scalar_one()==3
        assert c.execute(text('SELECT unidad_negocio_id FROM perfil_costeo_producto WHERE id=5')).scalar_one()==1
        assert c.execute(text('SELECT unidad_negocio_id FROM perfil_costeo_producto WHERE id=1')).scalar_one()==3
        assert tuple(c.execute(text('SELECT empleado_id,minutos FROM producto_operacion_costeo')).one())==(2,10)
        assert c.execute(text('SELECT maquina_id FROM producto_maquina_costeo')).scalar_one()==2
        assert tuple(c.execute(text('SELECT unidad_negocio_id,vigente,estado FROM costo_producto_version WHERE id=5')).one())==(1,0,'preparatorio')
        d=c.execute(text('SELECT contenido,revision,huella_composicion FROM producto_despiece_costeo')).one()
        assert json.loads(d[0])['tarifa_id']==2 and json.loads(d[0])['piezas'][0]['cantidad']=='6' and d[1]==2 and d[2]!='anterior'
        assert c.execute(text("SELECT i.codigo FROM material_proveedor_compra l JOIN insumo_productivo i ON i.id=l.insumo_id WHERE l.codigo='3951'")).scalar_one()=='1985'
        assert c.execute(text('SELECT activa FROM unidad_negocio WHERE id=3')).scalar_one()==1
    otra=correr(base,aplicar=True,bases_separadas=True,mapa=MAPA,proveedor=2)
    assert otra['aplicado'] and otra['cantidades']['perfiles']==otra['cantidades']['vinculos_codimat']==0


def test_conflictos_y_recursos_ajenos_bloquean(base):
    e,_=base
    with e.begin() as c:c.execute(text('UPDATE maquina_productiva SET unidad_negocio_id=4 WHERE id=2'))
    r=correr(base,mapa=MAPA,proveedor=2)
    assert any('maquina_productiva' in b for b in r['bloqueos'])
    with e.begin() as c:c.execute(text("INSERT INTO perfil_costeo_producto VALUES(6,1,1,5,'produccion')"))
    assert any('perfiles' in b for b in correr(base,mapa=MAPA,proveedor=2)['bloqueos'])


def test_fallo_final_revierte_todo(base):
    from sqlalchemy import event
    e,_=base
    def fallar(c,cursor,s,p,ctx,many):
        if s.startswith('INSERT INTO material_proveedor_compra'):raise RuntimeError('Fallo final simulado')
    event.listen(e,'before_cursor_execute',fallar)
    with pytest.raises(RuntimeError):correr(base,aplicar=True,bases_separadas=True,mapa=MAPA,proveedor=2)
    event.remove(e,'before_cursor_execute',fallar)
    with e.connect() as c:
        assert c.execute(text('SELECT unidad_negocio_id FROM insumo_productivo WHERE id=2')).scalar_one()==3
        assert c.execute(text('SELECT empleado_id FROM producto_operacion_costeo')).scalar_one()==1
        assert c.execute(text('SELECT revision FROM producto_despiece_costeo')).scalar_one()==1


def test_codigo_anterior_actualiza_vinculo_sin_recrearlo(base):
    e,_=base
    with e.begin() as c:
        ident=c.execute(text("SELECT id FROM insumo_productivo WHERE codigo='1985'")).scalar_one()
        c.execute(text("INSERT INTO material_proveedor_compra VALUES(50,1,1,2,:i,'1985','1985')"),dict(i=ident))
    r=correr(base,aplicar=True,bases_separadas=True,mapa=MAPA,proveedor=2)
    assert r['aplicado'] and r['cantidades']['codigos_a_actualizar']==1
    with e.connect() as c:assert c.execute(text('SELECT codigo FROM material_proveedor_compra WHERE id=50')).scalar_one()=='3951'


def test_identidades_faltantes_y_costos_vigentes_no_se_presumen(base):
    e,_=base
    with e.begin() as c:c.execute(text("UPDATE costo_producto_version SET vigente=1,estado='vigente' WHERE id=5"))
    assert any('vigentes' in b for b in correr(base,mapa=MAPA,proveedor=2)['bloqueos'])
    with e.begin() as c:c.execute(text("UPDATE producto SET sku='OTRO' WHERE id=5"))
    assert any('identidades' in b for b in correr(base,mapa=MAPA,proveedor=2)['bloqueos'])


def test_cli_exige_staging_antes_de_conectar():
    import os,subprocess,sys
    env=os.environ|{'MODO_LABORATORIO_DESCONECTADO':'true','RENDER_GIT_BRANCH':'main','RENDER_EXTERNAL_URL':'https://staging.example','DATABASE_URL':'postgresql://invalid'}
    r=subprocess.run([sys.executable,'-m','scripts.trasladar_uat_fierro','--staging','--origen','3','--destino','1'],env=env,capture_output=True,text=True)
    assert r.returncode!=0 and 'Se requiere staging' in r.stderr


def test_un_recurso_de_ensayo_se_reasigna_por_linea_de_producto(base):
    e,codigos=base
    with e.begin() as c:
        c.execute(text("UPDATE producto_ficha_maestra SET linea='HERRERIA' WHERE producto_id=5"))
        c.execute(text("INSERT INTO producto VALUES(6,1,'REAL2')"))
        c.execute(text("INSERT INTO producto_ficha_maestra VALUES(6,1,'LASER')"))
        c.execute(text("INSERT INTO perfil_costeo_producto VALUES(6,1,3,6,'produccion')"))
        c.execute(text("INSERT INTO producto_operacion_costeo VALUES(2,6,1,'Grabar',5,0,NULL)"))
        c.execute(text("INSERT INTO empleado_productivo VALUES(3,1,1,'LASER','Área láser real',1)"))
    mapa={'maquina_productiva':{'1':2},'por_linea':{'HERRERIA':{'empleado_productivo':{'1':2}},'LASER':{'empleado_productivo':{'1':3}}}}
    r=ejecutar(e,3,1,aplicar=True,bases_separadas=True,mapa=mapa,proveedor=2,skus=('REAL','REAL2'),codigos=codigos)
    assert r['aplicado']
    with e.connect() as c:assert list(c.execute(text('SELECT perfil_costeo_id,empleado_id FROM producto_operacion_costeo ORDER BY id')))==[(5,2),(6,3)]


def test_linea_sale_de_ficha_maestra_y_no_del_producto_logistico(base):
    r=correr(base,proveedor=2)
    assert {d['linea_producto'] for d in r['dependencias']}=={'HERRERIA'}
    with base[0].begin() as c:c.execute(text("UPDATE producto_ficha_maestra SET linea='' WHERE producto_id=5"))
    r=correr(base,mapa=MAPA,proveedor=2)
    assert any('sin línea' in b for b in r['bloqueos']) and not r['aplicado']
