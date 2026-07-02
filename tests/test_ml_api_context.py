from types import SimpleNamespace

import pytest

from services.ml_api_context import (
    MLApiCuentaInvalida,
    MLApiTokenInvalido,
    MLApiContext,
    ml_api_contexto,
)


class DbSessionFake:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def cuenta(id_=1, user_id_ml="111", access_token="token-111"):
    return SimpleNamespace(
        id=id_,
        user_id_ml=user_id_ml,
        access_token=access_token,
        refresh_token=f"refresh-{user_id_ml}",
    )


def test_contexto_rechaza_cuenta_vacia():
    ctx = MLApiContext(None)

    with pytest.raises(MLApiCuentaInvalida):
        ctx.asegurar_token()


def test_contexto_rechaza_cuenta_sin_id():
    ctx = MLApiContext(cuenta(id_=None))

    with pytest.raises(MLApiCuentaInvalida):
        ctx.asegurar_token()


def test_contexto_rechaza_cuenta_sin_seller_id():
    ctx = MLApiContext(cuenta(user_id_ml=""))

    with pytest.raises(MLApiCuentaInvalida):
        ctx.asegurar_token()


def test_asegurar_token_devuelve_token_actual_si_no_esta_vencido():
    c = cuenta(access_token="token-a")

    ctx = MLApiContext(
        c,
        token_vencido_fn=lambda cuenta: False,
    )

    assert ctx.asegurar_token() == "token-a"


def test_asegurar_token_refresca_solo_la_cuenta_del_contexto_y_commitea():
    c1 = cuenta(id_=1, user_id_ml="111", access_token="token-viejo-111")
    c2 = cuenta(id_=2, user_id_ml="222", access_token="token-viejo-222")
    db = DbSessionFake()

    refrescadas = []

    def refresh_fn(cuenta_recibida):
        refrescadas.append(cuenta_recibida.id)
        cuenta_recibida.access_token = f"token-nuevo-{cuenta_recibida.user_id_ml}"
        return cuenta_recibida

    ctx = MLApiContext(
        c1,
        db_session=db,
        token_vencido_fn=lambda cuenta: True,
        refresh_fn=refresh_fn,
    )

    assert ctx.asegurar_token() == "token-nuevo-111"
    assert refrescadas == [1]
    assert c1.access_token == "token-nuevo-111"
    assert c2.access_token == "token-viejo-222"
    assert db.commits == 1


def test_asegurar_token_sin_token_lanza_error():
    ctx = MLApiContext(
        cuenta(access_token=""),
        token_vencido_fn=lambda cuenta: False,
    )

    with pytest.raises(MLApiTokenInvalido):
        ctx.asegurar_token()


def test_get_usa_token_de_la_cuenta_recibida():
    c = cuenta(id_=1, user_id_ml="111", access_token="token-111")
    llamadas = []

    def get_fn(token, path, params=None):
        llamadas.append((token, path, params))
        return {"ok": True}

    ctx = MLApiContext(
        c,
        token_vencido_fn=lambda cuenta: False,
        get_fn=get_fn,
    )

    assert ctx.get("/orders/123", params={"x": "1"}) == {"ok": True}
    assert llamadas == [("token-111", "/orders/123", {"x": "1"})]


def test_post_json_usa_token_de_la_cuenta_recibida():
    c = cuenta(id_=2, user_id_ml="222", access_token="token-222")
    llamadas = []

    def post_json_fn(token, path, payload=None):
        llamadas.append((token, path, payload))
        return {"sent": True}

    ctx = MLApiContext(
        c,
        token_vencido_fn=lambda cuenta: False,
        post_json_fn=post_json_fn,
    )

    assert ctx.post_json("/messages", payload={"body": "hola"}) == {"sent": True}
    assert llamadas == [("token-222", "/messages", {"body": "hola"})]


def test_get_binario_usa_token_de_la_cuenta_recibida():
    c = cuenta(id_=3, user_id_ml="333", access_token="token-333")
    llamadas = []

    def get_binario_fn(token, path, params=None, accept="application/pdf"):
        llamadas.append((token, path, params, accept))
        return b"pdf", "application/pdf"

    ctx = MLApiContext(
        c,
        token_vencido_fn=lambda cuenta: False,
        get_binario_fn=get_binario_fn,
    )

    assert ctx.get_binario(
        "/shipment_labels",
        params={"shipment_ids": "999"},
        accept="application/pdf",
    ) == (b"pdf", "application/pdf")

    assert llamadas == [
        ("token-333", "/shipment_labels", {"shipment_ids": "999"}, "application/pdf")
    ]


def test_factory_ml_api_contexto_devuelve_contexto():
    c = cuenta()
    ctx = ml_api_contexto(c, token_vencido_fn=lambda cuenta: False)

    assert isinstance(ctx, MLApiContext)
    assert ctx.asegurar_token() == "token-111"


def test_dos_contextos_distintos_no_comparten_estado():
    c1 = cuenta(id_=1, user_id_ml="111", access_token="token-111")
    c2 = cuenta(id_=2, user_id_ml="222", access_token="token-222")

    llamadas = []

    def get_fn(token, path, params=None):
        llamadas.append(token)
        return {"token": token}

    ctx1 = MLApiContext(c1, token_vencido_fn=lambda cuenta: False, get_fn=get_fn)
    ctx2 = MLApiContext(c2, token_vencido_fn=lambda cuenta: False, get_fn=get_fn)

    assert ctx1.get("/users/me") == {"token": "token-111"}
    assert ctx2.get("/users/me") == {"token": "token-222"}
    assert llamadas == ["token-111", "token-222"]
