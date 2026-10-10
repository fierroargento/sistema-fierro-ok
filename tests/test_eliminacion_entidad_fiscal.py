import pytest
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, create_engine, event, select
from sqlalchemy.orm import declarative_base, sessionmaker
from services.eliminacion_entidad_fiscal import eliminar_entidad_fiscal_sin_uso

Base = declarative_base()
class Entidad(Base):
    __tablename__ = "entidad_fiscal"
    id = Column(Integer, primary_key=True)
    organizacion_id = Column(Integer, nullable=False)
    codigo = Column(String)
    razon_social = Column(String)
    activa = Column(Boolean, default=False)
    facturacion_habilitada = Column(Boolean, default=False)
class Vinculo(Base):
    __tablename__ = "vinculo_canal_comercial"
    id = Column(Integer, primary_key=True)
    entidad_fiscal_id = Column(Integer, ForeignKey("entidad_fiscal.id"))
    estado = Column(String)
class Borrador(Base):
    __tablename__ = "borrador_comprobante_fiscal"
    id = Column(Integer, primary_key=True)
    entidad_fiscal_id = Column(Integer, ForeignKey("entidad_fiscal.id"))
    estado = Column(String)
class Configuracion(Base):
    __tablename__ = "configuracion_fiscal"
    id = Column(Integer, primary_key=True)
    entidad_fiscal_id = Column(Integer, ForeignKey("entidad_fiscal.id"))
class PuntoVenta(Base):
    __tablename__ = "punto_venta_fiscal"
    id = Column(Integer, primary_key=True)
    entidad_fiscal_id = Column(Integer, ForeignKey("entidad_fiscal.id"))

@pytest.fixture
def sesion():
    engine = create_engine("sqlite://")
    @event.listens_for(engine, "connect")
    def activar_fk(conn, record):
        conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        session.add_all([
            Entidad(id=1, organizacion_id=1, codigo="error", razon_social="Error"),
            Entidad(id=2, organizacion_id=2, codigo="otra", razon_social="Otra"),
        ])
        session.commit()
        yield session

def borrar(sesion, **kwargs):
    return eliminar_entidad_fiscal_sin_uso(
        modelo=Entidad, sesion=sesion,
        **dict(dict(organizacion_id=1, entidad_fiscal_id=1, confirmacion="1"), **kwargs)
    )

def test_elimina_solo_entidad_sin_uso(sesion):
    assert "ID 1" in borrar(sesion)
    assert sesion.get(Entidad, 1) is None
    assert sesion.get(Entidad, 2) is not None

@pytest.mark.parametrize("kwargs", [
    {"confirmacion": ""}, {"confirmacion": "true"},
    {"entidad_fiscal_id": 2}, {"entidad_fiscal_id": 999},
])
def test_rechaza_sin_confirmacion_o_fuera_tenant(sesion, kwargs):
    with pytest.raises(ValueError):
        borrar(sesion, **kwargs)
    assert sesion.query(Entidad).count() == 2

@pytest.mark.parametrize("campo", ["activa", "facturacion_habilitada"])
def test_rechaza_entidad_habilitada(sesion, campo):
    setattr(sesion.get(Entidad, 1), campo, True)
    sesion.commit()
    with pytest.raises(ValueError):
        borrar(sesion)
    assert sesion.get(Entidad, 1) is not None

@pytest.mark.parametrize("modelo, datos", [
    (Vinculo, {"estado": "desactivado"}),
    (Borrador, {"estado": "cancelado"}),
    (Configuracion, {}),
    (PuntoVenta, {}),
])
def test_conserva_cualquier_vinculo_e_historial(sesion, modelo, datos):
    sesion.add(modelo(id=1, entidad_fiscal_id=1, **datos))
    sesion.commit()
    with pytest.raises(ValueError, match="vínculos o historial"):
        borrar(sesion)
    assert sesion.get(Entidad, 1) is not None
    assert sesion.get(modelo, 1) is not None

def test_error_commit_revierte_eliminacion(sesion, monkeypatch):
    def fallar():
        raise RuntimeError("fallo simulado")
    monkeypatch.setattr(sesion, "commit", fallar)
    with pytest.raises(RuntimeError):
        borrar(sesion)
    assert sesion.get(Entidad, 1) is not None
