from types import SimpleNamespace

import modules.whatsapp.router as router
from modules.whatsapp.config import (
    WA_ESPERANDO_DATOS,
    WA_ESPERANDO_OK_INICIO,
    WA_ESPERANDO_CONFIRMACION_SUCURSAL,
    WA_LISTO_PARA_RETIRAR,
    WA_POSTVENTA,
    WA_CROSS_SELL_CERRADO,
)


def pedido_base(**overrides):
    datos = {
        "wa_estado": "",
        "wa_paso_operativo": "",
        "telefono": "+5492920123456",
        "ml_mensajes_pendientes": False,
        "ml_mensajes_pendientes_count": 0,
        "ia_requiere_operador": False,
    }
    datos.update(overrides)
    return SimpleNamespace(**datos)


def estado(pedido):
    return pedido.wa_estado or ""


def test_router_esperando_ok_inicio_deriva_a_ok(monkeypatch):
    pedido = pedido_base(wa_estado=WA_ESPERANDO_OK_INICIO)
    llamado = {}

    monkeypatch.setattr(
        router,
        "wa_procesar_ok_inicio",
        lambda p, texto: llamado.update({"pedido": p, "texto": texto}),
    )

    router.routear_mensaje(pedido, "ok", "5492920123456", estado)

    assert llamado["pedido"] is pedido
    assert llamado["texto"] == "ok"


def test_router_esperando_datos_deriva_a_recolector(monkeypatch):
    pedido = pedido_base(wa_estado=WA_ESPERANDO_DATOS)
    llamado = {}

    monkeypatch.setattr(
        router,
        "wa_procesar_datos_recibidos",
        lambda p, texto: llamado.update({"pedido": p, "texto": texto}),
    )

    router.routear_mensaje(pedido, "mi dni es 12345678", "5492920123456", estado)

    assert llamado["pedido"] is pedido
    assert llamado["texto"] == "mi dni es 12345678"


def test_router_confirmacion_sucursal_deriva_a_confirmacion(monkeypatch):
    pedido = pedido_base(wa_estado=WA_ESPERANDO_CONFIRMACION_SUCURSAL)
    llamado = {}

    monkeypatch.setattr(
        router,
        "wa_procesar_respuesta_confirmacion",
        lambda p, texto: llamado.update({"pedido": p, "texto": texto}),
    )

    router.routear_mensaje(pedido, "sí", "5492920123456", estado)

    assert llamado["pedido"] is pedido
    assert llamado["texto"] == "sí"


def test_router_listo_para_retirar_escala_operador(monkeypatch):
    pedido = pedido_base(wa_estado=WA_LISTO_PARA_RETIRAR)
    llamado = {}

    monkeypatch.setattr(
        router,
        "_escalar_operador",
        lambda p, motivo, mensaje_cliente=None: llamado.update(
            {
                "pedido": p,
                "motivo": motivo,
                "mensaje_cliente": mensaje_cliente,
            }
        ),
    )

    router.routear_mensaje(pedido, "puedo ir ahora?", "5492920123456", estado)

    assert llamado["pedido"] is pedido
    assert "aviso de retiro" in llamado["motivo"]
    assert llamado["mensaje_cliente"] == "puedo ir ahora?"


def test_router_cross_sell_deriva_con_sku_e_indice(monkeypatch):
    pedido = pedido_base(wa_estado="cross_sell:BPPC01:0")
    llamado = {}

    monkeypatch.setattr(
        router,
        "wa_procesar_respuesta_cross_sell",
        lambda p, texto, sku, indice: llamado.update(
            {
                "pedido": p,
                "texto": texto,
                "sku": sku,
                "indice": indice,
            }
        ),
    )

    router.routear_mensaje(pedido, "precio?", "5492920123456", estado)

    assert llamado["pedido"] is pedido
    assert llamado["texto"] == "precio?"
    assert llamado["sku"] == "BPPC01"
    assert llamado["indice"] == 0


def test_router_postventa_deriva_a_postventa(monkeypatch):
    pedido = pedido_base(wa_estado=WA_POSTVENTA)
    llamado = {}

    monkeypatch.setattr(
        router,
        "wa_procesar_respuesta_postventa",
        lambda p, texto: llamado.update({"pedido": p, "texto": texto}),
    )

    router.routear_mensaje(pedido, "gracias", "5492920123456", estado)

    assert llamado["pedido"] is pedido
    assert llamado["texto"] == "gracias"


class SessionFake:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def test_router_operador_manual_marca_pendiente_y_persiste(
    monkeypatch,
):
    session = SessionFake()
    pedido = pedido_base(
        wa_estado="operador_manual",
        ml_mensajes_pendientes=False,
        ml_mensajes_pendientes_count=2,
        ia_requiere_operador=False,
    )

    monkeypatch.setattr(
        router,
        "db",
        SimpleNamespace(session=session),
    )

    router.routear_mensaje(
        pedido,
        "Necesito ayuda",
        "5492920123456",
        estado,
    )

    assert session.commits == 1
    assert pedido.ml_mensajes_pendientes is True
    assert pedido.ml_mensajes_pendientes_count == 3
    assert pedido.ia_requiere_operador is True


def test_router_usa_extension_canonica_para_db():
    from pathlib import Path

    texto = Path(
        "modules/whatsapp/router.py"
    ).read_text(encoding="utf-8-sig")

    assert texto.count(
        "from extensions import db"
    ) == 1
    assert "from app import db" not in texto
    assert (
        "from models.whatsapp_mensaje import "
        "WhatsAppMensaje"
        in texto
    )
    assert (
        "from models.pedido import Pedido"
        in texto
    )
    assert "from app import Pedido" not in texto
