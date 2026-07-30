from pathlib import Path


def test_app_importa_modelo_membresia_tenant():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )

    assert (
        "from models.usuario_organizacion "
        "import UsuarioOrganizacion"
        in app
    )


def test_bootstrap_tenant_ocurre_despues_de_create_all():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )

    indice_create_all = app.index(
        "db.create_all()"
    )
    indice_backfill = app.index(
        "asegurar_membresias_organizacion_inicial("
    )

    assert indice_create_all < indice_backfill


def test_backfill_usa_organizacion_inicial():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )

    inicio = app.index(
        "asegurar_membresias_organizacion_inicial("
    )
    bloque = app[inicio:inicio + 700]

    assert "UsuarioSistema=UsuarioSistema" in bloque
    assert (
        "UsuarioOrganizacion=UsuarioOrganizacion"
        in bloque
    )
    assert (
        '"organizacion"'
        in bloque
    )
    assert ".id" in bloque
