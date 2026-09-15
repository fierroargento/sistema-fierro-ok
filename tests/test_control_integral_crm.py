from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from services.control_integral_crm import controlar_crm,exportar_control
from services.gestion_lotes_crm import anular_lote,exportar_evidencia


def obj(**kw): return SimpleNamespace(**kw)


def datos(lotes=None):
    return dict(organizacion_id=7,modulo=obj(estado="prueba"),unidades=[obj(id=1,organizacion_id=7)],etapas=[obj(id=2,organizacion_id=7)],clientes=[obj(id=3,organizacion_id=7,codigo="C-1",unidad_negocio_id=1,estado="cliente",documento=None,email="a@b.com",telefono=None)],identidades=[],oportunidades=[],actividades=[],lotes=lotes or [])


def lote(**kw):
    base=dict(id=8,organizacion_id=7,nombre_archivo="crm.json",huella_documento="a"*64,huella_plan="b"*64,estado="confirmado",clientes_creados=1,identidades_creadas=0,oportunidades_creadas=0,actividades_creadas=0,evidencia_json='{"modo":"offline"}',automatizaciones=False);base.update(kw);return obj(**base)


def test_control_limpio_firmado_y_solo_lectura():
    resultado=controlar_crm(**datos([lote()]));assert resultado["aprobado"] and resultado["resumen"]["lotes_confirmados"]==1 and resultado["controles"]["escrituras"]==0


def test_detecta_huellas_duplicadas_y_otro_tenant_no_incide():
    resultado=controlar_crm(**datos([lote(id=1),lote(id=2),lote(id=3,organizacion_id=99)]));assert not resultado["aprobado"] and resultado["resumen"]["lotes"]==2


def test_exportaciones_utf8_con_evidencia():
    assert json.loads(exportar_control(controlar_crm(**datos())).read())["modo"]=="offline"
    assert json.loads(exportar_evidencia(lote()).read())["evidencia"]["modo"]=="offline"


class Sesion:
    def __init__(self):self.commits=0
    def commit(self):self.commits+=1


def test_anulacion_conserva_lote_y_confirma_una_vez():
    item=lote();sesion=Sesion();assert anular_lote(item,organizacion_id=7,db_session=sesion) is item;assert item.estado=="anulado" and sesion.commits==1
    with pytest.raises(ValueError):anular_lote(item,organizacion_id=7,db_session=sesion)


def test_anulacion_bloquea_otro_tenant_y_automatizaciones():
    with pytest.raises(ValueError):anular_lote(lote(),organizacion_id=9,db_session=Sesion())
    with pytest.raises(ValueError):anular_lote(lote(automatizaciones=True),organizacion_id=7,db_session=Sesion())


def test_servicios_no_tocan_operacion_externa():
    codigo=(Path("services/control_integral_crm.py").read_text(encoding="utf-8")+Path("services/gestion_lotes_crm.py").read_text(encoding="utf-8")).lower()
    assert not any(x in codigo for x in ("pedido.query","requests","urlopen","wa_enviar","ml_sync","tn_sync","access_token","client_secret","delete("))


def test_panel_final_y_rutas_delegadas():
    ruta=Path("modules/admin/crm/routes.py").read_text(encoding="utf-8");html=Path("templates/admin_control_integral_crm.html").read_text(encoding="utf-8")
    assert ".query" not in ruta and "controlar_crm(" in ruta and "anular_lote(" in ruta and "exportar_evidencia(" in ruta
    assert "solo lectura" in html and "no crea pedidos" in html
