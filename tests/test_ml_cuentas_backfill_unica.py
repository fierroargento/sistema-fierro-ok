from types import SimpleNamespace

import pytest

from services.ml_cuentas import (
    MLCuentaAmbigua,
    cuenta_por_pedido_o_backfill_unica,
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

    def filter_by(self, **kwargs):
        q = QueryFake(self.cuentas)
        q.filtros = dict(kwargs)
        return q


def modelo_cuentas(cuentas):
    class Modelo:
        query = QueryFake(cuentas)

    return Modelo


def cuenta(id_, user_id_ml):
    return SimpleNamespace(
        id=id_,
        user_id_ml=str(user_id_ml),
        nickname=f"cuenta-{user_id_ml}",
        access_token="token",
        refresh_token="refresh",
    )


def pedido_huerfano():
    return SimpleNamespace(
        id=931,
        canal="Mercado Libre",
        ml_cuenta_id=None,
        ml_seller_id="",
    )


def test_cuenta_por_pedido_o_backfill_unica_repara_pedido_huerfano():
    p = pedido_huerfano()
    c = cuenta(7, "1383494933")
    commits = []

    resultado = cuenta_por_pedido_o_backfill_unica(
        p,
        MercadoLibreCuenta=modelo_cuentas([c]),
        commit_fn=lambda: commits.append("commit"),
    )

    assert resultado is c
    assert p.ml_cuenta_id == 7
    assert p.ml_seller_id == "1383494933"
    assert commits == ["commit"]


def test_cuenta_por_pedido_o_backfill_unica_no_adivina_con_multiples_cuentas():
    p = pedido_huerfano()

    with pytest.raises(MLCuentaAmbigua):
        cuenta_por_pedido_o_backfill_unica(
            p,
            MercadoLibreCuenta=modelo_cuentas([
                cuenta(1, "111"),
                cuenta(2, "222"),
            ]),
        )

    assert p.ml_cuenta_id is None
    assert p.ml_seller_id == ""
