from pathlib import Path
from types import SimpleNamespace

from services.certificacion_pedidos_tenant import (
    certificar_coleccion_pedidos_tenant,
)


def test_certificacion_aprueba_coleccion_aislada():
    resultado = certificar_coleccion_pedidos_tenant(
        10,
        [SimpleNamespace(id=1, organizacion_id=10, unidad_negocio_id=100)],
        [SimpleNamespace(id=100, organizacion_id=10)],
    )
    assert resultado["aprobada"] is True
    assert resultado["pedidos_tenant"] == 1
    assert resultado["escrituras_realizadas"] == 0
    assert resultado["integraciones_habilitables"] is False


def test_certificacion_detecta_legacy_y_relaciones_cruzadas():
    resultado = certificar_coleccion_pedidos_tenant(
        10,
        [
            SimpleNamespace(id=1, organizacion_id=None, unidad_negocio_id=None),
            SimpleNamespace(id=2, organizacion_id=10, unidad_negocio_id=None),
            SimpleNamespace(id=3, organizacion_id=10, unidad_negocio_id=200),
            SimpleNamespace(id=4, organizacion_id=20, unidad_negocio_id=200),
        ],
        [SimpleNamespace(id=200, organizacion_id=20)],
    )
    assert resultado["aprobada"] is False
    assert resultado["sin_organizacion"] == 1
    assert resultado["sin_unidad"] == 1
    assert resultado["unidad_cruzada"] == 1
    assert len(resultado["bloqueos"]) == 3


def test_panel_expone_certificacion_sin_habilitar_integraciones():
    consultas = Path("services/estructura_consultas.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_estructura.html").read_text(encoding="utf-8")
    assert "certificar_pedidos_tenant(" in consultas
    assert '"certificacion_pedidos"' in consultas
    assert "certificacion_pedidos.aprobada" in panel
    assert "Legacy sin tenant" in panel
    assert "integraciones_habilitables" not in panel
