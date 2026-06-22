from datetime import datetime
from types import SimpleNamespace

from services.correo_recalculo_operativo import recalcular_sucursales_correo_operativo


def pedido_fake(**kwargs):
    base = {
        "empresa_envio": "Correo Argentino",
        "tipo_entrega": "Sucursal",
        "correo_sucursales_ofrecidas": """
        [
          {"id":"OLD1","nombre":"SAN MARTIN"},
          {"id":"OLD2","nombre":"TIGRE"}
        ]
        """,
        "sucursal_nombre": "SAN MARTIN",
        "ia_resumen": "Resumen previo",
        "wa_ultimo_contacto": None,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def sucursal(id_, nombre, distancia=10):
    return {
        "id": id_,
        "nombre": nombre,
        "direccion": "Calle 123",
        "localidad": nombre.title(),
        "provincia": "Buenos Aires",
        "cp": "7500",
        "distancia_km": distancia,
    }


def preferencias_fake():
    return {
        "cantidad_sucursales_cliente": 3,
    }


def test_recalcula_y_reemplaza_sucursales_ofrecidas():
    pedido = pedido_fake()

    resultado = recalcular_sucursales_correo_operativo(
        pedido,
        obtener_sucursales_fn=lambda p: [
            sucursal("TA001", "TRES ARROYOS", 62.4),
            sucursal("SC001", "SAN CAYETANO", 70.1),
        ],
        preferencias=preferencias_fake(),
        now_fn=lambda: datetime(2026, 1, 1),
    )

    assert resultado["ok"] is True
    assert "TRES ARROYOS" in pedido.correo_sucursales_ofrecidas
    assert "SAN MARTIN" not in pedido.correo_sucursales_ofrecidas
    assert pedido.empresa_envio == "Correo Argentino"
    assert pedido.tipo_entrega == "Sucursal"


def test_limpia_sucursal_previa_si_no_coincide_con_nuevo_calculo():
    pedido = pedido_fake(sucursal_nombre="SAN MARTIN")

    resultado = recalcular_sucursales_correo_operativo(
        pedido,
        obtener_sucursales_fn=lambda p: [
            sucursal("TA001", "TRES ARROYOS"),
            sucursal("SC001", "SAN CAYETANO"),
        ],
        preferencias=preferencias_fake(),
    )

    assert resultado["sucursal_limpiada"] is True
    assert pedido.sucursal_nombre == ""
    assert "Se limpió sucursal previa" in pedido.ia_resumen


def test_no_limpia_sucursal_si_sigue_en_las_opciones():
    pedido = pedido_fake(sucursal_nombre="TRES ARROYOS")

    resultado = recalcular_sucursales_correo_operativo(
        pedido,
        obtener_sucursales_fn=lambda p: [
            sucursal("TA001", "TRES ARROYOS"),
            sucursal("SC001", "SAN CAYETANO"),
        ],
        preferencias=preferencias_fake(),
    )

    assert resultado["sucursal_limpiada"] is False
    assert pedido.sucursal_nombre == "TRES ARROYOS"


def test_respeta_limite_de_preferencias():
    pedido = pedido_fake(sucursal_nombre="")

    resultado = recalcular_sucursales_correo_operativo(
        pedido,
        obtener_sucursales_fn=lambda p: [
            sucursal("1", "UNO"),
            sucursal("2", "DOS"),
            sucursal("3", "TRES"),
        ],
        preferencias={"cantidad_sucursales_cliente": 2},
    )

    assert resultado["ok"] is True
    assert len(resultado["sucursales"]) == 2


def test_sin_sucursales_deja_motivo_y_no_ok():
    pedido = pedido_fake(sucursal_nombre="SAN MARTIN")

    resultado = recalcular_sucursales_correo_operativo(
        pedido,
        obtener_sucursales_fn=lambda p: [],
        preferencias=preferencias_fake(),
    )

    assert resultado["ok"] is False
    assert resultado["motivo"] == "sin_sucursales_cercanas"
    assert pedido.correo_sucursales_ofrecidas == "[]"
