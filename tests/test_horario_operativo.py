from datetime import (
    datetime,
    timezone,
)

from services.horario_operativo import (
    ARG_TZ,
    IA_TIMEOUT_RESPUESTA_SEGUNDOS,
    _ia_datetime_arg,
    _ia_datetime_utc,
    ia_ahora_utc,
    ia_en_horario_operativo,
    ia_segundos_operativos_entre,
)


def _utc(
    anio,
    mes,
    dia,
    hora,
    minuto=0,
):
    return datetime(
        anio,
        mes,
        dia,
        hora,
        minuto,
        tzinfo=timezone.utc,
    )


def test_ahora_utc_conserva_contrato_naive():
    resultado = ia_ahora_utc()

    assert resultado.tzinfo is None


def test_datetime_utc_acepta_naive_y_aware():
    naive = datetime(
        2026,
        7,
        24,
        15,
        0,
    )
    aware = _utc(
        2026,
        7,
        24,
        15,
    )

    assert _ia_datetime_utc(naive).tzinfo == (
        timezone.utc
    )
    assert _ia_datetime_utc(aware) == aware


def test_datetime_arg_convierte_desde_utc():
    resultado = _ia_datetime_arg(
        _utc(
            2026,
            7,
            24,
            15,
        )
    )

    assert resultado.tzinfo == ARG_TZ
    assert resultado.hour == 12


def test_horario_operativo_incluye_8_y_excluye_22():
    ocho_argentina = _utc(
        2026,
        7,
        24,
        11,
    )
    veintidos_argentina = _utc(
        2026,
        7,
        25,
        1,
    )

    assert ia_en_horario_operativo(
        ocho_argentina
    ) is True
    assert ia_en_horario_operativo(
        veintidos_argentina
    ) is False


def test_segundos_operativos_mismo_dia():
    inicio = _utc(
        2026,
        7,
        24,
        10,
    )
    fin = _utc(
        2026,
        7,
        24,
        13,
    )

    # 07:00 a 10:00 Argentina:
    # solo cuentan 08:00 a 10:00.
    assert ia_segundos_operativos_entre(
        inicio,
        fin,
    ) == 2 * 60 * 60


def test_segundos_operativos_entre_dias():
    inicio = _utc(
        2026,
        7,
        24,
        23,
    )
    fin = _utc(
        2026,
        7,
        25,
        13,
    )

    # Día 1: 20:00 a 22:00.
    # Día 2: 08:00 a 10:00.
    assert ia_segundos_operativos_entre(
        inicio,
        fin,
    ) == 4 * 60 * 60


def test_segundos_operativos_casos_invalidos():
    fecha = _utc(
        2026,
        7,
        24,
        15,
    )

    assert ia_segundos_operativos_entre(
        None,
        fecha,
    ) == 0
    assert ia_segundos_operativos_entre(
        fecha,
        fecha,
    ) == 0


def test_timeout_operativo_sigue_siendo_dos_horas():
    assert IA_TIMEOUT_RESPUESTA_SEGUNDOS == (
        2 * 60 * 60
    )
