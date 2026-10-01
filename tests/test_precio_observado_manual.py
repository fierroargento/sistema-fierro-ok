from datetime import datetime
from types import SimpleNamespace

import pytest
from services.precio_observado_manual import registrar_precio_manual


class Campo:
    def __init__(self, nombre): self.nombre = nombre
    def __eq__(self, valor): return lambda row: getattr(row, self.nombre) == valor
    def ilike(self, valor): return lambda row: getattr(row, self.nombre).upper() == valor.upper()
    def desc(self): return self.nombre


class Query:
    def __init__(self, rows): self.rows = rows
    def filter_by(self, **datos): return Query([r for r in self.rows if all(getattr(r, k) == v for k, v in datos.items())])
    def filter(self, *criterios): return Query([r for r in self.rows if all(c(r) for c in criterios)])
    def order_by(self, *campos): return Query(sorted(self.rows, key=lambda r: tuple(getattr(r, c) for c in campos), reverse=True))
    def first(self): return self.rows[0] if self.rows else None
    def all(self): return self.rows[:]
    def one(self): assert len(self.rows) == 1; return self.rows[0]
    def count(self): return len(self.rows)


@pytest.fixture
def entorno():
    def modelo(**campos):
        return type("Modelo", (SimpleNamespace,), campos)
    Lista, Catalogo = modelo(), modelo()
    Inclusion = modelo(catalogo_id=Campo("catalogo_id"), sku_comercial=Campo("sku_comercial"))
    Obs = modelo(fecha_observacion=Campo("fecha_observacion"), id=Campo("id"))
    Lista.query = Query([Lista(id=1, organizacion_id=1, unidad_negocio_id=3, codigo="uat-lista")])
    Catalogo.query = Query([Catalogo(id=2, organizacion_id=1, unidad_negocio_id=3, codigo="uat-cat")])
    Inclusion.query = Query([Inclusion(id=4, catalogo_id=2, sku_comercial="UAT-001")])
    Obs.query = Query([])
    modelos = dict(ListaPrecio=Lista, Catalogo=Catalogo, CatalogoProducto=Inclusion, ObservacionComercialCanal=Obs)
    class Session:
        def add(self, row):
            row.id = len(Obs.query.rows) + 1
            row.fecha_observacion = datetime.now()
            Obs.query.rows.append(row)
        def commit(self): pass
        def rollback(self): pass
        def query(self, model): return model.query
        def get(self, model, id): return model.query.filter_by(id=id).first()
    session = Session()
    datos = dict(lista_precio_id="1", catalogo_producto_id="4", unidad_negocio_id="3", observacion_id="0", cuenta_codigo="uat", referencia_publicacion="PUB-1", precio_publicado="7.127,00")
    def guardar(**cambios):
        return registrar_precio_manual({**datos, **cambios}, organizacion_id=1, unidad_negocio_id=3, usuario=SimpleNamespace(id=5, username="admin"), modelos=modelos, db_session=session)
    return guardar, session, Obs, modelos



def test_guarda_historial_con_autor_y_no_duplica(entorno):
    guardar, session, Obs, _ = entorno
    assert guardar()
    primero = session.query(Obs).one()
    assert primero.precio_publicado_centavos == 712700
    assert primero.origen == "manual" and primero.lote_importacion_id is None
    assert primero.creado_por_usuario_id == 5
    assert not guardar(observacion_id=str(primero.id))
    assert guardar(observacion_id=str(primero.id), precio_publicado="7200")
    assert session.query(Obs).count() == 2
    assert session.get(Obs, primero.id).precio_publicado_centavos == 712700


@pytest.mark.parametrize("cambios", [{"unidad_negocio_id":"9"}, {"lista_precio_id":"999"}, {"catalogo_producto_id":"999"}, {"precio_publicado":"-1"}, {"precio_publicado":"NaN"}, {"precio_publicado":"Infinity"}, {"cuenta_codigo":""}, {"referencia_publicacion":""}])
def test_rechaza_sin_escribir(entorno, cambios):
    guardar, session, Obs, _ = entorno
    with pytest.raises(ValueError):
        guardar(**cambios)
    assert session.query(Obs).count() == 0


def test_no_acepta_catalogo_de_otra_unidad(entorno):
    guardar, session, Obs, modelos = entorno
    session.get(modelos["Catalogo"], 2).unidad_negocio_id = 9
    session.commit()
    with pytest.raises(ValueError, match="unidad activa"):
        guardar()
    assert session.query(Obs).count() == 0


def test_rechaza_formulario_obsoleto(entorno):
    guardar, session, Obs, _ = entorno
    guardar()
    with pytest.raises(ValueError, match="cambió"):
        guardar(precio_publicado="7200")
    assert session.query(Obs).count() == 1
