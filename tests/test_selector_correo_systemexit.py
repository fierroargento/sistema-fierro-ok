from types import SimpleNamespace

import modules.transportes.selector as selector


def test_cotizar_correo_pp6040_convierte_systemexit_en_revision_operador(monkeypatch):
    pedido = SimpleNamespace(
        codigo_postal="9000",
        cp_destino="9000",
        producto="Parrilla Camping Plegable Portatil 60 X 40 Rebatible",
        sku="PP6040H",
    )

    monkeypatch.setattr(
        selector,
        "calcular_logistica_pedido_desde_catalogo",
        lambda pedido: {
            "ok": True,
            "permite_correo": True,
            "peso_gr": 3000,
            "alto_cm": 6,
            "ancho_cm": 30,
            "largo_cm": 40,
        },
    )

    def explota(*args, **kwargs):
        raise SystemExit(1)

    monkeypatch.setattr(selector, "cotizar_correo", explota)

    resultado = selector.cotizar_correo_pp6040(pedido)

    assert resultado["ok"] is False
    assert resultado["requiere_operador"] is True
    assert resultado["tipo_error"] == selector.TIPO_ERROR_INTEGRACION
    assert resultado["motivo"] == "error_integracion_correo"
    assert "No se pudo cotizar Correo" in resultado["error"]
