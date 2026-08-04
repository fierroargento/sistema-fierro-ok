from pathlib import Path

from models.organizacion import Organizacion
from models.unidad_negocio import UnidadNegocio


def test_modelo_organizacion_expone_base_empresarial():
    assert Organizacion.__tablename__ == "organizacion"

    columnas = {
        "id",
        "nombre",
        "slug",
        "activa",
        "fecha_creacion",
        "fecha_actualizacion",
        "unidades_negocio",
    }

    assert columnas.issubset(
        set(Organizacion.__dict__)
    )


def test_modelo_unidad_negocio_pertenece_a_organizacion():
    assert UnidadNegocio.__tablename__ == "unidad_negocio"

    columnas = {
        "id",
        "organizacion_id",
        "nombre",
        "codigo",
        "activa",
        "fecha_creacion",
        "fecha_actualizacion",
    }

    assert columnas.issubset(
        set(UnidadNegocio.__dict__)
    )


def test_bootstrap_empresarial_es_idempotente_y_sin_pedidos():
    servicio = Path(
        "services/estructura_empresarial.py"
    ).read_text(encoding="utf-8")

    assert (
        'ORGANIZACION_SLUG_GRUPO_FIERRO = '
        '"grupo-fierro"'
        in servicio
    )
    assert '"fierro-100-argento"' in servicio
    assert '"nautica-del-plata"' in servicio

    assert (
        "Organizacion.query"
        in servicio
    )
    assert (
        "UnidadNegocio.query"
        in servicio
    )
    assert "if organizacion is None:" in servicio
    assert "if unidad is None:" in servicio

    assert "Pedido" not in servicio
    assert "MercadoLibreCuenta" not in servicio
    assert "TiendaNubeCuenta" not in servicio


def test_app_registra_y_crea_estructura_empresarial():
    app = Path("app.py").read_text(
        encoding="utf-8"
    )
    bootstrap = Path(
        "services/bootstrap_base_datos.py"
    ).read_text(encoding="utf-8")

    assert (
        "from models.organizacion import Organizacion"
        in app
    )
    assert (
        "from models.unidad_negocio import UnidadNegocio"
        in app
    )
    assert (
        "inicializar_base_datos_saas("
        in app
    )
    assert (
        "asegurar_estructura_empresarial_inicial("
        in bootstrap
    )
    assert (
        bootstrap.index("db.create_all()")
        < bootstrap.index(
            "asegurar_estructura_empresarial_inicial("
        )
    )
