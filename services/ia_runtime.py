from extensions import db
from models.estado_conversacional_pedido import (
    EstadoConversacionalPedido,
)
from models.evento_operativo import EventoOperativo
from services.conversacional import (
    actualizar_estado_conversacional_service,
)
from services.eventos_operativos import (
    registrar_evento_operativo_service,
)
from services.horario_operativo import (
    IA_TIMEOUT_RESPUESTA_SEGUNDOS,
    ia_ahora_utc,
    ia_segundos_operativos_entre,
)
from services.ia_mensajes import (
    ia_escalar_si_timeout_operativo_service,
)


def actualizar_estado_conversacional_ia(
    pedido,
    **kwargs,
):
    return actualizar_estado_conversacional_service(
        pedido,
        EstadoConversacionalPedido,
        db,
        **kwargs,
    )


def registrar_evento_operativo_ia(
    **kwargs,
):
    return registrar_evento_operativo_service(
        EventoOperativo,
        db,
        **kwargs,
    )


def ia_escalar_si_timeout_operativo(
    pedido,
    canal="",
    motivo="Sin respuesta del comprador",
):
    """Escala timeout usando dependencias canónicas."""
    return ia_escalar_si_timeout_operativo_service(
        pedido,
        actualizar_estado_conversacional_ia,
        registrar_evento_operativo_ia,
        db.session,
        ia_segundos_operativos_entre,
        ia_ahora_utc,
        IA_TIMEOUT_RESPUESTA_SEGUNDOS,
        canal=canal,
        motivo=motivo,
    )
