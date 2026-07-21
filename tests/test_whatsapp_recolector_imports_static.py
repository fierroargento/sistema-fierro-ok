from pathlib import Path


def test_whatsapp_consulta_faltantes_sin_importar_app():
    texto = Path(
        "modules/whatsapp/flows.py"
    ).read_text(encoding="utf-8")

    assert texto.count(
        "from services.ia_recolector_sync import ("
    ) >= 2
    assert texto.count(
        "faltantes_pedido_recolector(pedido)"
    ) == 2

    assert (
        "from app import  ia_faltantes_pedido"
        not in texto
    )
    assert (
        "ia_guardar_resultado_recolector, "
        "ia_faltantes_pedido"
        not in texto
    )


def test_datos_previos_recolector_no_dependen_de_app():
    app = Path("app.py").read_text(encoding="utf-8")
    flows = Path(
        "modules/whatsapp/flows.py"
    ).read_text(encoding="utf-8")

    assert "def ia_datos_previos_pedido(" not in app
    assert "ia_datos_previos_pedido" not in flows

    assert app.count(
        "datos_previos_pedido_recolector("
    ) == 2
    assert flows.count(
        "datos_previos_pedido_recolector("
    ) == 1

    assert (
        "parece_nickname_fn=parece_nickname_ml"
        in app
    )
    assert (
        "parece_nickname_fn=parece_nickname_ml"
        in flows
    )
