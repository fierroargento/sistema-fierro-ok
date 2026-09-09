import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.tareas_manuales_ml import decidir_tarea, especificaciones_lote, exportar_tareas, preparar_tareas


def lote(estado="aprobado"):
    resultado={"control":{"resultados":[{"publicacion":{"publicacion_id":"MLA1","sku":"SKU1","precio_centavos":100},"precio_objetivo_centavos":130,"acciones":[{"orden":1,"accion":"cancelar_promocion"},{"orden":2,"accion":"actualizar_precio"}]}]}}
    return SimpleNamespace(id=4,organizacion_id=2,unidad_negocio_id=3,lote_id="L1",huella_dependencias="h",resultado_json=json.dumps(resultado),estado=estado,puede_ejecutar=False)


class Query:
    def filter_by(self, **kw): return self
    def all(self): return []
class Tarea:
    query=Query()
    def __init__(self, **kw): self.__dict__.update(kw); self.id=None
class Sesion:
    def __init__(self): self.items=[]
    def add(self,x): self.items.append(x)
    def flush(self): self.items[-1].id=len(self.items)
    def commit(self): pass


def test_prepara_cadena_idempotente_no_ejecutable():
    s=Sesion(); r=preparar_tareas(lote(),usuario=SimpleNamespace(username="admin"),TareaManualML=Tarea,db_session=s)
    assert len(r["creadas"])==2 and r["puede_ejecutar"] is False
    assert r["creadas"][1].depende_de is r["creadas"][0]


def test_exige_lote_aprobado():
    with pytest.raises(ValueError): especificaciones_lote(lote("revision"))


def test_bloquea_obsoleta_y_dependencia():
    s=Sesion(); primera=SimpleNamespace(estado="aprobada",puede_ejecutar=False,depende_de=None)
    segunda=SimpleNamespace(estado="aprobada",puede_ejecutar=False,depende_de=primera)
    with pytest.raises(ValueError): decidir_tarea(segunda,"completar_manual","ticket",usuario=None,lote_vigente=True,db_session=s)
    decidir_tarea(primera,"completar_manual","ticket-1",usuario=None,lote_vigente=True,db_session=s)
    decidir_tarea(segunda,"completar_manual","ticket-2",usuario=None,lote_vigente=True,db_session=s)
    assert segunda.estado=="completada_manual"
    tercera=SimpleNamespace(estado="preparada",puede_ejecutar=False,depende_de=None)
    decidir_tarea(tercera,"aprobar","",usuario=None,lote_vigente=False,db_session=s)
    assert tercera.estado=="obsoleta" and tercera.puede_ejecutar is False


def test_exporta_utf8_para_gestion_humana():
    dato=SimpleNamespace(publicacion_id="MLA1",sku="Ñ",orden=1,tipo_accion="actualizar_precio",precio_actual_centavos=1,precio_propuesto_centavos=2,estado="aprobada",comprobante_manual=None)
    contenido=exportar_tareas([dato]).getvalue()
    assert contenido.startswith(b"\xef\xbb\xbf") and "Ñ" in contenido.decode("utf-8-sig")


def test_contrato_estatico_sin_transporte_y_modelo_bloqueado():
    servicio=Path("services/tareas_manuales_ml.py").read_text(encoding="utf-8").lower()
    modelo=Path("models/tarea_manual_ml.py").read_text(encoding="utf-8").lower()
    assert not any(x in servicio for x in ("requests", "urlopen", "access_token", "client_secret", "http://", "https://"))
    assert "puede_ejecutar = false" in modelo
    app=Path("app.py").read_text(encoding="utf-8-sig")
    bootstrap=Path("services/bootstrap_modulos_web.py").read_text(encoding="utf-8-sig")
    assert '"TareaManualML": TareaManualML' in app
    assert '"TareaManualML"' in bootstrap
