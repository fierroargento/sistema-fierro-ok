import py_compile
from pathlib import Path


def test_app_py_compila_sin_syntax_error():
    py_compile.compile(str(Path("app.py")), doraise=True)
