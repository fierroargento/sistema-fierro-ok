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

    aplicador = Path(
        "services/ia_recolector_resultado.py"
    ).read_text(encoding="utf-8")

    assert app.count(
        "datos_previos_pedido_recolector("
    ) == 1
    assert aplicador.count(
        "datos_previos_pedido_recolector("
    ) == 1
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


def test_whatsapp_procesa_resultado_sin_handoff_redundante():
    app = Path("app.py").read_text(encoding="utf-8")
    flows = Path(
        "modules/whatsapp/flows.py"
    ).read_text(encoding="utf-8")

    assert (
        "def ia_guardar_resultado_recolector("
        not in app
    )
    assert (
        "procesar_resultado_recolector("
        in flows
    )

    inicio = flows.index(
        "def wa_procesar_datos_recibidos("
    )
    fin = flows.index(
        "\ndef ",
        inicio + 1,
    )
    bloque = flows[inicio:fin]

    assert "iniciar_handoff_fn=" not in bloque
    assert (
        "wa_auto_iniciar_desde_ml_si_corresponde"
        not in bloque
    )
    assert "from app import db" in bloque


def test_whatsapp_analiza_recolector_sin_importarlo_desde_app():
    flows = Path(
        "modules/whatsapp/flows.py"
    ).read_text(encoding="utf-8")

    assert (
        "from services.ia_recolector_analisis import ("
        in flows
    )
    assert (
        "analizar_datos_cliente_ml_acordas("
        in flows
    )
    assert (
        "ia_analizar_datos_cliente_ml_acordas"
        not in flows
    )
