from pathlib import Path
from types import SimpleNamespace

import pytest

from services.onboarding_saas import cambiar_estado_unidad, normalizar_codigo


def test_normaliza_identificadores_saas():
    assert normalizar_codigo("  Empresa Ágil S.A. ") == "empresa-agil-s-a"
    with pytest.raises(ValueError):
        normalizar_codigo("---")


def test_unidad_de_otro_tenant_no_puede_modificarse():
    class Query:
        @staticmethod
        def get(_identificador):
            return SimpleNamespace(id=9, organizacion_id=22, activa=False)

    class Unidad:
        query = Query()

    with pytest.raises(ValueError, match="tenant activo"):
        cambiar_estado_unidad(
            SimpleNamespace(id=11), 9, UnidadNegocio=Unidad,
            db_session=SimpleNamespace(commit=lambda: None, rollback=lambda: None),
        )


def test_contrato_onboarding_es_generico_y_desconectado():
    servicio = Path("services/onboarding_saas.py").read_text(encoding="utf-8")
    rutas = Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8")
    plantilla = Path("templates/admin_estructura.html").read_text(encoding="utf-8")
    assert "activa=False" in servicio
    assert 'rol="admin"' in servicio
    assert "asegurar_modulos_fn(" in servicio
    for accion in (
        "crear_organizacion", "estado_organizacion", "editar_organizacion",
        "crear_unidad", "editar_unidad", "toggle_unidad",
    ):
        assert accion in rutas
        assert accion in plantilla
    contenido = (servicio + rutas).lower()
    for prohibido in ("requests", "oauth", "webhook", "access_token", "http://", "https://"):
        assert prohibido not in contenido


def test_plantilla_no_fija_grupo_fierro():
    plantilla = Path("templates/admin_estructura.html").read_text(encoding="utf-8")
    assert "Configuración interna de Grupo Fierro" not in plantilla
    assert "{{ organizacion.nombre }}" in plantilla
