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
