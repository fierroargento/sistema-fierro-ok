from services.pedidos_ui_actions import (
    inferir_tipo_accion,
    resolver_accion_ui_pedido,
    roles_habilitados_para_accion,
)


def test_infiere_accion_imprimir_etiqueta():
    assert inferir_tipo_accion("Imprimir etiqueta") == "imprimir_etiqueta"


def test_roles_imprimir_etiqueta_son_admin_despacho():
    assert roles_habilitados_para_accion("imprimir_etiqueta") == ("admin", "despacho")


def test_accion_principal_existente_queda_ejecutable():
    accion = {
        "tipo": "imprimir_etiqueta",
        "texto": "Imprimir etiqueta",
        "url": "/pedido/1/imprimir",
    }

    resultado = resolver_accion_ui_pedido(
        rol="despacho",
        accion_principal=accion,
        accion_sugerida="Imprimir etiqueta",
    )

    assert resultado["accion_real"] == "imprimir_etiqueta"
    assert resultado["texto_boton"] == "Imprimir etiqueta"
    assert resultado["puede_ejecutar"] is True
    assert resultado["accion"] == accion
    assert resultado["mensaje"] == ""


def test_accion_pendiente_sin_permiso_no_queda_como_sin_accion():
    resultado = resolver_accion_ui_pedido(
        rol="carga",
        accion_principal=None,
        accion_sugerida="Imprimir etiqueta",
    )

    assert resultado["accion_real"] == "imprimir_etiqueta"
    assert resultado["texto_boton"] == "Imprimir etiqueta"
    assert resultado["puede_ejecutar"] is False
    assert resultado["roles_habilitados"] == ["admin", "despacho"]
    assert resultado["mensaje"] == "Accion pendiente: Imprimir etiqueta. La ejecuta Despacho/Admin."


def test_accion_pendiente_con_permiso_queda_ejecutable_como_contrato():
    resultado = resolver_accion_ui_pedido(
        rol="despacho",
        accion_principal=None,
        accion_sugerida="Imprimir etiqueta",
    )

    assert resultado["accion_real"] == "imprimir_etiqueta"
    assert resultado["puede_ejecutar"] is True
    assert resultado["mensaje"] == ""


def test_sin_accion_real_y_sin_sugerida_devuelve_contrato_vacio():
    resultado = resolver_accion_ui_pedido(
        rol="carga",
        accion_principal=None,
        accion_sugerida="",
    )

    assert resultado["accion_real"] == ""
    assert resultado["texto_boton"] == ""
    assert resultado["puede_ejecutar"] is False
    assert resultado["roles_habilitados"] == []
    assert resultado["mensaje"] == ""
