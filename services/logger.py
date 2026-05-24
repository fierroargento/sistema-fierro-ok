import logging


def get_app_logger(nombre):
    """
    Logger central del sistema.

    APB:
    - No configura handlers propios si la app ya los tiene.
    - Compatible con Render stdout.
    - Compatible con Sentry cuando sentry_sdk está activo.
    """

    logger = logging.getLogger(nombre)
    logger.setLevel(logging.INFO)

    return logger