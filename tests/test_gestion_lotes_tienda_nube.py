import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.gestion_lotes_tienda_nube import (
    decidir_lote, exportar_evidencia_lote, huella_documento,
    registrar_lote, resumir_bandeja,
)


class Query:
    def __init__(self, encontrado=None): self.encontrado = encontrado
    def filter_by(self, **_filtros): return self
    def first(self): return self.encontrado


class Registro:
    query = Query()
    def __init__(self, **datos): self.__dict__.update(datos); self.id = 12; self.eventos = []


class Evento:
    def __init__(self, **datos): self.__dict__.update(datos)


class Sesion:
    def __init__(self): self.agregados = []; self.commits = 0; self.rollbacks = 0
    def add(self, item): self.agregados.append(item)
    def flush(self): pass
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


def resultado(bloqueadas=0, errores=0):
    return {
        "contexto": {"organizacion_id": 2, "unidad_negocio_id": 3, "vinculo_id": 4, "cuenta_id": 8, "store_id": "STORE-1"},
        "resumen": {"filas": 2, "aptas": 2 - bloqueadas, "bloqueadas": bloqueadas, "errores": errores, "acciones_externas": 0},
        "resultados": [], "errores": [], "escrituras": 0, "aplicable": False,
    }


def lote(estado="preparado", bloqueadas=0, errores=0, tenant=2):
    return SimpleNamespace(
        id=12, organizacion_id=tenant, unidad_negocio_id=3,
        tienda_nube_cuenta_id=8, store_id_snapshot="STORE-1",
        nombre_archivo="pedidos.json", huella_documento="a" * 64,
        evidencia_json=json.dumps(resultado()), filas=2, aptas=2,
        bloqueadas=bloqueadas, errores=errores, estado=estado,
        puede_ejecutar=False, fecha_creacion=datetime(2026, 9, 1), eventos=[],
    )


def test_huella_documento_es_estable():
    assert huella_documento(b"abc") == huella_documento("abc")
    assert len(huella_documento(b"abc")) == 64


def test_registro_es_idempotente_y_auditable():
    Registro.query = Query()
    sesion = Sesion()
    registro, creado = registrar_lote(
        resultado(), b"[]", "pedidos.json", usuario=SimpleNamespace(id=5, username="admin"),
        LoteDiagnosticoTiendaNube=Registro,
        EventoLoteDiagnosticoTiendaNube=Evento, db_session=sesion,
    )
    assert creado and registro.estado == "preparado" and registro.puede_ejecutar is False
    assert len(sesion.agregados) == 2 and sesion.commits == 1
    Registro.query = Query(registro)
    repetido, creado = registrar_lote(
        resultado(), b"[]", "pedidos.json", usuario=None,
        LoteDiagnosticoTiendaNube=Registro,
        EventoLoteDiagnosticoTiendaNube=Evento, db_session=Sesion(),
    )
    assert repetido is registro and not creado


def test_flujo_revision_aprobacion_y_archivo_no_ejecuta():
    item = lote(); sesion = Sesion(); usuario = SimpleNamespace(id=5, username="admin")
    r1 = decidir_lote(item, "enviar_revision", "", organizacion_id=2, unidad_negocio_id=3, usuario=usuario, EventoLoteDiagnosticoTiendaNube=Evento, db_session=sesion)
    r2 = decidir_lote(item, "aprobar", "", organizacion_id=2, unidad_negocio_id=3, usuario=usuario, EventoLoteDiagnosticoTiendaNube=Evento, db_session=sesion)
    r3 = decidir_lote(item, "archivar", "control finalizado", organizacion_id=2, unidad_negocio_id=3, usuario=usuario, EventoLoteDiagnosticoTiendaNube=Evento, db_session=sesion)
    assert [r1["estado"], r2["estado"], r3["estado"]] == ["revision", "aprobado", "archivado"]
    assert all(r["acciones_externas"] == 0 and r["puede_ejecutar"] is False for r in (r1, r2, r3))


def test_aprobacion_bloquea_errores_y_pedidos_no_aptos():
    for item in (lote("revision", bloqueadas=1), lote("revision", errores=1)):
        with pytest.raises(ValueError):
            decidir_lote(item, "aprobar", "", organizacion_id=2, unidad_negocio_id=3, usuario=None, EventoLoteDiagnosticoTiendaNube=Evento, db_session=Sesion())


def test_decisiones_exigen_tenant_transicion_y_motivo():
    with pytest.raises(ValueError):
        decidir_lote(lote(tenant=9), "enviar_revision", "", organizacion_id=2, unidad_negocio_id=3, usuario=None, EventoLoteDiagnosticoTiendaNube=Evento, db_session=Sesion())
    with pytest.raises(ValueError):
        decidir_lote(lote(), "aprobar", "", organizacion_id=2, unidad_negocio_id=3, usuario=None, EventoLoteDiagnosticoTiendaNube=Evento, db_session=Sesion())
    with pytest.raises(ValueError):
        decidir_lote(lote("revision"), "rechazar", "", organizacion_id=2, unidad_negocio_id=3, usuario=None, EventoLoteDiagnosticoTiendaNube=Evento, db_session=Sesion())


def test_bandeja_filtra_y_resume_por_tenant():
    resumen = resumir_bandeja([lote(), lote("revision"), lote(tenant=9)], organizacion_id=2, unidad_negocio_id=3)
    assert resumen["total"] == 2 and resumen["preparados"] == resumen["revision"] == 1
    assert resumen["acciones_externas"] == 0


def test_exportacion_revalida_tenant_y_conserva_contrato():
    contenido = json.loads(exportar_evidencia_lote(lote(), organizacion_id=2, unidad_negocio_id=3).getvalue())
    assert contenido["lote"]["store_id"] == "STORE-1"
    assert contenido["lote"]["acciones_externas"] == 0
    with pytest.raises(ValueError):
        exportar_evidencia_lote(lote(), organizacion_id=9, unidad_negocio_id=3)


def test_modelo_panel_y_bootstrap_quedan_integrados():
    modelo = Path("models/lote_diagnostico_tienda_nube.py").read_text(encoding="utf-8")
    ruta = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    html = Path("templates/admin_tienda_nube_offline.html").read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")
    assert "puede_ejecutar = false" in modelo
    assert 'value="guardar_lote"' in html and 'value="enviar_revision"' in html
    assert "registrar_lote_tienda_nube(" in ruta and "LoteDiagnosticoTiendaNube" in app


def test_servicio_no_incluye_transporte_ni_pedidos_productivos():
    fuente = Path("services/gestion_lotes_tienda_nube.py").read_text(encoding="utf-8").lower()
    prohibidos = ("requests", "urlopen", "access_token", "client_secret", "http://", "https://", "pedido.query", "tn_http_json")
    assert not any(texto in fuente for texto in prohibidos)
