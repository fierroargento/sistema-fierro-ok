from pathlib import Path
from types import SimpleNamespace

import services.workflow_confirmacion_sucursal as workflow


SUCURSALES = [
    {
        "id": "vc-1",
        "nombre": "Terminal Viedma",
        "direccion": "Ruta 3",
        "localidad": "Viedma",
        "provincia": "Rio Negro",
        "cp": "8500",
    }
]


def pedido_fake():
    return SimpleNamespace(
        id=10,
        sucursal_nombre="",
        direccion="",
        localidad="",
        provincia="",
        codigo_postal="",
        empresa_envio="",
        tipo_entrega="",
        ia_sucursales_ofrecidas='["vc-1"]',
        correo_sucursales_ofrecidas=None,
        ia_requiere_operador=True,
        ia_esperando_respuesta=True,
        ml_mensajes_pendientes=True,
        ia_resumen="Datos completos",
        ia_faltantes='["sucursal"]',
        ia_recolector_estado="juntando_datos",
        ia_ultimo_timeout_operador="pendiente",
    )


def test_confirma_sucursal_y_actualiza_recolector(
    monkeypatch,
):
    monkeypatch.setattr(
        workflow,
        "cargar_sucursales_via_cargo",
        lambda: SUCURSALES,
    )

    pedido = pedido_fake()
    logs = []

    resultado = (
        workflow
        .confirmar_sucursal_via_cargo_ofrecida_sin_persistir(
            pedido,
            "prefiero la primera",
            despacho_completo_fn=lambda _pedido: True,
            log_fn=logs.append,
        )
    )

    assert resultado is True
    assert pedido.sucursal_nombre == "Terminal Viedma"
    assert pedido.direccion == "Ruta 3"
    assert pedido.empresa_envio == "Vía Cargo"
    assert pedido.tipo_entrega == "Sucursal"
    assert pedido.ia_sucursales_ofrecidas is None
    assert pedido.ia_faltantes == "[]"
    assert (
        pedido.ia_recolector_estado
        == "datos_completos"
    )
    assert pedido.ia_ultimo_timeout_operador is None
    assert len(logs) == 1


def test_no_confirma_si_no_hay_catalogo(
    monkeypatch,
):
    monkeypatch.setattr(
        workflow,
        "cargar_sucursales_via_cargo",
        lambda: [],
    )

    pedido = pedido_fake()

    resultado = (
        workflow
        .confirmar_sucursal_via_cargo_ofrecida_sin_persistir(
            pedido,
            "opcion 1",
            despacho_completo_fn=lambda _pedido: True,
        )
    )

    assert resultado is False
    assert pedido.sucursal_nombre == ""
    assert (
        pedido.ia_sucursales_ofrecidas
        == '["vc-1"]'
    )


def test_no_reconfirma_pedido_con_sucursal(
    monkeypatch,
):
    llamadas = []

    monkeypatch.setattr(
        workflow,
        "cargar_sucursales_via_cargo",
        lambda: llamadas.append(True),
    )

    pedido = pedido_fake()
    pedido.sucursal_nombre = "Ya confirmada"

    resultado = (
        workflow
        .confirmar_sucursal_via_cargo_ofrecida_sin_persistir(
            pedido,
            "opcion 1",
            despacho_completo_fn=lambda _pedido: True,
        )
    )

    assert resultado is False
    assert llamadas == []


def test_servicio_no_persiste_ni_envia_mensajes():
    texto = Path(
        "services/workflow_confirmacion_sucursal.py"
    ).read_text(encoding="utf-8")

    prohibidos = [
        "from app import",
        "db.session",
        "ml_enviar_mensaje",
        "wa_enviar",
        "registrar_envio_automatico",
        "cross_sell",
    ]

    for prohibido in prohibidos:
        assert prohibido not in texto


def test_confirma_sucursal_unica_con_respuesta_afirmativa(
    monkeypatch,
):
    monkeypatch.setattr(
        workflow,
        "cargar_sucursales_via_cargo",
        lambda: SUCURSALES,
    )

    pedido = pedido_fake()

    resultado = (
        workflow
        .confirmar_sucursal_via_cargo_ofrecida_sin_persistir(
            pedido,
            "sí, perfecto",
            despacho_completo_fn=lambda _pedido: False,
            es_afirmativo_fn=lambda _texto: True,
            log_fn=lambda _mensaje: None,
        )
    )

    assert resultado is True
    assert pedido.sucursal_nombre == "Terminal Viedma"
    assert pedido.empresa_envio == "Vía Cargo"
    assert pedido.tipo_entrega == "Sucursal"
    assert pedido.ia_sucursales_ofrecidas is None
