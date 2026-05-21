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
    RECLAMO = "Con reclamo en transporte"
    NO_ENTREGADO = "No entregado"

    # FINAL
    ENTREGADO = "Entregado"
    FINALIZADO = "Finalizado"