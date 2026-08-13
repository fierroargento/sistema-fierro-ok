"""Alertas administrativas de vencimientos de costos productivos."""

from datetime import date, timedelta


def construir_alertas_cuentas_pagar(obligaciones, *, hoy=None, dias_aviso=7, url=None):
    """Resume vencimientos sin exponer datos de otra organización."""
    hoy = hoy or date.today()
    limite = hoy + timedelta(days=int(dias_aviso))
    vencidas = 0
    proximas = 0

    for obligacion in obligaciones:
        if obligacion.estado in {"pagada", "anulada"}:
            continue
        if obligacion.fecha_vencimiento < hoy:
            vencidas += 1
        elif obligacion.fecha_vencimiento <= limite:
            proximas += 1

    alertas = []
    if vencidas:
        alertas.append({
            "tipo": "roja",
            "texto": f"{vencidas} obligación(es) de costos vencida(s)",
            "url": url,
            "boton": "Revisar pagos",
        })
    if proximas:
        alertas.append({
            "tipo": "amarilla",
            "texto": f"{proximas} obligación(es) de costos vence(n) en los próximos {dias_aviso} días",
            "url": url,
            "boton": "Ver vencimientos",
        })
    return alertas
