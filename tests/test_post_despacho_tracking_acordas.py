from pathlib import Path


def test_post_despacho_tracking_externo_solo_acciona_en_ml_acordas():
    texto = Path("modules/whatsapp/post_despacho.py").read_text(encoding="utf-8")

    assert "def _es_ml_acordas_tracking(pedido):" in texto
    assert 'getattr(pedido, "canal", "")' in texto
    assert 'getattr(pedido, "ml_tipo", "")' in texto
    assert "Acordás la Entrega" in texto
    assert 'clasificacion in ["sucursal", "entregado"]' in texto
    assert "not _es_ml_acordas_tracking(pedido)" in texto
    assert 'acciones.append("tracking_informativo_sin_accion")' in texto
    assert "Mercado Envíos, Tienda Nube y otros canales" in texto
