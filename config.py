"""Configuracion centralizada preparatoria.

Este archivo no cambia el comportamiento actual hasta que app.py lo importe.
Sirve como base para reemplazar constantes dispersas en el refactor liviano.
"""
import os


def env(name, default=None):
    return os.getenv(name, default)


def required_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Falta variable de entorno obligatoria: {name}")
    return value


class BaseConfig:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER_NAME = "uploads"
    ROLES = ("admin", "carga", "despacho")


class ProductionConfig(BaseConfig):
    # Activar en etapa siguiente cuando confirmemos SECRET_KEY en Render.
    REQUIRE_SECRET_KEY = True


class DevelopmentConfig(BaseConfig):
    REQUIRE_SECRET_KEY = False
