from pathlib import Path
from types import SimpleNamespace

from services.identidad_tenant_pedidos import (
    diagnosticar_identidad_tenant_pedidos,
)


def _objeto(**datos):
    return SimpleNamespace(**datos)


def test_diagnostico_distingue_inferible_pendiente_y_ambiguo():
    vinculos = [
        _objeto(id=1, organizacion_id=10, unidad_negocio_id=100,
                mercado_libre_cuenta_id=5, tienda_nube_cuenta_id=None),
        _objeto(id=2, organizacion_id=20, unidad_negocio_id=200,
                mercado_libre_cuenta_id=None, tienda_nube_cuenta_id=8),
    ]
    pedidos = [
        _objeto(id=1, organizacion_id=None, unidad_negocio_id=None,
                ml_cuenta_id=5, tn_cuenta_id=None),
        _objeto(id=2, organizacion_id=None, unidad_negocio_id=None,
                ml_cuenta_id=None, tn_cuenta_id=None),
        _objeto(id=3, organizacion_id=None, unidad_negocio_id=None,
                ml_cuenta_id=5, tn_cuenta_id=8),
    ]
    resultado = diagnosticar_identidad_tenant_pedidos(pedidos, vinculos)
    assert resultado["inferibles"] == 1
    assert resultado["pendientes"] == 1
    assert resultado["ambiguos"] == 1
    assert resultado["escrituras_realizadas"] == 0
    assert resultado["integraciones_habilitables"] is False


def test_identidad_explicita_con_cuenta_distinta_es_conflicto():
    pedido = _objeto(
        id=4, organizacion_id=99, unidad_negocio_id=999,
        ml_cuenta_id=5, tn_cuenta_id=None,
    )
    vinculo = _objeto(
        id=1, organizacion_id=10, unidad_negocio_id=100,
        mercado_libre_cuenta_id=5, tienda_nube_cuenta_id=None,
    )
    resultado = diagnosticar_identidad_tenant_pedidos([pedido], [vinculo])
    assert resultado["conflictos"] == 1
    assert resultado["aprobada"] is False


def test_migracion_es_nullable_y_no_hace_backfill():
    migraciones = Path("services/migraciones_saas.py").read_text(encoding="utf-8")
    modelo = Path("models/pedido.py").read_text(encoding="utf-8")
    assert "def asegurar_identidad_tenant_pedido_preparatoria(" in migraciones
    assert '"organizacion_id": "INTEGER"' in migraciones
    assert "organizacion_id = db.Column(" in modelo
    assert "nullable=True" in modelo


def test_contrato_no_conecta_canales_ni_escribe_pedidos():
    servicio = Path("services/identidad_tenant_pedidos.py").read_text(encoding="utf-8")
    for prohibido in (
        "requests", "oauth", "webhook", "access_token",
        "db.session.add", ".commit(", ".delete(",
    ):
        assert prohibido not in servicio.lower()
