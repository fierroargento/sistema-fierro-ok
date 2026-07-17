from pathlib import Path


def test_app_usa_servicio_puro_para_telefono_tiendanube():
    contenido = Path("app.py").read_text(
        encoding="utf-8-sig",
        errors="replace",
    )

    assert (
        "from services.tiendanube_datos import "
        "extraer_telefono_tiendanube_service"
    ) in contenido

    assert "pedido.telefono = extraer_telefono_tiendanube_service(" in contenido

    assert (
        'pedido.telefono = str(order.get("contact_phone")'
        not in contenido
    )
