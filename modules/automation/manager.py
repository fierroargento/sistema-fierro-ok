from apscheduler.schedulers.background import BackgroundScheduler


_scheduler = None


def iniciar_scheduler(
    job_ml_mensajes,
    job_wa_timers,
):
    """
    Inicializa scheduler APB central.

    IMPORTANTE:
    No contiene lógica de negocio.
    Solo orquesta jobs existentes.

    Blindaje APB:
    - max_instances=1 evita que un mismo job se solape consigo mismo.
    - coalesce=True evita acumulación de ejecuciones si hubo demora.
    - replace_existing=True permite reinicio limpio del scheduler.
    """

    global _scheduler

    # Evita doble scheduler en reloads/debug dentro del mismo proceso.
    if _scheduler:
        return _scheduler

    scheduler = BackgroundScheduler(
        daemon=True
    )

    scheduler.add_job(
        job_ml_mensajes,
        "interval",
        minutes=5,
        id="ml_mensajes",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )

    scheduler.add_job(
        job_wa_timers,
        "interval",
        minutes=5,
        id="wa_timers",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )

    scheduler.start()

    print(
        "[AUTOMATION MANAGER] "
        "Scheduler iniciado: "
        "ml_mensajes + wa_timers"
    )

    _scheduler = scheduler

    return scheduler