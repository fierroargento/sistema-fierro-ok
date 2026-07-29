"""
Reglas puras del CRM interno.

Este módulo no importa pedidos, canales ni automatizaciones.
"""

from datetime import datetime

from services.catalogos_comerciales import (
    importe_a_centavos,
)


TIPOS_CLIENTE = frozenset(
    {
        "persona",
        "empresa",
    }
)

ESTADOS_CLIENTE = frozenset(
    {
        "potencial",
        "cliente",
        "inactivo",
    }
)

CANALES_IDENTIDAD = frozenset(
    {
        "mercadolibre",
        "tiendanube",
        "whatsapp",
        "presencial",
        "mayorista",
        "otro",
    }
)

ESTADOS_OPORTUNIDAD = frozenset(
    {
        "abierta",
        "ganada",
        "perdida",
        "cancelada",
    }
)

TIPOS_ACTIVIDAD = frozenset(
    {
        "nota",
        "tarea",
        "llamada",
        "reunion",
        "email",
        "whatsapp",
    }
)

ESTADOS_ACTIVIDAD = frozenset(
    {
        "pendiente",
        "completada",
        "cancelada",
    }
)


def _normalizar_opcion(
    valor,
    opciones,
    nombre,
):
    normalizado = str(
        valor or ""
    ).strip().lower()

    if normalizado not in opciones:
        raise ValueError(
            f"{nombre} inválido."
        )

    return normalizado


def normalizar_tipo_cliente(valor):
    return _normalizar_opcion(
        valor,
        TIPOS_CLIENTE,
        "Tipo de cliente",
    )


def normalizar_estado_cliente(valor):
    return _normalizar_opcion(
        valor,
        ESTADOS_CLIENTE,
        "Estado de cliente",
    )


def normalizar_canal_identidad(valor):
    return _normalizar_opcion(
        valor,
        CANALES_IDENTIDAD,
        "Canal de identidad",
    )


def normalizar_estado_oportunidad(valor):
    return _normalizar_opcion(
        valor,
        ESTADOS_OPORTUNIDAD,
        "Estado de oportunidad",
    )


def normalizar_tipo_actividad(valor):
    return _normalizar_opcion(
        valor,
        TIPOS_ACTIVIDAD,
        "Tipo de actividad",
    )


def validar_probabilidad(valor):
    try:
        probabilidad = int(
            str(valor or "0").strip()
        )
    except ValueError as error:
        raise ValueError(
            "La probabilidad no es válida."
        ) from error

    if not 0 <= probabilidad <= 100:
        raise ValueError(
            "La probabilidad debe estar "
            "entre 0 y 100."
        )

    return probabilidad


def fecha_opcional(valor):
    texto = str(
        valor or ""
    ).strip()

    if not texto:
        return None

    try:
        return datetime.strptime(
            texto,
            "%Y-%m-%d",
        )
    except ValueError as error:
        raise ValueError(
            "La fecha debe tener formato AAAA-MM-DD."
        ) from error


def configurar_importe_oportunidad(
    oportunidad,
    importe,
):
    if oportunidad is None:
        raise ValueError(
            "No se recibió la oportunidad."
        )

    oportunidad.importe_estimado_centavos = (
        importe_a_centavos(
            importe or "0"
        )
    )

    return oportunidad


def cambiar_estado_oportunidad(
    oportunidad,
    estado,
    *,
    db_session,
    commit=True,
):
    if oportunidad is None:
        raise ValueError(
            "No se recibió la oportunidad."
        )

    oportunidad.estado = (
        normalizar_estado_oportunidad(
            estado
        )
    )

    if commit:
        try:
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    return oportunidad


def crm_habilita_automatizaciones(
    modulo_crm,
):
    """
    Guardia futura explícita.

    Aun con CRM activo, las automatizaciones requerirán
    una habilitación independiente futura.
    """
    return False
