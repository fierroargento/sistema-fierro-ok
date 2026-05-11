import py_compile
import pytest

ARCHIVOS_CRITICOS = [
    "app.py",
    "modules/whatsapp/flows.py",
    "modules/whatsapp/webhook.py",
    "modules/whatsapp/scheduler.py",
    "services/andreani.py",
]

@pytest.mark.parametrize("archivo", ARCHIVOS_CRITICOS)
def test_compila_sin_errores(archivo):
    py_compile.compile(archivo, doraise=True)