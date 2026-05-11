"""
tests/conftest.py
─────────────────
Configura sys.path para que los tests puedan importar funciones puras de app.py
sin levantar Flask ni conectarse a la base de datos.

Estrategia:
- Agrega la raíz del proyecto al path
- Parchea las dependencias que requieren DB/Flask/env vars antes de importar app
- Expone las funciones puras que queremos testear como fixtures o importaciones directas
"""

import sys
import os
import types
import pytest

# ── Raíz del proyecto ────────────────────────────────────────────────────────
# Ajustar esta ruta según la ubicación real del proyecto en tu máquina.
# Si corres pytest desde la carpeta del proyecto, REPO_ROOT = "." funciona.
REPO_ROOT = os.environ.get("FIERRO_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, REPO_ROOT)


# ── Stub mínimo de Flask y SQLAlchemy ────────────────────────────────────────
# app.py importa Flask, SQLAlchemy, cloudinary, etc. al nivel del módulo.
# No necesitamos ninguno de esos para testear funciones puras.
# Los stubbeamos antes de que app.py los intente importar.

def _make_stub(name):
    mod = types.ModuleType(name)
    # Cualquier acceso a atributo devuelve un stub callable/clase vacía
    class _Any:
        def __init__(self, *a, **kw): pass
        def __call__(self, *a, **kw): return self
        def __getattr__(self, n): return _Any()
        def __iter__(self): return iter([])
        def __bool__(self): return True
        def __enter__(self): return self
        def __exit__(self, *a): pass
    mod.__dict__['__getattr__'] = lambda n: _Any()
    mod._Any = _Any
    return mod


STUBS = [
    "flask", "flask_sqlalchemy", "sqlalchemy", "sqlalchemy.orm",
    "sqlalchemy.sql", "sqlalchemy.ext", "cloudinary", "cloudinary.uploader",
    "fitz", "pymupdf", "pandas", "numpy", "openpyxl",
    "werkzeug", "werkzeug.utils", "werkzeug.security",
]

for stub_name in STUBS:
    if stub_name not in sys.modules:
        sys.modules[stub_name] = _make_stub(stub_name)


# Flask stub needs request, session, redirect, render_template etc.
import types as _types
flask_stub = sys.modules["flask"]

class _Request:
    method = "GET"
    args = {}
    form = {}
    files = {}
    path = "/"
    def get_json(self, *a, **kw): return {}

flask_stub.request = _Request()
flask_stub.session = {}

for attr in ["redirect", "render_template", "url_for", "flash", "send_from_directory", "jsonify"]:
    setattr(flask_stub, attr, lambda *a, **kw: None)

flask_stub.Flask = lambda *a, **kw: None


# SQLAlchemy stubs - db.Column, db.Model, db.session etc.
class _Column:
    def __init__(self, *a, **kw): pass
    def __set_name__(self, owner, name): pass

class _FakeDB:
    Column = _Column
    Integer = int
    String = str
    Boolean = bool
    Float = float
    DateTime = object
    Text = str
    Model = object
    relationship = lambda *a, **kw: None
    ForeignKey = lambda *a, **kw: None
    session = type("session", (), {
        "add": lambda *a: None,
        "commit": lambda *a: None,
        "rollback": lambda *a: None,
        "remove": lambda *a: None,
        "query": lambda *a: None,
    })()
    def __call__(self, *a, **kw): return self
    def init_app(self, *a): pass

flask_sqlalchemy_stub = sys.modules["flask_sqlalchemy"]
flask_sqlalchemy_stub.SQLAlchemy = _FakeDB

# ── Importar solo las funciones puras ────────────────────────────────────────
# Esto se hace en cada archivo de test con import directo.
# conftest solo garantiza que el entorno esté listo.
