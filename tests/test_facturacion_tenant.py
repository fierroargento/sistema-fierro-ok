import ast
from pathlib import Path
from types import SimpleNamespace

from services.migraciones_saas import (
    organizacion_evento_legacy,
)


def test_evento_fiscal_declara_organizacion():
    fuente = Path(
        "models/evento_fiscal.py"
    ).read_text(encoding="utf-8")

    assert "organizacion_id = db.Column(" in fuente
    assert 'db.ForeignKey("organizacion.id")' in fuente
    assert "nullable=False" in fuente


def test_todos_los_eventos_reciben_organizacion():
    fuente = Path(
        "services/facturacion_admin.py"
    ).read_text(encoding="utf-8")
    arbol = ast.parse(fuente)

    llamadas = [
        nodo
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Name)
        and nodo.func.id == "_crear_evento"
    ]

    assert len(llamadas) == 7

    for llamada in llamadas:
        argumentos = {
            argumento.arg: argumento.value
            for argumento in llamada.keywords
            if argumento.arg is not None
        }

        assert "organizacion_id" in argumentos

        valor = argumentos["organizacion_id"]

        assert isinstance(valor, ast.Attribute)
        assert valor.attr == "id"
        assert isinstance(valor.value, ast.Name)
        assert valor.value.id == "organizacion"

def test_evento_legacy_prioriza_borrador():
    evento = SimpleNamespace(
        borrador=SimpleNamespace(
            organizacion_id=20,
        ),
        configuracion=SimpleNamespace(
            organizacion_id=30,
        ),
    )

    assert (
        organizacion_evento_legacy(evento, 10)
        == 20
    )


def test_evento_legacy_usa_configuracion():
    evento = SimpleNamespace(
        borrador=None,
        configuracion=SimpleNamespace(
            organizacion_id=30,
        ),
    )

    assert (
        organizacion_evento_legacy(evento, 10)
        == 30
    )


def test_evento_legacy_tiene_fallback_compatible():
    evento = SimpleNamespace(
        borrador=None,
        configuracion=None,
    )

    assert (
        organizacion_evento_legacy(evento, 10)
        == 10
    )


def test_consultas_fiscales_filtran_eventos_por_tenant():
    fuente = Path(
        "services/facturacion_consultas.py"
    ).read_text(encoding="utf-8")

    inicio = fuente.index(
        "eventos = ("
    )
    bloque = fuente[inicio:]

    assert "EventoFiscal.query" in bloque
    assert "organizacion_id=organizacion_id" in bloque

def test_consultas_no_dependen_de_flask():
    fuente = Path(
        "services/facturacion_consultas.py"
    ).read_text(encoding="utf-8")

    assert "from flask" not in fuente
    assert "request." not in fuente
    assert "session[" not in fuente
