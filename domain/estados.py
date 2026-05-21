class Estado:
    # CARGA
    CARGANDO = "Cargando Pedido"

    # PREPARACIÓN
    ETIQUETA_LISTA = "Etiqueta Lista"
    ETIQUETA_IMPRESA = "Etiqueta Impresa"
    EMBALADO = "Embalado"

    # LOGÍSTICA
    DESPACHADO = "Despachado"
    VERIFICAR_DESTINO = "Verificar llegada a destino"
    LISTO_RETIRAR = "Listo para retirar"

    # EXCEPCIONES
    DEMORA = "Con demora de entrega"
    DEMORA_ENTREGA = DEMORA

    RECLAMO = "Con reclamo en transporte"
    RECLAMO_TRANSPORTE = RECLAMO

    NO_ENTREGADO = "No entregado"
    RECLAMAR_ML = "Reclamar a Mercado Libre"
    CANCELADO = "Cancelado"

    # FINAL
    ENTREGADO = "Entregado"
    FINALIZADO = "Finalizado"


ESTADOS_POST_DESPACHO = [
    Estado.DESPACHADO,
    Estado.DEMORA,
    Estado.RECLAMO,
    Estado.VERIFICAR_DESTINO,
    Estado.LISTO_RETIRAR,
    Estado.NO_ENTREGADO,
]

ESTADOS_FINALES = [
    Estado.ENTREGADO,
    Estado.FINALIZADO,
    Estado.CANCELADO,
]

ESTADOS_CERRADOS = ESTADOS_FINALES + [
    Estado.NO_ENTREGADO,
    Estado.RECLAMAR_ML,
]

ESTADOS_RECLAMO = [
    Estado.DEMORA,
    Estado.RECLAMO,
]

ESTADOS_ACTIVOS = [
    Estado.CARGANDO,
    Estado.ETIQUETA_LISTA,
    Estado.ETIQUETA_IMPRESA,
    Estado.EMBALADO,
    Estado.DESPACHADO,
    Estado.DEMORA,
    Estado.RECLAMO,
    Estado.VERIFICAR_DESTINO,
    Estado.LISTO_RETIRAR,
]