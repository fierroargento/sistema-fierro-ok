import io
import json
from pathlib import Path

import pytest

from services.ensayo_respaldo_restauracion import CONJUNTOS_REQUERIDOS, ensayar, exportar, plantilla


def respaldo(org=7, unidad=3):
    return io.BytesIO(json.dumps({
        "version": 1, "organizacion_id": org, "unidad_negocio_id": unidad,
        "conjuntos": {nombre: [{"id": indice + 1, "organizacion_id": org, "unidad_negocio_id": unidad}] for indice, nombre in enumerate(CONJUNTOS_REQUERIDOS)},
    }).encode())


def test_ensaya_doce_conjuntos_y_firma_sin_restaurar():
    resultado = ensayar(respaldo(), organizacion_id=7, unidad_negocio_id=3)
    assert resultado["aprobado"] and resultado["resumen"]["conjuntos_presentes"] == 12
    assert resultado["restauracion_autorizada"] is False
    assert all(item["restaurado"] is False for item in resultado["orden_restauracion"])
    assert len(resultado["huella_ensayo_restauracion"]) == 64


def test_detecta_faltantes_duplicados_y_registros_ajenos():
    documento = json.loads(respaldo().read())
    documento["conjuntos"].pop("auditoria")
    documento["conjuntos"]["pedidos"] = [{"id": 1}, {"id": 1}, {"id": 2, "organizacion_id": 8}, {"id": 3, "unidad_negocio_id": 4}]
    resultado = ensayar(io.BytesIO(json.dumps(documento).encode()), organizacion_id=7, unidad_negocio_id=3)
    codigos = {item["codigo"] for item in resultado["hallazgos"]}
    assert {"conjunto_faltante", "ids_duplicados", "registros_otro_tenant", "registros_otra_unidad"} <= codigos


def test_ids_iguales_de_modelos_distintos_no_son_duplicados():
    documento = json.loads(respaldo().read())
    documento["conjuntos"]["catalogo"] = [
        {"id": 1, "_modelo": "Producto", "organizacion_id": 7, "unidad_negocio_id": 3},
        {"id": 1, "_modelo": "Catalogo", "organizacion_id": 7, "unidad_negocio_id": 3},
    ]
    resultado = ensayar(io.BytesIO(json.dumps(documento).encode()), organizacion_id=7, unidad_negocio_id=3)
    assert "ids_duplicados" not in {item["codigo"] for item in resultado["hallazgos"]}


def test_rechaza_tenant_unidad_formato_y_tamano():
    with pytest.raises(ValueError, match="otro tenant"):
        ensayar(respaldo(org=8), organizacion_id=7, unidad_negocio_id=3)
    with pytest.raises(ValueError, match="otra unidad"):
        ensayar(respaldo(unidad=4), organizacion_id=7, unidad_negocio_id=3)
    with pytest.raises(ValueError, match="conjuntos"):
        ensayar(io.BytesIO(b"{}"), organizacion_id=7, unidad_negocio_id=3)


def test_plantilla_y_exportacion_son_json_utf8():
    base = json.loads(plantilla(organizacion_id=7, unidad_negocio_id=3).read())
    assert set(base["conjuntos"]) == set(CONJUNTOS_REQUERIDOS)
    resultado = ensayar(respaldo(), organizacion_id=7, unidad_negocio_id=3)
    assert json.loads(exportar(resultado).read())["modo"].endswith("no_ejecutable")


def test_servicio_no_persiste_ni_conecta():
    fuente = Path("services/ensayo_respaldo_restauracion.py").read_text(encoding="utf-8").lower()
    assert not any(x in fuente for x in ("db.session", "commit(", "rollback(", "requests.", "urlopen", "http://", "https://"))
    assert '"base_restaurada": 0' in fuente and '"restauracion_autorizada": false' in fuente


def test_ruta_admin_y_panel_declaran_frontera():
    rutas = Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_ensayo_respaldo_restauracion.html").read_text(encoding="utf-8")
    assert "ensayar_respaldo(" in rutas and "resolver_acceso()" in rutas
    assert "no restaura bases ni escribe registros" in panel and "Restauración autorizada" in panel
