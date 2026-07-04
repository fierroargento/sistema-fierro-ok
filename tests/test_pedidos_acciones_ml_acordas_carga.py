from types import SimpleNamespace

from services.pedidos_acciones import (
    debe_mostrar_accion_completar_carga,
    necesita_completar_carga_etiqueta_o_seguimiento,
)


def pedido_base(**kwargs):
    data = {
        "estado": "Cargando Pedido",
        "canal": "Mercado Libre",
        "ml_tipo": "Acordas la Entrega",
        "empresa_envio": "Correo Argentino",
        "etiqueta_archivo": "",
        "seguimiento": "",
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_ml_acordas_correo_sin_etiqueta_y_sin_seguimiento_necesita_completar_carga():
    pedido = pedido_base()

    assert necesita_completar_carga_etiqueta_o_seguimiento(pedido) is True
    assert debe_mostrar_accion_completar_carga(pedido) is True


def test_ml_acordas_correo_con_etiqueta_pero_sin_seguimiento_necesita_completar_carga():
    pedido = pedido_base(etiqueta_archivo="etiqueta.pdf", seguimiento="")

    assert necesita_completar_carga_etiqueta_o_seguimiento(pedido) is True
    assert debe_mostrar_accion_completar_carga(pedido) is True


def test_ml_acordas_correo_completo_no_necesita_completar_carga():
    pedido = pedido_base(etiqueta_archivo="etiqueta.pdf", seguimiento="TRK123")

    assert necesita_completar_carga_etiqueta_o_seguimiento(pedido) is False


def test_via_cargo_no_entra_en_regla_de_etiqueta_seguimiento():
    pedido = pedido_base(empresa_envio="Via Cargo")

    assert necesita_completar_carga_etiqueta_o_seguimiento(pedido) is False
