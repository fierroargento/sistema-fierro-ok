from types import SimpleNamespace as Obj

import pytest
from services import fuentes_costo_admin as admin


class Query:
    def __init__(self, machine):
        self.machine = machine

    def filter_by(self, **filters):
        self.filters = filters
        return self

    def first(self):
        return self.machine if all(getattr(self.machine, k) == v for k, v in self.filters.items()) else None


def execute(monkeypatch, machine, **changes):
    captured = []
    def registrar(record, **kwargs):
        captured.append((record, kwargs))
        return Obj(numero_version=2)
    monkeypatch.setattr(admin, 'registrar_costo_maquina', registrar)
    form = dict(maquina_id='1', nombre='Máquina UAT', categoria='Corte', activo='0',
                valor_adquisicion='120000', vida_util_horas='1000', horas_productivas_mensuales='100')
    form.update(changes)
    models = dict(Organizacion=Obj, UnidadNegocio=Obj,
                  MaquinaProductiva=Obj(query=Query(machine)), MaquinaCostoVersion=Obj)
    result = admin.procesar_accion_fuente_costo(
        'actualizar_costo_maquina', form, organizacion=Obj(id=1), unidad_activa=Obj(id=3),
        modelos=models, db_session=Obj(), usuario=Obj(id=4))
    return result, captured


def machine(**changes):
    values = dict(id=1, organizacion_id=1, unidad_negocio_id=3, nombre='Anterior', categoria='Anterior', activo=False)
    values.update(changes)
    return Obj(**values)


def test_gestion_reutiliza_registro_y_versionador(monkeypatch):
    current = machine()
    result, calls = execute(monkeypatch, current, activo='1')
    assert 'version 2' in result
    assert len(calls) == 1 and calls[0][0] is current
    assert calls[0][1]['valor_adquisicion_centavos'] == 12000000
    assert current.nombre == 'Máquina UAT' and current.activo is True


@pytest.mark.parametrize('changes', [dict(organizacion_id=2), dict(unidad_negocio_id=4)])
def test_gestion_rechaza_registro_ajeno(monkeypatch, changes):
    current = machine(**changes)
    with pytest.raises(ValueError, match='no pertenece'):
        execute(monkeypatch, current)
    assert current.nombre == 'Anterior' and current.activo is False


@pytest.mark.parametrize('changes', [dict(nombre=''), dict(categoria=''), dict(nombre='a'*201), dict(categoria='a'*101), dict(activo='externo')])
def test_gestion_rechaza_metadatos_invalidos(monkeypatch, changes):
    current = machine()
    with pytest.raises(ValueError):
        execute(monkeypatch, current, **changes)
    assert current.nombre == "Anterior" and current.activo is False
