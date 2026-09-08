from pathlib import Path
from types import SimpleNamespace

from services.certificacion_whatsapp_tenant import (
    certificar_coleccion_whatsapp_tenant,
)


def test_certificacion_aprueba_mensajes_aislados():
    resultado = certificar_coleccion_whatsapp_tenant(
        10,
        [SimpleNamespace(id=1, organizacion_id=10, unidad_negocio_id=100, pedido_id=5)],
        [SimpleNamespace(id=100, organizacion_id=10)],
        [SimpleNamespace(id=5, organizacion_id=10)],
    )
    assert resultado["aprobada"] is True
    assert resultado["mensajes_tenant"] == 1
    assert resultado["escrituras_realizadas"] == 0
    assert resultado["integraciones_habilitables"] is False


def test_certificacion_detecta_legacy_y_relaciones_cruzadas():
    resultado = certificar_coleccion_whatsapp_tenant(
        10,
        [
            SimpleNamespace(id=1, organizacion_id=None, unidad_negocio_id=None, pedido_id=None),
            SimpleNamespace(id=2, organizacion_id=10, unidad_negocio_id=None, pedido_id=None),
            SimpleNamespace(id=3, organizacion_id=10, unidad_negocio_id=200, pedido_id=8),
        ],
        [SimpleNamespace(id=200, organizacion_id=20)],
        [SimpleNamespace(id=8, organizacion_id=20)],
    )
    assert resultado["aprobada"] is False
    assert resultado["sin_organizacion"] == 1
    assert resultado["sin_unidad"] == 1
    assert resultado["unidad_cruzada"] == 1
    assert resultado["pedido_cruzado"] == 1


def test_panel_expone_certificacion_sin_habilitar_canales():
    consultas = Path("services/estructura_consultas.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_estructura.html").read_text(encoding="utf-8")
    assert "certificar_whatsapp_tenant(" in consultas
    assert '"certificacion_whatsapp"' in consultas
    assert "certificacion_whatsapp.aprobada" in panel
    assert "Legacy sin tenant" in panel
    assert "procesa webhooks" in panel
