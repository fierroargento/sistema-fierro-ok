import hashlib
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from services.certificacion_integral_mp import (
    certificar_preparacion_mp,
    exportar_certificacion_integral,
)
from services.cierres_conciliacion_mp import huella_snapshot, snapshot_conciliacion


def venta(tenant=2):
    return SimpleNamespace(
        id=1, organizacion_id=tenant, unidad_negocio_id=3,
        cuenta_codigo="MP", referencia_venta="V1", referencia_pago="P1",
        estado="confirmada", liquidacion_esperada_centavos=1000,
        piso_unitario_snapshot_centavos=900, cantidad=1,
        importe_bruto_centavos=1200,
    )


def movimiento(tenant=2, estado="confirmado"):
    return SimpleNamespace(
        id=2, organizacion_id=tenant, unidad_negocio_id=3,
        cuenta_codigo="MP", referencia_venta="V1", referencia_pago="P1",
        referencia_movimiento="M1", impacta_saldo=True, estado=estado,
        importe_centavos=1000, direccion="credito", tipo="liquidacion_neta",
        origen="extracto_mp",
    )


def cierre(v, m, estado="cerrado", tenant=2):
    snapshot = snapshot_conciliacion([v], [m], [])
    return SimpleNamespace(
        id=3, organizacion_id=tenant, unidad_negocio_id=3,
        estado=estado, fecha_creacion=datetime(2026, 9, 1),
        snapshot_json=json.dumps(snapshot),
        certificacion_json=json.dumps({"aprobada": True}),
        huella_origen=huella_snapshot(snapshot), puede_ejecutar=False,
    )


def lote(tenant=2, huella="a" * 64):
    evidencia = {
        "filas": [{
            "accion": "crear",
            "datos": {"cuenta_codigo": "MP", "referencia_movimiento": "M1"},
        }],
    }
    return SimpleNamespace(
        id=4, organizacion_id=tenant, unidad_negocio_id=3,
        estado="confirmado", fecha_creacion=datetime(2026, 9, 1),
        evidencia_json=json.dumps(evidencia), huella_documento=huella,
    )


def test_escenario_integral_aprueba_y_no_ejecuta():
    v = venta(); m = movimiento()
    resultado = certificar_preparacion_mp(
        [v], [m], [], [cierre(v, m)], [lote()],
        organizacion_id=2, unidad_negocio_id=3,
    )
    assert resultado["aprobada"] and resultado["estado"] == "aprobada"
    assert resultado["resumen"]["cierres_terminales"] == 1
    assert resultado["resumen"]["acciones_externas"] == 0
    assert resultado["puede_ejecutar"] is False


def test_bloquea_sin_cierre_terminal_y_lote_incompleto():
    v = venta(); m = movimiento()
    resultado = certificar_preparacion_mp(
        [v], [], [], [cierre(v, m, estado="preparado")], [lote()],
        organizacion_id=2, unidad_negocio_id=3,
    )
    assert not resultado["aprobada"]
    estados = {control["nombre"]: control["aprobado"] for control in resultado["controles"]}
    assert not estados["Integridad de lotes"]
    assert not estados["Cierre auditable"]


def test_filtra_registros_ajenos_al_tenant():
    v = venta(); m = movimiento()
    resultado = certificar_preparacion_mp(
        [v, venta(9)], [m, movimiento(9)], [],
        [cierre(v, m), cierre(v, m, tenant=9)], [lote(), lote(tenant=9)],
        organizacion_id=2, unidad_negocio_id=3,
    )
    assert resultado["resumen"]["ventas"] == 1
    assert resultado["resumen"]["movimientos"] == 1
    assert resultado["resumen"]["cierres"] == 1
    assert resultado["resumen"]["lotes"] == 1


def test_detecta_huellas_de_lote_duplicadas():
    v = venta(); m = movimiento()
    resultado = certificar_preparacion_mp(
        [v], [m], [], [cierre(v, m)], [lote(), lote()],
        organizacion_id=2, unidad_negocio_id=3,
    )
    control = next(c for c in resultado["controles"] if c["nombre"] == "Integridad de lotes")
    assert not control["aprobado"] and control["cantidad"] == 1


def test_expediente_zip_tiene_manifiesto_verificable():
    reporte = {
        "formato": "certificacion-integral-mp-v1",
        "tenant": {"organizacion_id": 2, "unidad_negocio_id": 3},
        "estado": "aprobada", "bloqueos": [], "advertencias": [],
        "resumen": {"acciones_externas": 0}, "controles": [],
        "puede_ejecutar": False,
    }
    with zipfile.ZipFile(io.BytesIO(exportar_certificacion_integral(reporte).getvalue())) as paquete:
        nombres = set(paquete.namelist())
        manifiesto = json.loads(paquete.read("manifiesto.json"))
        assert {"certificacion_integral.json", "resumen_ejecutivo.json", "LEEME.txt", "manifiesto.json"} == nombres
        for nombre, huella in manifiesto["archivos"].items():
            assert hashlib.sha256(paquete.read(nombre)).hexdigest() == huella
        assert manifiesto["acciones_externas"] == 0


def test_panel_expone_control_y_descarga_integral():
    ruta = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    html = Path("templates/admin_conciliacion_canal.html").read_text(encoding="utf-8")
    assert "certificar_preparacion_mp(" in ruta
    assert "organizacion_id=organizacion.id" in ruta
    assert 'value="exportar_certificacion_integral_mp"' in html
    assert "manifiesto SHA-256" in html


def test_servicio_es_de_solo_lectura_y_sin_transporte():
    fuente = Path("services/certificacion_integral_mp.py").read_text(encoding="utf-8").lower()
    prohibidos = (
        "db.session", "requests", "urlopen", "access_token", "client_secret",
        "http://", "https://", ".commit(", ".rollback(", ".add(", ".delete(",
    )
    assert not any(texto in fuente for texto in prohibidos)
