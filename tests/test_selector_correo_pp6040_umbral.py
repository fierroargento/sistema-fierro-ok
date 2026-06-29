from pathlib import Path


def test_selector_pp6040_valida_umbral_antes_de_ofrecer_sucursales():
    texto = Path("modules/transportes/selector.py").read_text(encoding="utf-8")

    assert "evaluar_oferta_sucursales_correo_pp6040" in texto
    assert "cotizar_correo_pp6040(pedido)" in texto
    assert "pedido_contiene_pp6040(pedido)" in texto
    assert 'decision_sucursal.get("ofrecer_sucursales")' in texto
    assert "Precio Correo sucursal" in texto
    assert "No se pudo validar costo Correo sucursal PP6040" in texto


def test_selector_pp6040_supera_umbral_no_busca_sucursales(monkeypatch):
    from modules.transportes import selector
    from services import correo_argentino_operacion as operacion

    class PedidoFake:
        pass

    llamadas = {}

    monkeypatch.setattr(selector, "correo_pp6040_habilitado", lambda: True)
    monkeypatch.setattr(selector, "pedido_contiene_pp6040", lambda pedido: True)
    monkeypatch.setattr(
        selector,
        "cotizar_correo_pp6040",
        lambda pedido: {"ok": True, "sucursal": {"disponible": True, "precio": 12000}},
    )
    monkeypatch.setattr(
        operacion,
        "evaluar_oferta_sucursales_correo_pp6040",
        lambda sucursal, **kwargs: {
            "ofrecer_sucursales": False,
            "requiere_operador": True,
            "motivo": "Correo sucursal PP6040 supera el umbral; revisar operador.",
            "precio": 12000,
            "umbral": 10000,
        },
    )

    def no_debe_buscar_sucursales(pedido):
        raise AssertionError("No debería buscar sucursales si supera el umbral")

    monkeypatch.setattr(selector, "obtener_sucursales_correo_por_pedido", no_debe_buscar_sucursales)
    monkeypatch.setattr(
        selector,
        "_marcar_escalado",
        lambda pedido, motivo: llamadas.setdefault("motivo", motivo),
    )

    respuesta = selector.sugerir_sucursales_correo_pedido(PedidoFake())

    assert respuesta is None
    assert "supera el umbral" in llamadas["motivo"]
    assert "12000" in llamadas["motivo"]
    assert "10000" in llamadas["motivo"]
