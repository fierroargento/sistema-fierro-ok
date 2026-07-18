import ast
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from services import via_cargo_sucursales


class SessionCommitFallido:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1
        raise RuntimeError("fallo simulado de persistencia")

    def rollback(self):
        self.rollbacks += 1


def cargar_sugerir_sucursales(db_fake):
    texto = Path("app.py").read_text(
        encoding="utf-8-sig",
    )
    arbol = ast.parse(texto)

    funcion = next(
        nodo
        for nodo in arbol.body
        if isinstance(nodo, ast.FunctionDef)
        and nodo.name == "sugerir_sucursales"
    )

    modulo = ast.Module(
        body=[funcion],
        type_ignores=[],
    )
    ast.fix_missing_locations(modulo)

    namespace = {
        "db": db_fake,
        "json": json,
    }

    exec(
        compile(
            modulo,
            filename="app.py",
            mode="exec",
        ),
        namespace,
    )

    return namespace["sugerir_sucursales"]


def test_via_cargo_no_devuelve_mensaje_si_falla_persistencia(
    monkeypatch,
):
    session = SessionCommitFallido()
    db_fake = SimpleNamespace(session=session)

    monkeypatch.setattr(
        via_cargo_sucursales,
        "armar_sugerencia_via_cargo_pedido",
        lambda pedido, limite=3, exigir_distancia=False: {
            "ok": True,
            "ids_ofrecidas": ["VC1"],
            "mensaje": "Elegí una sucursal Vía Cargo",
        },
    )

    sugerir_sucursales = cargar_sugerir_sucursales(
        db_fake,
    )

    pedido = SimpleNamespace(
        sucursal_nombre="",
        empresa_envio="Vía Cargo",
        ia_sucursales_ofrecidas=None,
    )

    resultado = sugerir_sucursales(pedido)

    assert session.commits == 1
    assert session.rollbacks == 1
    assert resultado is None


def test_correo_no_devuelve_mensaje_si_falla_persistencia_ml(
    monkeypatch,
):
    session = SessionCommitFallido()
    db_fake = SimpleNamespace(session=session)

    preparar_llamadas = []

    def preparar_oferta(
        pedido,
        canal_origen="ml",
    ):
        preparar_llamadas.append(canal_origen)
        pedido.correo_sucursales_ofrecidas = '["A1"]'
        return SimpleNamespace(
            ok=True,
            mensaje="Elegí una sucursal Correo",
        )

    selector_fake = types.SimpleNamespace(
        preparar_oferta_sucursales_correo_pedido=preparar_oferta,
    )

    monkeypatch.setitem(
        sys.modules,
        "modules.transportes.selector",
        selector_fake,
    )

    sugerir_sucursales = cargar_sugerir_sucursales(
        db_fake,
    )

    pedido = SimpleNamespace(
        sucursal_nombre="",
        empresa_envio="Correo Argentino",
        correo_sucursales_ofrecidas=None,
    )

    resultado = sugerir_sucursales(pedido)

    assert preparar_llamadas == ["ml"]
    assert pedido.correo_sucursales_ofrecidas == '["A1"]'
    assert session.commits == 1
    assert session.rollbacks == 1
    assert resultado is None
