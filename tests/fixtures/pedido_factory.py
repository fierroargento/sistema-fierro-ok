"""
tests/fixtures/pedido_factory.py
─────────────────────────────────
Fábrica de pedidos falsos para tests.
No requiere DB, Flask ni ninguna dependencia externa.
Todos los campos del modelo Pedido están representados con defaults sensatos.
"""


class PedidoFake:
    """
    Objeto simple que imita el modelo Pedido de SQLAlchemy.
    Usarlo directamente en tests que prueban funciones puras:
    normalizar_telefono, ia_cp_valido, despacho_completo, motor_bloqueo, etc.
    """

    def __init__(self, **kwargs):
        # Identidad
        self.id = kwargs.get("id", 1)

        # Canal y tipo
        self.canal = kwargs.get("canal", "Mercado Libre")
        self.ml_tipo = kwargs.get("ml_tipo", "Acordás la Entrega")
        self.origen = kwargs.get("origen", "ml")

        # Estado operativo
        self.estado = kwargs.get("estado", "Cargando Pedido")

        # Datos del comprador
        self.cliente = kwargs.get("cliente", "RUBEN OSCAR GOMEZ")
        self.ml_buyer_nickname = kwargs.get("ml_buyer_nickname", "")
        self.ml_billing_nombre = kwargs.get("ml_billing_nombre", "")
        self.ml_billing_documento = kwargs.get("ml_billing_documento", "")
        self.ml_nombre_real = kwargs.get("ml_nombre_real", False)
        self.dni = kwargs.get("dni", "")
        self.telefono = kwargs.get("telefono", "")
        self.mail = kwargs.get("mail", "")

        # Entrega
        self.empresa_envio = kwargs.get("empresa_envio", "")
        self.tipo_entrega = kwargs.get("tipo_entrega", "")
        self.direccion = kwargs.get("direccion", "")
        self.codigo_postal = kwargs.get("codigo_postal", "")
        self.localidad = kwargs.get("localidad", "")
        self.provincia = kwargs.get("provincia", "")
        self.sucursal_nombre = kwargs.get("sucursal_nombre", "")

        # Autorizado
        self.autorizado_nombre = kwargs.get("autorizado_nombre", "")
        self.autorizado_dni = kwargs.get("autorizado_dni", "")
        self.autorizado_telefono = kwargs.get("autorizado_telefono", "")

        # Venta
        self.id_venta = kwargs.get("id_venta", "2000016334304086")
        self.ml_pack_id = kwargs.get("ml_pack_id", "")
        self.ml_order_status = kwargs.get("ml_order_status", "confirmed")
        self.ml_shipping_status = kwargs.get("ml_shipping_status", "")
        self.ml_logistic_type = kwargs.get("ml_logistic_type", "")
        self.ml_shipping_mode = kwargs.get("ml_shipping_mode", "")
        self.ml_shipping_id = kwargs.get("ml_shipping_id", "")

        # Tienda Nube
        self.tn_order_id = kwargs.get("tn_order_id", "")
        self.tn_order_status = kwargs.get("tn_order_status", "")
        self.tn_payment_status = kwargs.get("tn_payment_status", "")
        self.tn_cancelled_at = kwargs.get("tn_cancelled_at", None)
        self.tn_fulfillment_status = kwargs.get("tn_fulfillment_status", "")
        self.tn_shipping_type = kwargs.get("tn_shipping_type", "")

        # Seguimiento
        self.seguimiento = kwargs.get("seguimiento", "")
        self.etiqueta_archivo = kwargs.get("etiqueta_archivo", "")

        # IA recolector
        self.ia_recolector_estado = kwargs.get("ia_recolector_estado", "")
        self.ia_datos_detectados = kwargs.get("ia_datos_detectados", "")
        self.ia_faltantes = kwargs.get("ia_faltantes", "")
        self.ia_resumen = kwargs.get("ia_resumen", "")
        self.ia_requiere_operador = kwargs.get("ia_requiere_operador", False)
        self.ia_ultimo_mensaje_hash = kwargs.get("ia_ultimo_mensaje_hash", "")
        self.ia_canal_activo = kwargs.get("ia_canal_activo", "")

        # WhatsApp
        self.wa_estado = kwargs.get("wa_estado", "")
        self.wa_ultimo_contacto = kwargs.get("wa_ultimo_contacto", None)
        self.wa_listo_retirar_enviado = kwargs.get("wa_listo_retirar_enviado", False)
        self.wa_postventa_enviada = kwargs.get("wa_postventa_enviada", False)

        # ML mensajes
        self.ml_mensajes_pendientes = kwargs.get("ml_mensajes_pendientes", False)
        self.ml_mensajes_pendientes_count = kwargs.get("ml_mensajes_pendientes_count", 0)
        self.contacto_iniciado = kwargs.get("contacto_iniciado", False)

        # Reclamos
        self.ml_claim_id = kwargs.get("ml_claim_id", "")
        self.ml_claim_abierto = kwargs.get("ml_claim_abierto", False)
        self.numero_reclamo = kwargs.get("numero_reclamo", "")

        # Agregado
        self.agregado_pendiente_revision = kwargs.get("agregado_pendiente_revision", False)
        self.agregado_revision_fecha = kwargs.get("agregado_revision_fecha", None)
        self.agregado_revision_usuario = kwargs.get("agregado_revision_usuario", "")

        # Fechas
        self.fecha_creacion = kwargs.get("fecha_creacion", None)
        self.fecha_etiqueta_impresa = kwargs.get("fecha_etiqueta_impresa", None)
        self.fecha_embalado = kwargs.get("fecha_embalado", None)
        self.fecha_despachado = kwargs.get("fecha_despachado", None)
        self.fecha_entregado = kwargs.get("fecha_entregado", None)

        # Items (lista de objetos con sku, descripcion, cantidad)
        self.items = kwargs.get("items", [])

        # Correo sucursales
        self.correo_sucursales_ofrecidas = kwargs.get("correo_sucursales_ofrecidas", "")
        self.ia_sucursales_ofrecidas = kwargs.get("ia_sucursales_ofrecidas", "")

        # Misc
        self.observaciones = kwargs.get("observaciones", "")
        self.costo_envio = kwargs.get("costo_envio", None)
        self.ml_datos_fiscales_ok = kwargs.get("ml_datos_fiscales_ok", False)
        self.ml_campos_faltantes = kwargs.get("ml_campos_faltantes", "")
        self.comprobante_dux_archivo = kwargs.get("comprobante_dux_archivo", "")
        self.tracking_estado_externo = kwargs.get("tracking_estado_externo", "")
        self.ia_esperando_respuesta = kwargs.get("ia_esperando_respuesta", False)


class ItemFake:
    """Item de pedido fake."""

    def __init__(self, sku="PP6040", descripcion="Parrilla 60x40", cantidad=1):
        self.sku = sku
        self.descripcion = descripcion
        self.cantidad = cantidad


# ── Factories listas para usar ────────────────────────────────────────────────

def pedido_ml_acordas(empresa_envio="Vía Cargo", tipo_entrega="Sucursal", **kwargs):
    """ML Acordás la Entrega con datos mínimos completos."""
    return PedidoFake(
        canal="Mercado Libre",
        ml_tipo="Acordás la Entrega",
        empresa_envio=empresa_envio,
        tipo_entrega=tipo_entrega,
        cliente="RUBEN OSCAR GOMEZ",
        dni="17144245",
        telefono="5491164445369",
        direccion="Av. Ángel Torcuato de Alvear 459",
        codigo_postal="1612",
        localidad="Don Torcuato",
        provincia="Buenos Aires",
        sucursal_nombre="Agencia Don Torcuato",
        items=[ItemFake()],
        **kwargs,
    )


def pedido_ml_mercado_envios(**kwargs):
    """ML Mercado Envíos (etiqueta directa)."""
    return PedidoFake(
        canal="Mercado Libre",
        ml_tipo="Mercado Envíos",
        empresa_envio="Mercado Envíos",
        tipo_entrega="Domicilio",
        seguimiento="ML123456789",
        etiqueta_archivo="etiqueta_ml.pdf",
        items=[ItemFake()],
        **kwargs,
    )


def pedido_tn(**kwargs):
    """Tienda Nube base."""
    return PedidoFake(
        canal="Tienda Nube",
        ml_tipo="",
        tn_order_id="TN123",
        tn_order_status="paid",
        tn_payment_status="paid",
        items=[ItemFake()],
        **kwargs,
    )
