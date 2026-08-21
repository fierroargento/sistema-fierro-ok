from pathlib import Path
from types import SimpleNamespace

import pytest

from services.estructura_admin import (
    _exigir_pertenencia_tenant,
)


def test_acepta_registro_del_tenant_activo():
    organizacion = SimpleNamespace(id=10)
    registro = SimpleNamespace(
        organizacion_id=10
    )

    assert (
        _exigir_pertenencia_tenant(
            organizacion,
            registro,
            "El registro",
        )
        is registro
    )


def test_rechaza_registro_de_otro_tenant():
    organizacion = SimpleNamespace(id=10)
    registro = SimpleNamespace(
        organizacion_id=20
    )

    with pytest.raises(
        ValueError,
        match="no pertenece",
    ):
        _exigir_pertenencia_tenant(
            organizacion,
            registro,
            "El registro",
        )


def test_valida_relacion_tenant_indirecta():
    organizacion = SimpleNamespace(id=10)
    registro = SimpleNamespace()

    assert (
        _exigir_pertenencia_tenant(
            organizacion,
            registro,
            "La inclusion",
            organizacion_id=10,
        )
        is registro
    )

    with pytest.raises(ValueError):
        _exigir_pertenencia_tenant(
            organizacion,
            registro,
            "La inclusion",
            organizacion_id=20,
        )


def test_mutaciones_sensibles_exigen_tenant():
    contenido = Path(
        "services/estructura_admin.py"
    ).read_text(encoding="utf-8")

    inicio = contenido.index(
        "def procesar_accion_estructura_admin("
    )
    bloque = contenido[inicio:]

    assert bloque.count(
        "_exigir_pertenencia_tenant("
    ) == 11

    acciones = (
        "toggle_sucursal",
        "toggle_entidad_fiscal",
        "toggle_facturacion",
        "estado_catalogo",
        "agregar_producto_catalogo",
        "toggle_producto_catalogo",
        "estado_modulo",
        "asignar_vinculo_canal",
        "estado_vinculo_canal",
    )

    for accion in acciones:
        inicio_accion = bloque.index(
            f'if accion == "{accion}":'
        )
        siguiente = bloque.find(
            "\n    if accion == ",
            inicio_accion + 1,
        )
        fin_accion = (
            siguiente
            if siguiente != -1
            else len(bloque)
        )

        assert (
            "_exigir_pertenencia_tenant("
            in bloque[inicio_accion:fin_accion]
        )
