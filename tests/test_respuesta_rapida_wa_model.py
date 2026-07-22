from pathlib import Path

from models.respuesta_rapida_wa import RespuestaRapidaWA


def test_respuesta_rapida_wa_expone_modelo_canonico():
    assert RespuestaRapidaWA.__tablename__ == "respuesta_rapida_wa"

    columnas = {
        "id",
        "empresa_id",
        "titulo",
        "texto",
        "categoria",
        "orden",
        "activa",
        "imagen_url",
        "imagen_public_id",
        "imagen_nombre",
        "creado_por",
        "creado_en",
        "actualizado_en",
    }

    assert columnas.issubset(
        set(RespuestaRapidaWA.__dict__)
    )


def test_respuesta_rapida_wa_no_usa_factory_ni_utcnow():
    modelo = Path(
        "models/respuesta_rapida_wa.py"
    ).read_text(encoding="utf-8")

    app = Path("app.py").read_text(encoding="utf-8")

    assert modelo.count("from extensions import db") == 1
    assert modelo.count(
        "from services.fechas import ahora_utc_naive"
    ) == 1
    assert "datetime.utcnow" not in modelo
    assert (
        "def crear_modelo_respuesta_rapida_wa"
        not in modelo
    )

    assert (
        "from models.respuesta_rapida_wa import "
        "RespuestaRapidaWA"
        in app
    )
    assert (
        "crear_modelo_respuesta_rapida_wa"
        not in app
    )
