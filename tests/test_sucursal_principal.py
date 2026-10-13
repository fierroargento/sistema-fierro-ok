import pytest
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from services.sucursal_principal import establecer_sucursal_principal

Base = declarative_base()
class Organizacion(Base):
    __tablename__ = "organizacion"
    id = Column(Integer, primary_key=True)
class Sucursal(Base):
    __tablename__ = "sucursal_operativa"
    id = Column(Integer, primary_key=True)
    organizacion_id = Column(Integer, ForeignKey("organizacion.id"))
    codigo = Column(String)
    nombre = Column(String)
    activa = Column(Boolean)
    es_principal = Column(Boolean)

@pytest.fixture
def sesion():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        s.add_all([Organizacion(id=1), Organizacion(id=2)])
        s.add_all([
            Sucursal(id=1, organizacion_id=1, codigo="origen", nombre="Origen", activa=True, es_principal=False),
            Sucursal(id=2, organizacion_id=1, codigo="destino", nombre="Destino", activa=True, es_principal=False),
            Sucursal(id=3, organizacion_id=1, codigo="inactiva", nombre="Inactiva", activa=False, es_principal=False),
            Sucursal(id=4, organizacion_id=2, codigo="otra", nombre="Otra", activa=True, es_principal=True),
        ])
        s.commit()
        yield s

def elegir(s, **kwargs):
    return establecer_sucursal_principal(
        modelo_organizacion=Organizacion, modelo_sucursal=Sucursal, sesion=s,
        **dict(dict(organizacion_id=1, sucursal_id=1, confirmacion="1"), **kwargs)
    )

def test_principal_unica_sin_cambiar_estados_ni_otro_tenant(sesion):
    assert "origen" in elegir(sesion)
    assert sesion.get(Sucursal, 1).es_principal
    elegir(sesion, sucursal_id=2)
    assert not sesion.get(Sucursal, 1).es_principal
    assert sesion.get(Sucursal, 2).es_principal
    assert not sesion.get(Sucursal, 3).activa
    assert sesion.get(Sucursal, 4).es_principal
    assert sesion.get(Sucursal, 1).activa
    assert sesion.get(Sucursal, 2).activa

@pytest.mark.parametrize("kwargs", [
    {"confirmacion": ""}, {"sucursal_id":3}, {"sucursal_id":4},
    {"sucursal_id":999}, {"organizacion_id":999}
])
def test_rechazo_no_modifica_principales(sesion, kwargs):
    with pytest.raises(ValueError):
        elegir(sesion, **kwargs)
    assert sesion.query(Sucursal).filter_by(organizacion_id=1, es_principal=True).count()==0
    assert sesion.get(Sucursal, 4).es_principal

def test_repara_multiples_marcas_y_es_idempotente(sesion):
    for i in (1, 2, 3):
        sesion.get(Sucursal, i).es_principal=True
    sesion.commit()
    elegir(sesion)
    elegir(sesion)
    assert sesion.query(Sucursal).filter_by(organizacion_id=1, es_principal=True).count()==1
    assert sesion.get(Sucursal, 1).es_principal

def test_fallo_commit_revierte_todas_las_marcas(sesion, monkeypatch):
    def fallar():
        raise RuntimeError("fallo simulado")
    monkeypatch.setattr(sesion, "commit", fallar)
    with pytest.raises(RuntimeError):
        elegir(sesion)
    assert sesion.query(Sucursal).filter_by(organizacion_id=1, es_principal=True).count()==0
