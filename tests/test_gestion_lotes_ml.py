import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.gestion_lotes_ml import (
    decidir_lote, diagnosticar_vigencia, huella_dependencias, registrar_lote,
)
from services.lotes_offline_ml import consolidar_lote_secciones


def archivos():
    return {
        "precios": json.dumps([{"id": "MLA-1", "seller_sku": "SKU-1", "price": 1000}]),
        "cargos": json.dumps([{"id": "MLA-1", "commission_percentage": 15, "fixed_fee": 100}]),
        "envios": json.dumps([{"id": "MLA-1", "shipping_cost": 0}]),
        "promociones": "[]",
    }


def fila_control(precio=130000, costo_id=4):
    return {"regla_canal": SimpleNamespace(id=3, lista_precio_id=10, comision_pct="15"), "costo": SimpleNamespace(id=costo_id, producto=SimpleNamespace(sku="SKU-1")), "regla": SimpleNamespace(id=5), "inclusion": SimpleNamespace(id=6), "minimo": {"piso_liquidacion_centavos": 90000}, "objetivo": {"piso_liquidacion_centavos": 100000}, "propuesto": {"precio_final_centavos": precio}, "actual": {"cargo_fijo_centavos": 10000, "envio_centavos": 0}}


def resultado():
    return consolidar_lote_secciones(archivos(), [fila_control()], cuenta_codigo="CTA", organizacion_id=2, unidad_negocio_id=3, lista_precio_id=10)


class QueryVacia:
    def filter_by(self, **_filtros):
        return self

    def first(self):
        return None


class Registro:
    query = QueryVacia()

    def __init__(self, **datos):
        self.__dict__.update(datos)
        self.id = 71


class Evento:
    def __init__(self, **datos):
        self.__dict__.update(datos)


class Sesion:
    def __init__(self):
        self.agregados = []
        self.commits = 0

    def add(self, item):
        self.agregados.append(item)

    def flush(self):
        pass

    def commit(self):
        self.commits += 1


def test_registro_congela_snapshot_huellas_y_ejecucion_bloqueada():
    sesion = Sesion()
    lote, creado = registrar_lote(resultado(), vinculo_canal_id=8, usuario=SimpleNamespace(id=9, username="admin"), LoteDiagnosticoML=Registro, EventoLoteDiagnosticoML=Evento, db_session=sesion)
    assert creado is True and lote.estado == "preparado"
    assert lote.puede_ejecutar is False
    assert json.loads(lote.snapshot_json)["resultados"][0]["sku"] == "SKU-1"
    assert sesion.commits == 1 and len(sesion.agregados) == 2


def test_vigencia_detecta_cambio_de_costo_regla_o_precio():
    datos = resultado()
    lote = SimpleNamespace(snapshot_json=json.dumps(datos["lote"]["snapshot"]), lista_precio_id=10, huella_dependencias=huella_dependencias(datos["control"]))
    assert diagnosticar_vigencia(lote, [fila_control()])["vigente"] is True
    assert diagnosticar_vigencia(lote, [fila_control(costo_id=99)])["vigente"] is False


def test_aprobacion_obsoleta_se_bloquea_y_marca_obsoleto():
    datos = resultado()
    lote = SimpleNamespace(id=1, organizacion_id=2, unidad_negocio_id=3, snapshot_json=json.dumps(datos["lote"]["snapshot"]), resultado_json=json.dumps(datos), lista_precio_id=10, huella_dependencias=huella_dependencias(datos["control"]), estado="revision", puede_ejecutar=False)
    salida = decidir_lote(lote, "aprobar", "", usuario=SimpleNamespace(id=9, username="admin"), filas_control=[fila_control(precio=140000)], EventoLoteDiagnosticoML=Evento, db_session=Sesion())
    assert salida["estado"] == "obsoleto"
    assert salida["puede_ejecutar"] is False and lote.puede_ejecutar is False


def test_flujo_revision_aprobacion_y_motivos_obligatorios():
    datos = resultado()
    lote = SimpleNamespace(id=1, organizacion_id=2, unidad_negocio_id=3, snapshot_json=json.dumps(datos["lote"]["snapshot"]), resultado_json=json.dumps(datos), lista_precio_id=10, huella_dependencias=huella_dependencias(datos["control"]), estado="preparado", puede_ejecutar=False)
    decidir_lote(lote, "enviar_revision", "", usuario=SimpleNamespace(id=9, username="admin"), filas_control=[fila_control()], EventoLoteDiagnosticoML=Evento, db_session=Sesion())
    assert lote.estado == "revision"
    decidir_lote(lote, "aprobar", "", usuario=SimpleNamespace(id=9, username="admin"), filas_control=[fila_control()], EventoLoteDiagnosticoML=Evento, db_session=Sesion())
    assert lote.estado == "aprobado" and lote.puede_ejecutar is False
    with pytest.raises(ValueError):
        decidir_lote(lote, "archivar", "", usuario=None, filas_control=[fila_control()], EventoLoteDiagnosticoML=Evento, db_session=Sesion())


def test_modelo_impone_tenant_unicidad_estados_y_no_ejecucion():
    modelo = Path("models/lote_diagnostico_ml.py").read_text(encoding="utf-8")
    assert "uq_lote_diagnostico_ml_tenant" in modelo
    assert "puede_ejecutar = db.Column(db.Boolean, default=False" in modelo
    assert "EventoLoteDiagnosticoML" in modelo


def test_ruta_limita_historial_y_decisiones_al_tenant():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    bloque = rutas.split("def mercado_libre_offline_comercial():", 1)[1].split("@blueprint.route", 1)[0]
    assert "LoteML.query.filter_by" in bloque
    assert "organizacion_id=organizacion.id" in bloque
    assert "unidad_negocio_id=unidad_activa.id" in bloque
    assert "puede_ejecutar=True" not in bloque


def test_gestor_no_contiene_transporte_ni_credenciales():
    fuente = Path("services/gestion_lotes_ml.py").read_text(encoding="utf-8").lower()
    for prohibido in ("requests", "urlopen", "access_token", "client_secret", "http://", "https://"):
        assert prohibido not in fuente
