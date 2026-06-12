from types import SimpleNamespace

from services.pedidos_acciones import debe_mostrar_accion_completar_carga


def pedido(estado="Cargando Pedido"):
    return SimpleNamespace(estado=estado)


def test_completar_carga_si_tienda_nube_necesita_carga():
    assert debe_mostrar_accion_completar_carga(
        pedido("Cargando Pedido"),
        necesita_completar_carga_tn=True,
        requiere_contacto=False,
        estados_post_despacho=[],
        estados_despacho_operativo=[],
    )


def test_completar_carga_si_requiere_contacto_y_no_esta_en_estado_posterior():
    assert debe_mostrar_accion_completar_carga(
        pedido("Cargando Pedido"),
        necesita_completar_carga_tn=False,
        requiere_contacto=True,
        estados_post_despacho=["Despachado"],
        estados_despacho_operativo=["Etiqueta Impresa", "Embalado"],
    )


def test_no_completar_carga_si_requiere_contacto_pero_esta_entregado():
    assert not debe_mostrar_accion_completar_carga(
        pedido("Entregado"),
        necesita_completar_carga_tn=False,
        requiere_contacto=True,
        estados_post_despacho=["Despachado"],
        estados_despacho_operativo=["Etiqueta Impresa", "Embalado"],
    )


def test_no_completar_carga_si_no_hay_faltantes():
    assert not debe_mostrar_accion_completar_carga(
        pedido("Cargando Pedido"),
        necesita_completar_carga_tn=False,
        requiere_contacto=False,
        estados_post_despacho=[],
        estados_despacho_operativo=[],
    )
