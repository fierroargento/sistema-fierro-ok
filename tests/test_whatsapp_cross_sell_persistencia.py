from types import SimpleNamespace

from modules.whatsapp import cross_sell


class SessionFake:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def pedido_fake():
    return SimpleNamespace(
        id=123,
        ia_resumen="Resumen previo",
        ml_mensajes_pendientes=False,
        ia_requiere_operador=False,
    )


def test_venta_cerrada_actualiza_pedido_y_persiste(
    monkeypatch,
):
    session = SessionFake()
    pedido = pedido_fake()

    monkeypatch.setattr(
        cross_sell,
        "db",
        SimpleNamespace(session=session),
    )
    monkeypatch.setattr(
        cross_sell,
        "obtener_producto",
        lambda sku: {
            "nombre": "Kit pala y atizador",
            "precio": 15000,
        },
    )

    cross_sell.wa_escalar_venta_cerrada(
        pedido,
        "KITPACH",
        2,
    )

    assert session.commits == 1
    assert pedido.ml_mensajes_pendientes is True
    assert pedido.ia_requiere_operador is True
    assert "Resumen previo" in pedido.ia_resumen
    assert "Kit pala y atizador" in pedido.ia_resumen
    assert "x2" in pedido.ia_resumen
    assert "$30,000" in pedido.ia_resumen


def test_cross_sell_usa_extension_canonica_db():
    from pathlib import Path

    texto = Path(
        "modules/whatsapp/cross_sell.py"
    ).read_text(encoding="utf-8-sig")

    assert texto.count(
        "from extensions import db"
    ) == 1
    assert "from app import db" not in texto
    assert texto.count(
        "db.session.commit()"
    ) == 1
