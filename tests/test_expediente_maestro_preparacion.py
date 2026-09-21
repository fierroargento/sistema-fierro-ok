import hashlib
import io
import json
from pathlib import Path

import pytest

from services.expediente_maestro_preparacion import construir_expediente, exportar


def evidencia(dominio, org=7, unidad=3, aprobado=True):
    base = {"organizacion_id": org, "unidad_negocio_id": unidad, "aprobado": aprobado, "resumen": {}, "controles": {}}
    if dominio == "saas_base":
        base.update({"modo": "offline", "aprobada": aprobado, "resumen": {"componentes_identificados": 9, "componentes_requeridos": 9}})
        base.pop("aprobado")
        base.pop("unidad_negocio_id")
        huella = "huella_expediente"
    elif dominio == "compras":
        base.update({"modo": "solo_lectura", "resumen": {"recepciones": 2, "facturas": 1}}); huella = "huella_control"
    elif dominio == "produccion":
        base.update({"modo": "solo_lectura", "resumen": {"simulaciones": 2}, "controles": {"consumos": 0}}); huella = "huella_control"
    elif dominio == "tesoreria":
        base.update({"modo": "presupuesto_offline_no_ejecutable", "errores": []}); base.pop("aprobado"); huella = "huella_presupuesto"
    elif dominio == "contabilidad":
        base.update({"modo": "reportes_contables_borrador_no_oficiales"}); huella = "huella_reporte"
    elif dominio == "mantenimiento":
        base.update({"modo": "expediente_mantenimiento_no_ejecutable"}); huella = "huella_expediente"
    elif dominio == "personas":
        base.update({"modo": "expediente_personas_no_laboral"}); huella = "huella_expediente"
    elif dominio == "postventa":
        base.update({"modo": "cierre_postventa_no_ejecutable"}); huella = "huella_control"
    else:
        base.update({"modo": "expediente_transicion_dux_no_ejecutable", "decision_recomendada": "apto_para_ensayo_controlado" if aprobado else "bloqueado"}); huella = "huella_expediente_transicion"
    base[huella] = hashlib.sha256(json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return io.BytesIO(json.dumps(base).encode())


def completos():
    return [evidencia(x) for x in ("saas_base", "compras", "produccion", "tesoreria", "contabilidad", "mantenimiento", "personas", "postventa", "transicion_dux")]


def test_consolida_nueve_dominios_sin_habilitar_corte():
    resultado = construir_expediente(completos(), organizacion_id=7, unidad_negocio_id=3)
    assert resultado["estado"] == "preparado_para_revision_humana"
    assert resultado["autorizacion_corte_real"] is False
    assert resultado["resumen"]["dominios_aprobados"] == 9


def test_detecta_faltantes_no_aprobados_y_duplicados():
    resultado = construir_expediente([evidencia("compras", aprobado=False), evidencia("compras")], organizacion_id=7, unidad_negocio_id=3)
    codigos = {x["codigo"] for x in resultado["hallazgos"]}
    assert {"dominio_no_aprobado", "dominio_duplicado", "dominio_faltante"} <= codigos


def test_rechaza_tenant_unidad_y_firma_incorrectos():
    with pytest.raises(ValueError, match="otro tenant"):
        construir_expediente([evidencia("compras", org=8)], organizacion_id=7, unidad_negocio_id=3)
    with pytest.raises(ValueError, match="otra unidad"):
        construir_expediente([evidencia("compras", unidad=4)], organizacion_id=7, unidad_negocio_id=3)
    alterada = json.loads(evidencia("compras").read()); alterada["aprobado"] = False
    with pytest.raises(ValueError, match="huella digital"):
        construir_expediente([io.BytesIO(json.dumps(alterada).encode())], organizacion_id=7, unidad_negocio_id=3)


def test_transicion_exige_dependencias_y_exporta_utf8():
    resultado = construir_expediente([evidencia("transicion_dux")], organizacion_id=7, unidad_negocio_id=3)
    assert "transicion_sin_dependencias" in {x["codigo"] for x in resultado["hallazgos"]}
    assert json.loads(exportar(resultado).read())["modo"] == "expediente_maestro_preparacion_no_habilitante"


def test_limites_y_frontera_sin_efectos():
    with pytest.raises(ValueError):
        construir_expediente([], organizacion_id=7, unidad_negocio_id=3)
    fuente = Path("services/expediente_maestro_preparacion.py").read_text(encoding="utf-8").lower()
    assert not any(x in fuente for x in ("db.session", "commit(", "requests.", "urlopen", "http://", "https://"))
    assert '"autorizacion_corte_real": false' in fuente


def test_ruta_y_panel_exigen_admin_tenant():
    rutas = Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_expediente_maestro_preparacion.html").read_text(encoding="utf-8")
    assert "construir_expediente_maestro(" in rutas and "resolver_acceso()" in rutas
    assert "no autoriza el corte de DUX" in panel and "Autorización de corte real" in panel

