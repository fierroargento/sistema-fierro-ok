from types import SimpleNamespace

from services.ia_recolector_sync import (
    decidir_estado_recolector,
    resolver_requiere_operador_final_recolector,
)


def test_no_fuerza_operador_si_no_habia_lock_y_la_ia_no_lo_pide():
    pedido = SimpleNamespace(
        ia_requiere_operador=False,
        ia_recolector_estado="juntando_datos",
    )

    assert resolver_requiere_operador_final_recolector(
        pedido,
        requiere_operador=False,
    ) is False


def test_respeta_requiere_operador_detectado_por_ia():
    pedido = SimpleNamespace(
        ia_requiere_operador=False,
        ia_recolector_estado="juntando_datos",
    )

    assert resolver_requiere_operador_final_recolector(
        pedido,
        requiere_operador=True,
    ) is True


def test_no_limpia_lock_previo_por_flag_ia_requiere_operador():
    pedido = SimpleNamespace(
        ia_requiere_operador=True,
        ia_recolector_estado="requiere_operador",
    )

    assert resolver_requiere_operador_final_recolector(
        pedido,
        requiere_operador=False,
    ) is True


def test_no_limpia_lock_previo_por_estado_recolector():
    pedido = SimpleNamespace(
        ia_requiere_operador=False,
        ia_recolector_estado="requiere_operador",
    )

    assert resolver_requiere_operador_final_recolector(
        pedido,
        requiere_operador=False,
    ) is True


def test_estado_recolector_sigue_en_requiere_operador_si_habia_lock():
    pedido = SimpleNamespace(
        ia_requiere_operador=True,
        ia_recolector_estado="requiere_operador",
    )

    requiere_operador_final = resolver_requiere_operador_final_recolector(
        pedido,
        requiere_operador=False,
    )

    estado = decidir_estado_recolector(
        faltantes=["telefono"],
        requiere_operador=requiere_operador_final,
    )

    assert estado == "requiere_operador"
