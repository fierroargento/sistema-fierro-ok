"""Cruce interno con persistencia real SQLite, sin app ni canales."""

import json
from types import SimpleNamespace as Obj

import pytest
from sqlalchemy import Boolean, Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from services.materias_primas_inventario import preparar_materia_prima, validar_existencia_insumo
from services.destino_produccion import guardar_destino, leer_destino
from services.propuestas_inventario_produccion import preparar_propuesta_inventario
from services.inventario_saas import preparar_items_catalogo
from tests.test_propuestas_inventario_produccion import orden as orden_fixture, datos


@pytest.fixture
def persistencia():
    Base = declarative_base()
    class Insumo(Base):
        __tablename__ = "insumo"
        id = Column(Integer, primary_key=True)
        organizacion_id = Column(Integer)
        unidad_negocio_id = Column(Integer)
        nombre = Column(String)
        tipo = Column(String)
        activo = Column(Boolean)
        unidad_medida = Column(String)
    class Producto(Base):
        __tablename__ = "producto"
        id = Column(Integer, primary_key=True)
        organizacion_id = Column(Integer)
        sku = Column(String, unique=True)
        descripcion = Column(String)
        permite_correo = Column(Boolean)
        permite_via_cargo = Column(Boolean)
        requiere_revision_logistica = Column(Boolean)
    class Item(Base):
        __tablename__ = "item"
        id = Column(Integer, primary_key=True)
        organizacion_id = Column(Integer)
        producto_id = Column(Integer)
        catalogo_producto_id = Column(Integer)
        sku = Column(String, unique=True)
        nombre = Column(String)
        tipo = Column(String)
        activo = Column(Boolean)
        atributos_json = Column(String)
    class Orden(Base):
        __tablename__ = "orden"
        id = Column(Integer, primary_key=True)
        organizacion_id = Column(Integer)
        unidad_negocio_id = Column(Integer)
        producto_id = Column(Integer)
        estado = Column(String)
    class Configuracion(Base):
        __tablename__ = "configuracion"
        id = Column(Integer, primary_key=True)
        clave = Column(String, unique=True)
        valor = Column(String)
        descripcion = Column(String)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    for model in (Insumo, Producto, Item, Orden, Configuracion):
        model.query = session.query(model)
    insumo = Insumo(id=3, organizacion_id=7, unidad_negocio_id=9, nombre="Chapa",
                    tipo="materia_prima", activo=True, unidad_medida="kg")
    orden = Orden(id=1, organizacion_id=7, unidad_negocio_id=9, producto_id=30, estado="aprobada")
    session.add_all([insumo, orden]); session.commit()
    yield Obj(session=session, insumo=insumo, orden=orden, Producto=Producto, Item=Item, Configuracion=Configuracion)
    session.close(); engine.dispose()


def preparar(db, sku="UAT-MP-001", **contexto):
    return preparar_materia_prima(insumo=db.insumo, sku=sku,
        organizacion_id=contexto.get("org", 7), unidad_negocio_id=contexto.get("unidad", 9),
        Producto=db.Producto, ItemInventario=db.Item, db_session=db.session)


def test_prepara_una_sola_identidad_inactiva_sin_catalogo(persistencia):
    db = persistencia
    item, creado = preparar(db)
    assert creado and not item.activo and item.tipo == "insumo"
    assert item.catalogo_producto_id is None
    assert json.loads(item.atributos_json) == {"insumo_productivo_id": 3, "unidad_medida": "kg", "factor_inventario": 1, "precision_inventario": "unidad", "unidad_inventario": "kg", "version_unidad": 1}
    producto = db.Producto.query.one()
    assert not producto.permite_correo and not producto.permite_via_cargo
    assert preparar(db)[1] is False
    assert db.Producto.query.count() == db.Item.query.count() == 1
    with pytest.raises(ValueError, match="ya tiene"):
        preparar(db, "OTRO")


@pytest.mark.parametrize("contexto", [{"org": 8}, {"unidad": 10}])
def test_preparacion_rechaza_contextos_ajenos(persistencia, contexto):
    with pytest.raises(ValueError): preparar(persistencia, **contexto)
    assert persistencia.Producto.query.count() == persistencia.Item.query.count() == 0


def test_rechaza_colision_producto_servicio_e_insumo_inactivo(persistencia):
    db = persistencia
    db.session.add(db.Producto(organizacion_id=7, sku="EXISTENTE", descripcion="Terminado"))
    db.session.commit()
    with pytest.raises(ValueError, match="maestro"): preparar(db, "EXISTENTE")
    for campo, valor in [("tipo", "servicio_productivo"), ("activo", False)]:
        anterior = getattr(db.insumo, campo); setattr(db.insumo, campo, valor)
        with pytest.raises(ValueError, match="físico activo"): preparar(db)
        setattr(db.insumo, campo, anterior)
    assert db.Item.query.count() == 0


def existencia(id=12, producto_id=30):
    return Obj(id=id, organizacion_id=7, producto_id=producto_id, control_activo=True,
               stock_actual=5, stock_reservado=0,
               item_inventario=Obj(organizacion_id=7, producto_id=producto_id, activo=True, tipo="producto"),
               sucursal=Obj(organizacion_id=7, activa=True))


def test_mapeo_rechaza_producto_terminado_y_solo_acepta_insumo_correcto(persistencia):
    db = persistencia; e = existencia()
    with pytest.raises(ValueError, match="SKU preparado"):
        validar_existencia_insumo(db.insumo, e, 7, 9)
    item, _ = preparar(db); item.activo=True; db.session.commit()
    e.item_inventario=item; e.producto_id=item.producto_id
    validar_existencia_insumo(db.insumo, e, 7, 9)
    e.control_activo=False
    with pytest.raises(ValueError, match="Activá"):
        validar_existencia_insumo(db.insumo, e, 7, 9)
    assert e.stock_actual == 5


def test_actualizar_catalogo_no_reclasifica_materia_prima(persistencia):
    db = persistencia; item, _ = preparar(db)
    original = item.atributos_json
    inclusion = Obj(id=8, catalogo=Obj(organizacion_id=7), producto_id=30,
                    sku_comercial=item.sku, nombre_comercial="Terminado", variantes_json="[]")
    with pytest.raises(ValueError, match="reservado"):
        preparar_items_catalogo(7, [inclusion], ItemInventario=db.Item, db_session=db.session)
    assert item.tipo == "insumo" and item.atributos_json == original
    assert item.catalogo_producto_id is None and not item.activo


def test_destino_se_guarda_por_contexto_y_no_modifica_stock(persistencia):
    db = persistencia; e = existencia()
    guardar_destino(orden=db.orden, existencia=e, organizacion_id=7, unidad_negocio_id=9,
                    ConfiguracionSistema=db.Configuracion, db_session=db.session)
    db.session.expire_all()
    assert leer_destino(orden=db.orden, organizacion_id=7, unidad_negocio_id=9,
                       ConfiguracionSistema=db.Configuracion) == 12
    assert leer_destino(orden=db.orden, organizacion_id=7, unidad_negocio_id=10,
                       ConfiguracionSistema=db.Configuracion) is None
    assert e.stock_actual == 5 and db.Configuracion.query.count() == 1
    e.id=13
    guardar_destino(orden=db.orden, existencia=e, organizacion_id=7, unidad_negocio_id=9,
                    ConfiguracionSistema=db.Configuracion, db_session=db.session)
    assert db.Configuracion.query.one().valor == "13"


@pytest.mark.parametrize("cambio", ["otra_org", "otro_producto", "inactivo", "otra_unidad", "cerrada"])
def test_destino_invalido_no_persiste(persistencia, cambio):
    db = persistencia; e = existencia(); unidad=9
    if cambio == "otra_org": e.organizacion_id=8
    if cambio == "otro_producto": e.producto_id=40
    if cambio == "inactivo": e.sucursal.activa=False
    if cambio == "otra_unidad": unidad=10
    if cambio == "cerrada": db.orden.estado="cerrada"; db.session.commit()
    with pytest.raises(ValueError):
        guardar_destino(orden=db.orden, existencia=e, organizacion_id=7, unidad_negocio_id=unidad,
                        ConfiguracionSistema=db.Configuracion, db_session=db.session)
    assert db.Configuracion.query.count() == 0 and e.stock_actual == 5


def test_propuesta_resuelve_dos_destinos_y_bloquea_seleccion_invalida():
    mapeos, _ = datos(); destinos=[existencia(12), existencia(13)]
    def propuesta(seleccion):
        return preparar_propuesta_inventario(orden_fixture(), organizacion_id=7,
            unidad_negocio_id=9, mapeos_insumo=mapeos, existencias_producto=destinos,
            destino_existencia_id=seleccion)
    assert not propuesta(None)["aprobada"]
    valido = propuesta(13)
    assert valido["aprobada"] and valido["movimientos_propuestos"][-1]["existencia_sucursal_id"] == 13
    assert not valido["controles"]["stock_modificado"]
    assert not propuesta(99)["aprobada"]
    destinos[1].sucursal.activa=False
    assert not propuesta(13)["aprobada"]


def test_precision_se_persiste_y_no_se_puede_reinterpretar(persistencia):
    db=persistencia
    def crear(precision):
        return preparar_materia_prima(insumo=db.insumo,sku='UAT-MP-FRACCION',
            organizacion_id=7,unidad_negocio_id=9,Producto=db.Producto,
            ItemInventario=db.Item,db_session=db.session,precision_inventario=precision)
    item,creado=crear('milesimas');anterior=item.atributos_json;db.session.expire_all()
    assert creado and json.loads(db.Item.query.one().atributos_json)['unidad_inventario']=='g'
    assert crear('milesimas')[1] is False
    with pytest.raises(ValueError,match='conserva su unidad'):crear('millonesimas')
    assert db.Item.query.one().atributos_json==anterior
    assert db.Item.query.count()==db.Producto.query.count()==1
    assert not item.activo


def test_precision_invalida_no_crea_identidades(persistencia):
    db=persistencia
    with pytest.raises(ValueError):
        preparar_materia_prima(insumo=db.insumo,sku='UAT',organizacion_id=7,unidad_negocio_id=9,
            Producto=db.Producto,ItemInventario=db.Item,db_session=db.session,precision_inventario='libre')
    assert db.Item.query.count()==db.Producto.query.count()==0
