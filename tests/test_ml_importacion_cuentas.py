from types import SimpleNamespace

from services.ml_importacion_cuentas import (
    ml_asignar_cuenta_ml_a_pedido_service,
    ml_extraer_seller_id_order_service,
    ml_resolver_cuenta_ml_webhook_service,
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
    )


def pedido_ml():
    return SimpleNamespace(
        id=10,
        canal="Mercado Libre",
        ml_cuenta_id=None,
        ml_seller_id="",
    )


def test_extrae_seller_id_directo_de_order():
    assert ml_extraer_seller_id_order_service({"seller_id": "111"}) == "111"


def test_extrae_seller_id_desde_seller_objeto():
    assert ml_extraer_seller_id_order_service({"seller": {"id": 222}}) == "222"


def test_asigna_cuenta_explicita_al_pedido():
    p = pedido_ml()
    c = cuenta(5, "555")

    resultado = ml_asignar_cuenta_ml_a_pedido_service(
        p,
        {"seller": {"id": "111"}},
        modelo_cuentas([]),
        cuenta_ml=c,
    )

    assert resultado is c
    assert p.ml_cuenta_id == 5
    assert p.ml_seller_id == "555"


def test_resuelve_cuenta_por_seller_de_order():
    c1 = cuenta(1, "111")
    c2 = cuenta(2, "222")
    p = pedido_ml()

    resultado = ml_asignar_cuenta_ml_a_pedido_service(
        p,
        {"seller": {"id": "222"}},
        modelo_cuentas([c1, c2]),
    )

    assert resultado is c2
    assert p.ml_cuenta_id == 2
    assert p.ml_seller_id == "222"


def test_usa_default_si_hay_una_sola_cuenta_y_order_no_trae_seller():
    c = cuenta(1, "111")
    p = pedido_ml()

    resultado = ml_asignar_cuenta_ml_a_pedido_service(
        p,
        {},
        modelo_cuentas([c]),
    )

    assert resultado is c
    assert p.ml_cuenta_id == 1
    assert p.ml_seller_id == "111"


def test_no_adivina_si_hay_multiples_cuentas_y_order_no_trae_seller():
    c1 = cuenta(1, "111")
    c2 = cuenta(2, "222")
    p = pedido_ml()

    resultado = ml_asignar_cuenta_ml_a_pedido_service(
        p,
        {},
        modelo_cuentas([c1, c2]),
    )

    assert resultado is None
    assert p.ml_cuenta_id is None
    assert p.ml_seller_id == ""


def test_webhook_resuelve_cuenta_por_user_id_payload():
    c1 = cuenta(1, "111")
    c2 = cuenta(2, "222")

    assert ml_resolver_cuenta_ml_webhook_service(
        {"user_id": 222},
        modelo_cuentas([c1, c2]),
    ) is c2


def test_webhook_sin_user_id_no_resuelve():
    assert ml_resolver_cuenta_ml_webhook_service(
        {},
        modelo_cuentas([cuenta(1, "111")]),
    ) is None
