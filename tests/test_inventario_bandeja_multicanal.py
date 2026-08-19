from types import SimpleNamespace
from pathlib import Path

import pytest

from services.inventario_eventos_canal import (
    preparar_sobre_evento,
    registrar_sobre_desconectado,
    resolver_identidad_cuenta,
)


def _pedido(**cambios):
    datos = {
        "id": 1204,
        "canal": "Tienda Nube",
        "tn_cuenta_id": 7,
        "tn_order_id": "TN-55",
        "id_venta": "TN-55",
        "estado": "pagado",
        "items": [SimpleNamespace(sku="PP6040H", cantidad=2)],
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def test_exige_cuenta_empresarial_exacta():
    assert resolver_identidad_cuenta(_pedido()) == ("tienda_nube", 7)
    with pytest.raises(ValueError):
        resolver_identidad_cuenta(_pedido(tn_cuenta_id=None))


def test_sobre_es_determinista_idempotente_y_desconectado():
    primero = preparar_sobre_evento(
        _pedido(), organizacion_id=3, evento_externo_id="order-paid-55",
    )
    segundo = preparar_sobre_evento(
        _pedido(), organizacion_id=3, evento_externo_id="order-paid-55",
    )
    assert primero == segundo
    assert primero["estado"] == "preparado_sin_conexion"
    assert primero["contrato"]["modo"] == "desconectado"
    assert primero["clave_idempotencia"] == "org:3:tienda_nube:7:evento:order-paid-55"


def test_despacho_parcial_y_devolucion_quedan_explicitados():
    parcial = preparar_sobre_evento(
        _pedido(), organizacion_id=3, evento_externo_id="ship-1",
        evento_externo="shipped", cantidades={"PP6040H": 1},
    )
    assert parcial["contrato"]["tipo_evento"] == "consumir"
    assert parcial["contrato"]["parcial"] is True
    devolucion = preparar_sobre_evento(
        _pedido(), organizacion_id=3, evento_externo_id="return-1",
        evento_externo="returned", cantidades={"PP6040H": 1},
    )
    assert devolucion["contrato"]["requiere_revision"] is True


def test_registro_repetido_no_duplica_y_conflicto_se_bloquea():
    sobre = preparar_sobre_evento(
        _pedido(), organizacion_id=3, evento_externo_id="paid-55",
    )
    existente = SimpleNamespace(payload_hash=sobre["payload_hash"])

    class Consulta:
        def filter_by(self, **_filtros):
            return self

        def first(self):
            return existente

    class Evento:
        query = Consulta()

    sesion = SimpleNamespace(add=lambda _e: None, commit=lambda: None)
    recuperado, creado = registrar_sobre_desconectado(
        sobre, EventoCanal=Evento, db_session=sesion,
    )
    assert recuperado is existente
    assert creado is False
    existente.payload_hash = "otro"
    with pytest.raises(ValueError):
        registrar_sobre_desconectado(
            sobre, EventoCanal=Evento, db_session=sesion,
        )


def test_app_no_conecta_bandeja_a_webhooks():
    fuente = Path("app.py").read_text(encoding="utf-8")
    assert "registrar_sobre_desconectado(" not in fuente


def test_modelo_y_panel_declaran_bandeja_auditable():
    modelo = Path("models/inventario_pedidos.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_inventario.html").read_text(encoding="utf-8")
    assert 'class EventoCanalInventario' in modelo
    assert 'uq_evento_canal_inventario_organizacion_clave' in modelo
    assert 'Bandeja multicanal desconectada' in panel
    assert 'No recibe webhooks ni ejecuta stock' in panel
