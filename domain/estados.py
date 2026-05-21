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