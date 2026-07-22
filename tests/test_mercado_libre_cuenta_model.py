from pathlib import Path

from models.mercado_libre_cuenta import MercadoLibreCuenta
from services import ml_cuentas


def test_mercado_libre_cuenta_expone_modelo_canonico():
    assert (
        MercadoLibreCuenta.__tablename__
        == "mercado_libre_cuenta"
    )

    columnas = {
        "id",
        "user_id_ml",
        "nickname",
        "access_token",
        "refresh_token",
        "token_expires_at",
        "scope",
        "estado_conexion",
        "last_sync_at",
        "last_sync_status",
        "last_sync_detail",
        "created_at",
        "updated_at",
    }

    assert columnas.issubset(
        set(MercadoLibreCuenta.__dict__)
    )


def test_ml_cuentas_usa_modelo_canonico_por_default():
    assert (
        ml_cuentas._modelo_cuenta()
        is MercadoLibreCuenta
    )


def test_modelo_ml_no_depende_de_app_ni_utcnow():
    modelo = Path(
        "models/mercado_libre_cuenta.py"
    ).read_text(encoding="utf-8")

    servicio = Path(
        "services/ml_cuentas.py"
    ).read_text(encoding="utf-8")

    app = Path("app.py").read_text(encoding="utf-8")

    assert modelo.count("from extensions import db") == 1
    assert (
        "from services.fechas import ahora_utc_naive"
        in modelo
    )
    assert "datetime.utcnow" not in modelo
    assert "from app import" not in servicio
    assert "class MercadoLibreCuenta" not in app
    assert (
        "from models.mercado_libre_cuenta import "
        "MercadoLibreCuenta"
        in app
    )
