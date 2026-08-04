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
    contenido = Path(
        "services/bootstrap_base_datos.py"
    ).read_text(encoding="utf-8")

    indice_create_all = contenido.index(
        "db.create_all()"
    )
    indice_backfill = contenido.index(
        "asegurar_membresias_organizacion_inicial("
    )

    assert indice_create_all < indice_backfill


def test_backfill_usa_organizacion_inicial():
    contenido = Path(
        "services/bootstrap_base_datos.py"
    ).read_text(encoding="utf-8")

    inicio = contenido.index(
        "asegurar_membresias_organizacion_inicial("
    )
    bloque = contenido[inicio:inicio + 700]

    assert (
        'modelos["UsuarioSistema"]'
        in bloque
    )
    assert (
        'modelos["UsuarioOrganizacion"]'
        in bloque
    )
    assert (
        "organizacion_id=organizacion_id"
        in bloque
    )
