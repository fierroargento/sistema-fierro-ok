from types import SimpleNamespace

import pytest

from services.ml_cuentas import (
    MLCuentaAmbigua,
    MLCuentaInconsistente,
    MLCuentaNoAsignada,
    MLCuentaNoConfigurada,
    MLCuentaNoEncontrada,
    cuenta_default,
    cuenta_por_pedido,
    cuenta_por_seller_id,
    cuentas_activas,
    seller_id_pedido,
)


class QueryFake:
    def __init__(self, cuentas):
        self.cuentas = list(cuentas)
        self.filtros = {}

    def all(self):
        if not self.filtros:
            return list(self.cuentas)

        salida = []
        for cuenta in self.cuentas:
            ok = True
            for campo, esperado in self.filtros.items():
                if getattr(cuenta, campo, None) != esperado:
                    ok = False
                    break
            if ok:
                salida.append(cuenta)

        return salida

    def first(self):
        valores = self.all()
        return valores[0] if valores else None

    def get(self, id_):
        for cuenta in self.cuentas:
            if getattr(cuenta, "id", None) == id_:
                return cuenta
        return None

    def filter_by(self, **kwargs):
        q = QueryFake(self.cuentas)
        q.filtros = dict(kwargs)
        return q


class MercadoLibreCuentaFake:
    query = QueryFake([])


def modelo_cuentas(cuentas):
    class Modelo:
        query = QueryFake(cuentas)

    return Modelo


def cuenta(id_, user_id_ml, estado_conexion="conectada"):
    return SimpleNamespace(
        id=id_,
        user_id_ml=str(user_id_ml),
        nickname=f"cuenta-{user_id_ml}",
        estado_conexion=estado_conexion,
        access_token=f"token-{user_id_ml}",
    )


def pedido_ml(ml_cuenta_id=None, ml_seller_id=None):
    return SimpleNamespace(
        canal="Mercado Libre",
        ml_cuenta_id=ml_cuenta_id,
        ml_seller_id=ml_seller_id,
    )


def test_cuenta_default_devuelve_unica_cuenta():
    c = cuenta(1, "111")
    assert cuenta_default(MercadoLibreCuenta=modelo_cuentas([c])) is c


def test_cuenta_default_sin_cuentas_lanza_error():
    with pytest.raises(MLCuentaNoConfigurada):
        cuenta_default(MercadoLibreCuenta=modelo_cuentas([]))


def test_cuenta_default_con_multiples_cuentas_lanza_error():
    with pytest.raises(MLCuentaAmbigua):
        cuenta_default(MercadoLibreCuenta=modelo_cuentas([
            cuenta(1, "111"),
            cuenta(2, "222"),
        ]))


def test_cuenta_por_pedido_con_ml_cuenta_id_devuelve_cuenta_correcta():
    c1 = cuenta(1, "111")
    c2 = cuenta(2, "222")
    pedido = pedido_ml(ml_cuenta_id=2, ml_seller_id="222")

    resultado = cuenta_por_pedido(
        pedido,
        MercadoLibreCuenta=modelo_cuentas([c1, c2]),
    )

    assert resultado is c2


def test_cuenta_por_pedido_sin_ml_cuenta_id_lanza_error():
    pedido = pedido_ml(ml_cuenta_id=None, ml_seller_id="111")

    with pytest.raises(MLCuentaNoAsignada):
        cuenta_por_pedido(
            pedido,
            MercadoLibreCuenta=modelo_cuentas([cuenta(1, "111")]),
        )


def test_cuenta_por_pedido_no_ml_lanza_error():
    pedido = SimpleNamespace(
        canal="Tienda Nube",
        ml_cuenta_id=1,
        ml_seller_id="111",
    )

    with pytest.raises(MLCuentaNoAsignada):
        cuenta_por_pedido(
            pedido,
            MercadoLibreCuenta=modelo_cuentas([cuenta(1, "111")]),
        )


def test_cuenta_por_pedido_con_seller_id_inconsistente_lanza_error():
    pedido = pedido_ml(ml_cuenta_id=1, ml_seller_id="222")

    with pytest.raises(MLCuentaInconsistente):
        cuenta_por_pedido(
            pedido,
            MercadoLibreCuenta=modelo_cuentas([cuenta(1, "111")]),
        )


def test_cuenta_por_pedido_permite_snapshot_vacio():
    c = cuenta(1, "111")
    pedido = pedido_ml(ml_cuenta_id=1, ml_seller_id="")

    assert cuenta_por_pedido(
        pedido,
        MercadoLibreCuenta=modelo_cuentas([c]),
    ) is c


def test_seller_id_pedido_sale_de_la_cuenta_no_del_snapshot():
    c = cuenta(1, "111")
    pedido = pedido_ml(ml_cuenta_id=1, ml_seller_id="111")

    assert seller_id_pedido(
        pedido,
        MercadoLibreCuenta=modelo_cuentas([c]),
    ) == "111"


def test_cuenta_por_seller_id_devuelve_cuenta_correcta():
    c1 = cuenta(1, "111")
    c2 = cuenta(2, "222")

    assert cuenta_por_seller_id(
        "222",
        MercadoLibreCuenta=modelo_cuentas([c1, c2]),
    ) is c2


def test_cuenta_por_seller_id_inexistente_lanza_error():
    with pytest.raises(MLCuentaNoEncontrada):
        cuenta_por_seller_id(
            "999",
            MercadoLibreCuenta=modelo_cuentas([cuenta(1, "111")]),
        )


def test_cuentas_activas_devuelve_solo_conectadas():
    c1 = cuenta(1, "111", estado_conexion="conectada")
    c2 = cuenta(2, "222", estado_conexion="desconectada")

    assert cuentas_activas(
        MercadoLibreCuenta=modelo_cuentas([c1, c2]),
    ) == [c1]
