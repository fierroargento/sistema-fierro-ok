from pathlib import Path

from models.usuario_sistema import UsuarioSistema


def test_usuario_sistema_expone_modelo_canonico():
    assert (
        UsuarioSistema.__tablename__
        == "usuario_sistema"
    )

    columnas = {
        "id",
        "username",
        "password_hash",
        "nombre",
        "rol",
        "activo",
        "fecha_creacion",
        "creado_por",
        "actualizado_at",
    }

    assert columnas.issubset(
        set(UsuarioSistema.__dict__)
    )


def test_usuario_sistema_no_depende_de_app_ni_utcnow():
    modelo = Path(
        "models/usuario_sistema.py"
    ).read_text(encoding="utf-8")

    app = Path("app.py").read_text(encoding="utf-8")

    assert modelo.count("from extensions import db") == 1
    assert (
        "from services.fechas import ahora_utc_naive"
        in modelo
    )
    assert "datetime.utcnow" not in modelo
    assert "class UsuarioSistema" not in app
    assert (
        "from models.usuario_sistema import "
        "UsuarioSistema"
        in app
    )
