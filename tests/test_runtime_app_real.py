"""Pruebas que fuerzan una importación Flask/SQLAlchemy real en otro proceso."""

import os
from pathlib import Path
import subprocess
import sys


def _entorno_runtime(raiz, base):
    entorno = os.environ.copy()
    entorno.update({
        "PYTHONPATH": str(raiz),
        "DATABASE_URL": f"sqlite:///{base}",
        "SECRET_KEY": "prueba-runtime-aislada-clave-segura",
        "SISTEMA_FIERRO_ENTORNO": "desarrollo",
        "MODO_LABORATORIO_DESCONECTADO": "true",
        "BOOTSTRAP_BASE_DATOS_HABILITADO": "false",
        "SCHEDULER_ENABLED": "false",
        "USUARIOS_DEMO_HABILITADOS": "false",
        "SENTRY_DSN": "",
    })
    return entorno


def test_aplicacion_real_arranca_y_sus_gets_autenticados_no_fallan(tmp_path):
    raiz = Path(__file__).resolve().parents[1]
    ejecutor = raiz / "tests" / "runtime_app_smoke.py"
    entorno = _entorno_runtime(raiz, tmp_path / "runtime-smoke.sqlite3")
    resultado = subprocess.run(
        [sys.executable, str(ejecutor)],
        cwd=raiz,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "RUNTIME_SMOKE_OK" in resultado.stdout


def test_bootstrap_real_inicializa_una_base_vacia(tmp_path):
    raiz = Path(__file__).resolve().parents[1]
    entorno = _entorno_runtime(raiz, tmp_path / "bootstrap-smoke.sqlite3")
    entorno.update({
        "MODO_LABORATORIO_DESCONECTADO": "false",
        "BOOTSTRAP_BASE_DATOS_HABILITADO": "true",
    })
    codigo = (
        "import app; "
        "ctx=app.app.app_context(); ctx.push(); "
        "assert app.Organizacion.query.count() == 1; "
        "assert app.UsuarioSistema.query.count() == 0; "
        "print('BOOTSTRAP_RUNTIME_OK')"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=raiz,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "BOOTSTRAP_RUNTIME_OK" in resultado.stdout
