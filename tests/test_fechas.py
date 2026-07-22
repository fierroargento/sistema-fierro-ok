from datetime import UTC, datetime

from services.fechas import ahora_utc_naive


def test_ahora_utc_naive_devuelve_utc_sin_tzinfo():
    antes = datetime.now(UTC).replace(tzinfo=None)

    resultado = ahora_utc_naive()

    despues = datetime.now(UTC).replace(tzinfo=None)

    assert resultado.tzinfo is None
    assert antes <= resultado <= despues
