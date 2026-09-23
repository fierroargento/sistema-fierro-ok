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
        "ALMACENAMIENTO_ARCHIVOS": "local_aislado",
        "STAGING_UPLOAD_ROOT": str(base.parent / "archivos-uat"),
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
        "assert app.Organizacion.query.count() == 2; "
        "assert app.UsuarioSistema.query.count() == 0; "
        "assert app.db.session.execute(app.text("
        "'SELECT version FROM schema_version_saas')).first() is not None; "
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


def test_staging_inseguro_es_rechazado_antes_de_conectar(tmp_path):
    raiz = Path(__file__).resolve().parents[1]
    entorno = _entorno_runtime(raiz, tmp_path / "no-debe-usarse.sqlite3")
    entorno.update({
        "SISTEMA_FIERRO_ENTORNO": "staging",
        "DATABASE_URL": "postgresql://usuario:clave@host-inexistente/base-staging",
        "SISTEMA_FIERRO_PROPOSITO": "uat_desconectada",
        "SISTEMA_FIERRO_RAMA_DESPLIEGUE": "integracion-saas-2026-09",
        "MODO_LABORATORIO_DESCONECTADO": "false",
    })
    resultado = subprocess.run(
        [sys.executable, "-c", "import app"],
        cwd=raiz,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    salida = resultado.stdout + resultado.stderr
    assert resultado.returncode != 0
    assert "Staging rechazado por preflight" in salida
    assert "host-inexistente" not in salida
