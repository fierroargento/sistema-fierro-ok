from modules.transportes import selector


class PedidoFalso:
    def __init__(self, codigo_postal="9000"):
        self.codigo_postal = codigo_postal


def test_cotizar_correo_pp6040_clasifica_error_integracion(monkeypatch):
    monkeypatch.setattr(
        selector,
        "_calcular_logistica_correo_pedido",
        lambda pedido: {
            "ok": True,
            "permite_correo": True,
            "peso_gr": 3200,
            "alto_cm": 5,
            "ancho_cm": 42,
            "largo_cm": 36,
        },
    )

    def cotizador_fake(cp, tipo_entrega="S", **kwargs):
        return {
            "disponible": False,
            "error": "No se pudo cotizar Correo Argentino.",
        }

    monkeypatch.setattr(selector, "cotizar_correo", cotizador_fake)

    resultado = selector.cotizar_correo_pp6040(PedidoFalso("9000"))

    assert resultado["ok"] is False
    assert resultado["tipo_error"] == "error_integracion"
    assert "No se pudo cotizar Correo para CP 9000" in resultado["error"]


def test_cotizar_correo_pp6040_clasifica_autenticacion(monkeypatch):
    monkeypatch.setattr(
        selector,
        "_calcular_logistica_correo_pedido",
        lambda pedido: {
            "ok": True,
            "permite_correo": True,
            "peso_gr": 3200,
            "alto_cm": 5,
            "ancho_cm": 42,
            "largo_cm": 36,
        },
    )

    monkeypatch.setattr(
        selector,
        "cotizar_correo",
        lambda *args, **kwargs: {
            "disponible": False,
            "error": "Error autenticando credenciales",
        },
    )

    resultado = selector.cotizar_correo_pp6040(PedidoFalso("9000"))

    assert resultado["ok"] is False
    assert resultado["tipo_error"] == "error_autenticacion"
    assert "autenticar" in resultado["error"]


def test_cotizar_correo_pp6040_clasifica_datos_logisticos_incompletos(monkeypatch):
    monkeypatch.setattr(
        selector,
        "_calcular_logistica_correo_pedido",
        lambda pedido: {
            "ok": False,
            "motivo": "datos_logisticos_incompletos",
            "faltantes": ["SKU SINCAT no encontrado en catálogo."],
        },
    )

    resultado = selector.cotizar_correo_pp6040(PedidoFalso("9000"))

    assert resultado["ok"] is False
    assert resultado["tipo_error"] == "datos_logisticos_incompletos"
    assert "Datos logísticos incompletos" in resultado["error"]


def test_evaluar_decision_correo_pp6040_conserva_tipo_error(monkeypatch):
    monkeypatch.setattr(
        selector,
        "cotizar_correo_pp6040",
        lambda pedido: {
            "ok": False,
            "error": "No se pudo cotizar Correo para CP 9000.",
            "tipo_error": "error_integracion",
        },
    )

    resultado = selector.evaluar_decision_correo_pp6040(PedidoFalso("9000"))

    assert resultado["decision"] == "escalar"
    assert resultado["tipo_error"] == "error_integracion"
