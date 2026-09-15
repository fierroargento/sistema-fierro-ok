from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from services.importacion_offline_crm import previsualizar_importacion
from services.confirmacion_importacion_crm import deserializar_plan,validar_confirmacion,confirmar_importacion


def obj(**kw): return SimpleNamespace(**kw)


def plan():
    csv = "tipo;codigo;nombre;unidad;canal;identidad externa;referencia;etapa;estado;importe;probabilidad\ncliente;C-1;José;hogar;whatsapp;5491;;;potencial;;\noportunidad;C-1;Venta;hogar;;;OP-1;nuevo;abierta;100;50\nactividad;C-1;Llamar;hogar;;;;;pendiente;;"
    return previsualizar_importacion(csv.encode(), organizacion_id=7, unidades=[obj(id=1,organizacion_id=7,codigo="hogar")], etapas=[obj(id=2,organizacion_id=7,codigo="nuevo")], clientes=[], identidades=[])


def validar(resultado=None, **kw):
    base=dict(organizacion_id=7,unidades=[obj(id=1,organizacion_id=7)],etapas=[obj(id=2,organizacion_id=7)],clientes=[],identidades=[],lotes=[]);base.update(kw)
    return validar_confirmacion(resultado or plan(),**base)


def test_deserializa_y_revalida_plan_firmado():
    resultado=plan();assert deserializar_plan(json.dumps(resultado).encode())["huella_plan"]==resultado["huella_plan"];assert validar(resultado) is resultado


def test_rechaza_tenant_firma_y_contrato_alterados():
    for campo,valor in (("organizacion_id",8),("modo","online"),("automatizaciones",True)):
        resultado=plan();resultado[campo]=valor
        with pytest.raises(ValueError):validar(resultado)


def test_rechaza_repeticion_idempotente():
    resultado=plan();lote=obj(organizacion_id=7,huella_documento=resultado["huella_documento"])
    with pytest.raises(ValueError,match="ya fue confirmado"):validar(resultado,lotes=[lote])


def test_rechaza_estado_actual_del_tenant_incompatible():
    resultado=plan()
    with pytest.raises(ValueError):validar(resultado,clientes=[obj(organizacion_id=7,codigo="c-1")])
    with pytest.raises(ValueError):validar(resultado,unidades=[])


class Modelo:
    def __init__(self,**kw):self.__dict__.update(kw)


class Sesion:
    def __init__(self):self.objetos=[];self.commits=0
    def add_all(self,objetos):self.objetos.extend(objetos)
    def commit(self):self.commits+=1


def test_confirmacion_atomica_crea_registros_desactivados_y_lote():
    sesion=Sesion();modelos={x:Modelo for x in ("ClienteCRM","ClienteIdentidadCanal","OportunidadCRM","ActividadCRM","LoteImportacionCRM")}
    lote=confirmar_importacion(validar(),organizacion_id=7,usuario=obj(id=4,username="admin"),nombre_archivo="plan.json",clientes_existentes=[],modelos=modelos,db_session=sesion)
    assert sesion.commits==1 and len(sesion.objetos)==5
    assert lote.clientes_creados==1 and lote.oportunidades_creadas==1 and lote.actividades_creadas==1 and lote.automatizaciones is False
    assert sesion.objetos[0].activo is False and sesion.objetos[2].activa is False


def test_servicio_no_contiene_transportes_ni_pedidos():
    codigo=Path("services/confirmacion_importacion_crm.py").read_text(encoding="utf-8").lower()
    assert not any(x in codigo for x in ("pedido.query","requests","urlopen","wa_enviar","ml_sync","tn_sync","access_token","client_secret"))


def test_ruta_delega_sin_consultas_directas():
    ruta=Path("modules/admin/crm/routes.py").read_text(encoding="utf-8");html=Path("templates/admin_importacion_crm_offline.html").read_text(encoding="utf-8")
    assert ".query" not in ruta and "validar_confirmacion(" in ruta and "confirmar_importacion(" in ruta
    assert "No crea pedidos ni inicia contactos" in html
