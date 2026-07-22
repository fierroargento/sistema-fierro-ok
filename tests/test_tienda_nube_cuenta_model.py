from pathlib import Path

from models.tienda_nube_cuenta import TiendaNubeCuenta


def test_tienda_nube_cuenta_expone_modelo_canonico():
    assert (
        TiendaNubeCuenta.__tablename__
        == "tienda_nube_cuenta"
    )

    columnas = {
        "id",
        "store_id",
        "estado_conexion",
        "last_sync_at",
        "last_sync_status",
        "last_sync_detail",
        "created_at",
        "updated_at",
    }

    assert columnas.issubset(
        set(TiendaNubeCuenta.__dict__)
    )


def test_tienda_nube_cuenta_no_depende_de_app_ni_utcnow():
    modelo = Path(
        "models/tienda_nube_cuenta.py"
    ).read_text(encoding="utf-8")

    app = Path("app.py").read_text(encoding="utf-8")

    assert modelo.count("from extensions import db") == 1
    assert (
        "from services.fechas import ahora_utc_naive"
        in modelo
    )
    assert "datetime.utcnow" not in modelo
    assert "class TiendaNubeCuenta" not in app
    assert (
        "from models.tienda_nube_cuenta import "
        "TiendaNubeCuenta"
        in app
    )
