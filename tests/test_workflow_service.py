from types import SimpleNamespace

from domain.estados import Estado
from services.workflow import (
    actualizar_estado_automatico_service,
    aplicar_autoavance_post_despacho_service,
)


def pedido_base(**overrides):
    datos = {
        "estado": Estado.CARGANDO,
        "empresa_envio": "",
        "seguimiento": "",
        "canal": "",
        "ml_tipo": "",
    }
    datos.update(overrides)
    return SimpleNamespace(**datos)


def test_actualizar_estado_automatico_pasa_a_etiqueta_lista_si_puede_imprimir():
    pedido = pedido_base(estado=Estado.CARGANDO)

    actualizar_estado_automatico_service(
        pedido,
        puede_imprimir_etiqueta_directamente=lambda p: True,
        puede_imprimir_acordas_entrega=lambda p: False,
        debe_pasar_a_demora_entrega=lambda p: False,
    )

    assert pedido.estado == Estado.ETIQUETA_LISTA


def test_actualizar_estado_automatico_pasa_a_demora_si_corresponde():
    pedido = pedido_base(estado=Estado.DESPACHADO)

    actualizar_estado_automatico_service(
        pedido,
        puede_imprimir_etiqueta_directamente=lambda p: False,
        puede_imprimir_acordas_entrega=lambda p: False,
        debe_pasar_a_demora_entrega=lambda p: True,
    )

    assert pedido.estado == Estado.DEMORA


def test_autoavance_post_despacho_via_cargo_con_seguimiento_pasa_a_verificar_destino():
    pedido = pedido_base(
        estado=Estado.DESPACHADO,
        empresa_envio="Vía Cargo",
        seguimiento="ABC123",
    )

    aplicar_autoavance_post_despacho_service(pedido)

    assert pedido.estado == Estado.VERIFICAR_DESTINO


def test_autoavance_post_despacho_via_cargo_sin_seguimiento_no_avanza():
    pedido = pedido_base(
        estado=Estado.DESPACHADO,
        empresa_envio="Vía Cargo",
        seguimiento="",
    )

    aplicar_autoavance_post_despacho_service(pedido)

    assert pedido.estado == Estado.DESPACHADO


def test_autoavance_post_despacho_ml_acordas_andreani_con_seguimiento_pasa_a_verificar_destino():
    pedido = pedido_base(
        estado=Estado.DESPACHADO,
        canal="Mercado Libre",
        ml_tipo="Acordás la Entrega",
        empresa_envio="Andreani",
        seguimiento="AND123",
    )

    aplicar_autoavance_post_despacho_service(pedido)

    assert pedido.estado == Estado.VERIFICAR_DESTINO


def test_autoavance_post_despacho_no_toca_pedido_que_no_esta_despachado():
    pedido = pedido_base(
        estado=Estado.EMBALADO,
        empresa_envio="Vía Cargo",
        seguimiento="ABC123",
    )

    aplicar_autoavance_post_despacho_service(pedido)

    assert pedido.estado == Estado.EMBALADO

def test_autoavance_post_despacho_ml_acordas_correo_con_seguimiento_pasa_a_verificar_destino():
    pedido = pedido_base(
        estado=Estado.DESPACHADO,
        canal="Mercado Libre",
        ml_tipo="Acordás la Entrega",
        empresa_envio="Correo Argentino",
        seguimiento="COR123",
    )

    aplicar_autoavance_post_despacho_service(pedido)

    assert pedido.estado == Estado.VERIFICAR_DESTINO


def test_actualizar_estado_automatico_pasa_a_etiqueta_lista_si_puede_imprimir_acordas():
    pedido = pedido_base(estado=Estado.CARGANDO)

    actualizar_estado_automatico_service(
        pedido,
        puede_imprimir_etiqueta_directamente=lambda p: False,
        puede_imprimir_acordas_entrega=lambda p: True,
        debe_pasar_a_demora_entrega=lambda p: False,
    )

    assert pedido.estado == Estado.ETIQUETA_LISTA    