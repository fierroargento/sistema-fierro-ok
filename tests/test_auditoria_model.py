from pathlib import Path

from models.auditoria import Auditoria


def test_auditoria_expone_modelo_canonico():
    assert Auditoria.__tablename__ == "auditoria"

    columnas = {
        "id",
        "usuario_id",
        "username",
        "nombre",
        "rol",
        "accion",
        "entidad",
        "entidad_id",
        "detalle",
        "fecha",
        "ip",
        "metodo",
        "path",
    }

    assert columnas.issubset(set(Auditoria.__dict__))


def test_auditoria_no_depende_de_app_ni_utcnow():
    modelo = Path(
        "models/auditoria.py"
    ).read_text(encoding="utf-8")

    app = Path("app.py").read_text(encoding="utf-8")

    assert modelo.count("from extensions import db") == 1
    assert (
        "from services.fechas import ahora_utc_naive"
        in modelo
    )
    assert "datetime.utcnow" not in modelo
    assert "class Auditoria" not in app
    assert "from models.auditoria import Auditoria" in app
