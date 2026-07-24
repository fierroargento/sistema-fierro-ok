from datetime import (
    datetime,
    time,
    timedelta,
    timezone,
)
from zoneinfo import ZoneInfo


ARG_TZ = ZoneInfo(
    "America/Argentina/Buenos_Aires"
)
IA_HORA_INICIO_OPERATIVA = time(8, 0)
IA_HORA_FIN_OPERATIVA = time(22, 0)
IA_TIMEOUT_RESPUESTA_SEGUNDOS = 2 * 60 * 60


def _ia_datetime_utc(dt):
    if not dt:
        return None

    if dt.tzinfo is None:
        return dt.replace(
            tzinfo=timezone.utc,
        )

    return dt.astimezone(timezone.utc)


def _ia_datetime_arg(dt):
    dt_utc = _ia_datetime_utc(dt)

    return (
        dt_utc.astimezone(ARG_TZ)
        if dt_utc
        else None
    )


def ia_ahora_utc():
    """Devuelve UTC naive para respetar el contrato DB."""
    return datetime.now(
        timezone.utc
    ).replace(tzinfo=None)


def ia_en_horario_operativo(dt=None):
    ahora_arg = _ia_datetime_arg(
        dt or ia_ahora_utc()
    )

    if not ahora_arg:
        return False

    hora = ahora_arg.time()

    return (
        IA_HORA_INICIO_OPERATIVA
        <= hora
        < IA_HORA_FIN_OPERATIVA
    )


def ia_segundos_operativos_entre(
    inicio,
    fin=None,
):
    """Cuenta segundos entre 08:00 y 22:00 Argentina."""
    if not inicio:
        return 0

    fin = fin or ia_ahora_utc()
    ini_arg = _ia_datetime_arg(inicio)
    fin_arg = _ia_datetime_arg(fin)

    if (
        not ini_arg
        or not fin_arg
        or fin_arg <= ini_arg
    ):
        return 0

    total = 0
    cursor_fecha = ini_arg.date()
    fin_fecha = fin_arg.date()

    while cursor_fecha <= fin_fecha:
        tramo_ini = datetime.combine(
            cursor_fecha,
            IA_HORA_INICIO_OPERATIVA,
            tzinfo=ARG_TZ,
        )
        tramo_fin = datetime.combine(
            cursor_fecha,
            IA_HORA_FIN_OPERATIVA,
            tzinfo=ARG_TZ,
        )
        desde = max(
            ini_arg,
            tramo_ini,
        )
        hasta = min(
            fin_arg,
            tramo_fin,
        )

        if hasta > desde:
            total += int(
                (
                    hasta - desde
                ).total_seconds()
            )

        cursor_fecha += timedelta(days=1)

    return max(0, total)
