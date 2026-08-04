from pathlib import Path
from types import SimpleNamespace

from services.migraciones_saas import (
    organizacion_identidad_canal_legacy,
)


RAIZ = Path(__file__).resolve().parents[1]


def _leer(ruta):
    return (
        RAIZ
        .joinpath(ruta)
        .read_text(encoding="utf-8")
    )


def test_identidad_declara_tenant_explicito():
    contenido = _leer(
        "models/cliente_identidad_canal.py"
    )

    assert (
        'db.ForeignKey("organizacion.id")'
        in contenido
    )
    assert (
        "organizacion_id = db.Column("
        in contenido
    )
    assert (
        'backref="identidades_canal_crm"'
        in contenido
    )


def test_identidad_nueva_copia_tenant():
    contenido = _leer(
        "services/crm_admin.py"
    )

    assert (
        "identidad = ClienteIdentidadCanal("
        in contenido
    )
    assert (
        "organizacion_id=organizacion.id"
        in contenido
    )


def test_codigos_se_validan_dentro_del_tenant():
    contenido = _leer(
        "services/crm_admin.py"
    )

    assert (
        contenido.count(
            "organizacion_id=organizacion.id,"
        )
        >= 3
    )
    assert (
        ".filter_by(codigo=codigo)"
        not in contenido
    )


def test_backfill_prioriza_tenant_cliente():
    identidad = SimpleNamespace(
        cliente=SimpleNamespace(
            organizacion_id=31,
        )
    )

    assert (
        organizacion_identidad_canal_legacy(
            identidad,
            1,
        )
        == 31
    )


def test_backfill_tiene_fallback():
    identidad = SimpleNamespace(
        cliente=None
    )

    assert (
        organizacion_identidad_canal_legacy(
            identidad,
            8,
        )
        == 8
    )


def test_migracion_identidad_es_aditiva():
    contenido = _leer(
        "services/migraciones_saas.py"
    )

    assert (
        "ALTER TABLE cliente_identidad_canal "
        in contenido
    )
    assert (
        "ADD COLUMN organizacion_id INTEGER"
        in contenido
    )
    assert "DROP TABLE" not in contenido
    assert "DROP COLUMN" not in contenido


def test_consultas_crm_filtran_todo_por_tenant():
    contenido = _leer(
        "services/crm_consultas.py"
    )

    assert (
        contenido.count(
            "organizacion_id=organizacion_id"
        )
        == 7
    )
    assert (
        ".join(ClienteCRM)"
        not in contenido
    )


def test_consultas_crm_no_dependen_de_flask():
    contenido = _leer(
        "services/crm_consultas.py"
    )

    assert "from flask" not in contenido
    assert "request." not in contenido
    assert "session." not in contenido


def test_bootstrap_ejecuta_migracion_crm():
    contenido = _leer(
        "services/bootstrap_base_datos.py"
    )

    assert (
        "asegurar_identidad_canal_crm_tenant("
        in contenido
    )
    assert (
        'modelos["ClienteIdentidadCanal"]'
        in contenido
    )
