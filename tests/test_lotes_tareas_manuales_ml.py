from pathlib import Path
from types import SimpleNamespace

import pytest

from services.lotes_tareas_manuales_ml import aplicar_lote, exportar_evidencia, previsualizar_lote


def tarea(i, orden=1, estado="preparada", dependencia=None, org=2):
    return SimpleNamespace(id=i, organizacion_id=org, unidad_negocio_id=3, lote_diagnostico_id=8,
        puede_ejecutar=False, estado=estado, depende_de=dependencia, publicacion_id="MLA1",
        orden=orden, tipo_accion="actualizar_precio", comprobante_manual=None,
        decidido_por_username=None, fecha_decision=None, eventos=[])

class Evento:
    def __init__(self, **kw): self.__dict__.update(kw); self.id=None; self.fecha_evento="2026-09-10"
class Sesion:
    def __init__(self): self.items=[]; self.commits=0
    def add(self,x): self.items.append(x)
    def commit(self): self.commits+=1


def test_prevalidacion_es_tenant_y_atomica():
    vista=previsualizar_lote([tarea(1), tarea(2,org=9)],"aprobar","",organizacion_id=2,unidad_negocio_id=3,vigencias={8:True})
    assert not vista["puede_aplicar"] and "fuera del tenant" in vista["errores"][0]


def test_aplica_una_sola_confirmacion_y_audita():
    s=Sesion(); tareas=[tarea(1),tarea(2)]
    vista=previsualizar_lote(tareas,"aprobar","",organizacion_id=2,unidad_negocio_id=3,vigencias={8:True})
    salida=aplicar_lote(vista,"",usuario=SimpleNamespace(username="admin"),vigencias={8:True},EventoTareaManualML=Evento,db_session=s)
    assert salida["actualizadas"]==2 and s.commits==1
    assert all(t.estado=="aprobada" and t.puede_ejecutar is False for t in tareas)
    assert len(s.items)==2


def test_dependencias_se_prevalidan_antes_de_mutar():
    primera=tarea(1,1,"aprobada"); segunda=tarea(2,2,"aprobada",primera)
    vista=previsualizar_lote([segunda],"completar_manual","ticket",organizacion_id=2,unidad_negocio_id=3,vigencias={8:True})
    assert not vista["puede_aplicar"] and primera.estado=="aprobada" and segunda.estado=="aprobada"


def test_obsolescencia_bloquea_todo_el_lote():
    vista=previsualizar_lote([tarea(1)],"aprobar","",organizacion_id=2,unidad_negocio_id=3,vigencias={8:False})
    assert not vista["puede_aplicar"] and "obsoleto" in vista["errores"][0]


def test_evidencia_utf8_incluye_eventos():
    t=tarea(1); t.eventos=[SimpleNamespace(id=4,estado_anterior="preparada",estado_nuevo="aprobada",username="martín",comprobante="revisión",fecha_evento="2026-09-10")]
    dato=exportar_evidencia([t]).getvalue()
    assert dato.startswith(b"\xef\xbb\xbf") and "martín" in dato.decode("utf-8-sig")


def test_contrato_desconectado_y_modelo_auditable():
    fuente=Path("services/lotes_tareas_manuales_ml.py").read_text(encoding="utf-8").lower()
    modelo=Path("models/tarea_manual_ml.py").read_text(encoding="utf-8").lower()
    assert not any(x in fuente for x in ("requests", "urlopen", "access_token", "client_secret", "http://", "https://"))
    assert "eventotareamanualml" in modelo and "puede_ejecutar = false" in modelo
