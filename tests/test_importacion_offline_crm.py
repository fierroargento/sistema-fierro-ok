from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from services.importacion_offline_crm import exportar_previsualizacion,previsualizar_importacion


def objeto(**datos):
    return SimpleNamespace(**datos)


def base(contenido, **cambios):
    argumentos = dict(
        organizacion_id=7,
        unidades=[objeto(id=1, organizacion_id=7, codigo="hogar")],
        etapas=[objeto(id=2, organizacion_id=7, codigo="nuevo")],
        clientes=[],
        identidades=[],
    )
    argumentos.update(cambios)
    return previsualizar_importacion(contenido.encode("utf-8"), **argumentos)


def csv_valido():
    return "tipo;codigo;nombre;unidad;email;canal;identidad externa;referencia;etapa;estado;importe;probabilidad\ncliente;C-1;José Pérez;hogar;jose@ejemplo.com;whatsapp;54911;;;potencial;;\noportunidad;C-1;Venta parrilla;hogar;;;;OP-1;nuevo;abierta;150000,50;60\nactividad;C-1;Llamar al cliente;hogar;;;;;;pendiente;;"


def test_previsualiza_tres_tipos_sin_escrituras():
    resultado = base(csv_valido())
    assert resultado["resumen"] == {"filas": 3, "clientes": 1, "oportunidades": 1, "actividades": 1, "preparados": 3, "rechazados": 0, "escrituras": 0, "mensajes_enviados": 0, "acciones_externas": 0}
    assert resultado["confirmacion_habilitada"] is False


def test_rechaza_unidad_y_etapa_de_otro_tenant():
    resultado = base("tipo;codigo;nombre;unidad;referencia;etapa;estado\ncliente;C-1;Ana;ajena;;;potencial\noportunidad;C-1;Venta;ajena;OP-1;ajena;abierta")
    errores = " ".join(error for fila in resultado["filas"] for error in fila["errores"])
    assert "unidad de negocio" in errores and "etapa" in errores


def test_rechaza_codigo_e_identidad_duplicados():
    cliente = objeto(id=9, organizacion_id=7, codigo="C-1")
    identidad = objeto(organizacion_id=7, canal="whatsapp", identificador_externo="54911")
    resultado = base("tipo;codigo;nombre;canal;identidad externa;estado\ncliente;C-1;Ana;whatsapp;54911;potencial", clientes=[cliente], identidades=[identidad])
    assert resultado["resumen"]["rechazados"] == 1


def test_rechaza_relacion_huerfana_y_economia_invalida():
    resultado = base("tipo;codigo;nombre;referencia;estado;importe;probabilidad\noportunidad;NO-EXISTE;Venta;OP-1;abierta;-1;120")
    assert len(resultado["filas"][0]["errores"]) >= 2


def test_limites_y_columnas_obligatorias():
    with pytest.raises(ValueError, match="Faltan columnas"):
        base("codigo;nombre\nC-1;Ana")
    with pytest.raises(ValueError, match="vacío"):
        previsualizar_importacion(b"", organizacion_id=7, unidades=[], etapas=[], clientes=[], identidades=[])


def test_huella_estable_y_documento_distinto():
    primero = base(csv_valido())
    segundo = base(csv_valido())
    tercero = base(csv_valido().replace("José", "Jose"))
    assert primero["huella_plan"] == segundo["huella_plan"]
    assert primero["huella_documento"] != tercero["huella_documento"]


def test_exporta_utf8_y_acentos():
    documento = json.loads(exportar_previsualizacion(base(csv_valido())).read())
    assert documento["filas"][0]["nombre"] == "José Pérez"


def test_servicio_es_desconectado_y_no_persistente():
    codigo = Path("services/importacion_offline_crm.py").read_text(encoding="utf-8").lower()
    prohibidos = ("pedido.query", "requests", "urlopen", "db.session", "commit(", "rollback(", "wa_enviar", "ml_sync", "tn_sync", "access_token", "client_secret")
    assert not any(texto in codigo for texto in prohibidos)


def test_ruta_delega_y_no_consulta_modelos():
    ruta = Path("modules/admin/crm/routes.py").read_text(encoding="utf-8")
    html = Path("templates/admin_importacion_crm_offline.html").read_text(encoding="utf-8")
    assert ".query" not in ruta
    assert "previsualizar_importacion(" in ruta
    assert "No confirma registros" in html and "Confirmación bloqueada" in html
