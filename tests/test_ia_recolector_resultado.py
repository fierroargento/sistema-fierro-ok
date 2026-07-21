import hashlib
import json
from types import SimpleNamespace

from services.ia_recolector_resultado import (
    aplicar_resultado_recolector,
)


def pedido_fake(**cambios):
    datos = {
        "id": 10,
        "cliente": "",
        "ml_buyer_nickname": "",
        "ml_billing_documento": "",
        "dni": "",
        "telefono": "",
        "direccion": "",
        "localidad": "",
        "provincia": "",
        "codigo_postal": "",
        "autorizado_nombre": "",
        "autorizado_dni": "",
        "autorizado_telefono": "",
        "ia_datos_detectados": "{}",
        "ia_recolector_estado": "",
        "ia_requiere_operador": False,
        "ia_ultimo_timeout_operador": "pendiente",
        "ia_error": "",
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def dependencias(**cambios):
    valores = {
        "parece_nickname_fn": (
            lambda _cliente, _nickname: False
        ),
        "es_ml_acordas_entrega_fn": (
            lambda _pedido: False
        ),
        "pedido_es_plegable_pp6040_fn": (
            lambda _pedido: False
        ),
        "ahora_fn": lambda: "AHORA",
        "log_fn": lambda _mensaje: None,
    }
    valores.update(cambios)
    return valores


def test_aplica_resultado_y_devuelve_handoff_pendiente():
    pedido = pedido_fake()

    resultado = aplicar_resultado_recolector(
        pedido,
        "Soy Juan",
        {
            "ok": True,
            "datos": {
                "nombre": "Juan",
                "apellido": "Pérez",
            },
            "resumen": "Datos parciales",
            "requiere_operador": False,
        },
        **dependencias(),
    )

    assert resultado.aplicado is True
    assert resultado.exitoso is True
    assert resultado.estado == "juntando_datos"
    assert resultado.iniciar_handoff is True
    assert "telefono" in resultado.faltantes
    assert resultado.completados == ("cliente",)

    assert pedido.ia_ultimo_analisis == "AHORA"
    assert pedido.ia_ultimo_mensaje_hash == (
        hashlib.sha256(
            b"Soy Juan"
        ).hexdigest()
    )
    assert pedido.ia_recolector_estado == (
        "juntando_datos"
    )
    assert pedido.ia_requiere_operador is False
    assert "IA autocompletó: cliente" in (
        pedido.ia_resumen
    )


def test_resultado_invalido_marca_error_sin_autocompletar():
    pedido = pedido_fake()

    resultado = aplicar_resultado_recolector(
        pedido,
        "mensaje",
        {
            "ok": False,
            "estado": "error_ia",
            "error": "falló proveedor",
        },
        **dependencias(),
    )

    assert resultado.exitoso is False
    assert resultado.motivo == "resultado_invalido"
    assert pedido.ia_recolector_estado == "error_ia"
    assert pedido.ia_error == "falló proveedor"
    assert pedido.cliente == ""


def test_respeta_lock_previo_de_operador():
    pedido = pedido_fake(
        ia_recolector_estado="requiere_operador",
        ia_requiere_operador=True,
    )

    resultado = aplicar_resultado_recolector(
        pedido,
        "dato adicional",
        {
            "ok": True,
            "datos": {},
            "requiere_operador": False,
        },
        **dependencias(),
    )

    assert resultado.requiere_operador is True
    assert resultado.estado == "requiere_operador"
    assert resultado.iniciar_handoff is False
    assert pedido.ia_requiere_operador is True


def test_reencauza_pp6040_completo_sin_motivo_duro():
    pedido = pedido_fake(
        cliente="Juan Pérez",
        dni="30111222",
        telefono="2920123456",
        direccion="Mitre 500",
        codigo_postal="8500",
        ia_recolector_estado="requiere_operador",
        ia_requiere_operador=True,
    )

    resultado = aplicar_resultado_recolector(
        pedido,
        "datos completos",
        {
            "ok": True,
            "datos": {},
            "resumen": "Datos completos",
            "requiere_operador": True,
        },
        **dependencias(
            es_ml_acordas_entrega_fn=(
                lambda _pedido: True
            ),
            pedido_es_plegable_pp6040_fn=(
                lambda _pedido: True
            ),
        ),
    )

    assert resultado.faltantes == ()
    assert resultado.requiere_operador is False
    assert resultado.estado == "datos_completos"
    assert resultado.iniciar_handoff is False
    assert pedido.ia_requiere_operador is False
    assert pedido.ia_ultimo_timeout_operador is None


def test_persiste_datos_y_faltantes_como_json():
    pedido = pedido_fake(
        cliente="Juan Pérez",
        dni="30111222",
        telefono="2920123456",
        direccion="Mitre 500",
        codigo_postal="8500",
    )

    resultado = aplicar_resultado_recolector(
        pedido,
        "todo listo",
        {
            "ok": True,
            "datos": {
                "nombre": "Juan",
                "apellido": "Pérez",
            },
        },
        **dependencias(),
    )

    assert resultado.estado == "datos_completos"
    assert json.loads(
        pedido.ia_datos_detectados
    )["nombre"] == "Juan"
    assert json.loads(pedido.ia_faltantes) == []


def test_sin_pedido_no_invoca_dependencias():
    resultado = aplicar_resultado_recolector(
        None,
        "mensaje",
        {"ok": True},
        **dependencias(),
    )

    assert resultado.aplicado is False
    assert resultado.estado == "no_pedido"


def test_servicio_no_ejecuta_efectos_externos():
    from pathlib import Path

    texto = Path(
        "services/ia_recolector_resultado.py"
    ).read_text(encoding="utf-8")

    prohibidos = [
        "from app import",
        "import app",
        "db.session",
        "wa_auto_iniciar",
        "ml_enviar_mensaje",
        "registrar_envio_automatico",
        "cross_sell",
    ]

    for prohibido in prohibidos:
        assert prohibido not in texto


def test_aplicador_consume_primitivas_centralizadas_sin_inyeccion():
    from pathlib import Path

    servicio = Path(
        "services/ia_recolector_resultado.py"
    ).read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")

    assert (
        "from services.ia_recolector_datos import ("
        in servicio
    )
    assert "normalizar_datos_ia_fierro(" in servicio
    assert (
        "ia_extraer_datos_clasico_fierro("
        in servicio
    )
    assert (
        "ia_autocompletar_pedido_con_datos("
        in servicio
    )

    prohibidos = [
        "normalizar_datos_fn",
        "extraer_datos_clasicos_fn",
        "autocompletar_pedido_fn",
    ]

    for prohibido in prohibidos:
        assert prohibido not in servicio
        assert prohibido not in app
