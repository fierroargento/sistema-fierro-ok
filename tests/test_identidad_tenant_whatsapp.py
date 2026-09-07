from pathlib import Path
from types import SimpleNamespace

from services.identidad_tenant_whatsapp import diagnosticar_identidad_tenant_whatsapp


def test_diagnostico_separa_asignados_inferibles_pendientes_y_conflictos():
    pedidos = [SimpleNamespace(id=1, organizacion_id=10, unidad_negocio_id=11)]
    mensajes = [
        SimpleNamespace(id=1, pedido_id=1, organizacion_id=10, unidad_negocio_id=11),
        SimpleNamespace(id=2, pedido_id=1, organizacion_id=None, unidad_negocio_id=None),
        SimpleNamespace(id=3, pedido_id=None, organizacion_id=None, unidad_negocio_id=None),
        SimpleNamespace(id=4, pedido_id=1, organizacion_id=20, unidad_negocio_id=21),
    ]
    resultado = diagnosticar_identidad_tenant_whatsapp(mensajes, pedidos)
    assert resultado["asignados"] == 1
    assert resultado["inferibles_por_pedido"] == 1
    assert resultado["pendientes"] == 1
    assert resultado["conflictos"] == 1
    assert resultado["escrituras_realizadas"] == 0
    assert resultado["integraciones_habilitables"] is False


def test_migracion_es_nullable_y_no_hace_backfill():
    texto = Path("services/migraciones_saas.py").read_text(encoding="utf-8")
    inicio = texto.index("def asegurar_identidad_tenant_whatsapp_preparatoria(")
    fin = texto.index("\ndef asegurar_ficha_catalogo_integral(", inicio)
    bloque = texto[inicio:fin]
    assert "ADD COLUMN {nombre} INTEGER" in bloque
    assert "UPDATE whatsapp_mensaje" not in bloque
    assert "NOT NULL" not in bloque


def test_modelo_declara_identidad_tenant_opcional():
    texto = Path("models/whatsapp_mensaje.py").read_text(encoding="utf-8")
    assert 'db.ForeignKey("organizacion.id")' in texto
    assert 'db.ForeignKey("unidad_negocio.id")' in texto
    assert texto.count("nullable=True") >= 2


def test_diagnostico_no_infiere_por_telefono():
    texto = Path("services/identidad_tenant_whatsapp.py").read_text(encoding="utf-8").lower()
    assert "telefono" not in texto
    for prohibido in ("db.session", "requests", "oauth", "access_token", "webhook"):
        assert prohibido not in texto
