from pathlib import Path

from models.politica_disponibilidad_catalogo import (
    PoliticaDisponibilidadCatalogo,
)


def test_modelo_declara_cuenta_empresarial_exacta():
    assert hasattr(
        PoliticaDisponibilidadCatalogo,
        "vinculo_canal_comercial_id",
    )
    assert hasattr(
        PoliticaDisponibilidadCatalogo,
        "vinculo_canal",
    )


def test_migracion_es_aditiva_y_no_toca_stock():
    migracion = Path(
        "services/migraciones_saas.py"
    ).read_text(encoding="utf-8")
    assert (
        '"ALTER TABLE politica_disponibilidad_catalogo "'
        in migracion
    )
    assert (
        '"ADD COLUMN vinculo_canal_comercial_id INTEGER"'
        in migracion
    )
    bloque = migracion.split(
        'if "politica_disponibilidad_catalogo" in tablas:', 1
    )[1].split("if cambios:", 1)[0]
    assert "UPDATE" not in bloque
    assert "stock_actual" not in bloque
    assert "ix_politica_disponibilidad_vinculo_canal" in bloque
