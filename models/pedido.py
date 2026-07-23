"""Modelo central de pedidos del sistema."""

from extensions import db
from services.fechas import ahora_utc_naive


class Pedido(db.Model):
    __tablename__ = "pedido"

    origen = db.Column(db.String(30))
    ml_cuenta_id = db.Column(db.Integer, db.ForeignKey("mercado_libre_cuenta.id"), nullable=True, index=True)
    ml_seller_id = db.Column(db.String(50), index=True)
    ml_pack_id = db.Column(db.String(50))
    ml_order_status = db.Column(db.String(50))
    ml_shipping_status = db.Column(db.String(50))
    ml_shipping_id = db.Column(db.String(50))
    ml_logistic_type = db.Column(db.String(50))
    ml_shipping_mode = db.Column(db.String(50))
    ultima_sync_ml = db.Column(db.DateTime)

    # =====================
    # TIENDA NUBE
    # =====================
    tn_order_id = db.Column(db.String(50), index=True)
    tn_order_number = db.Column(db.String(50))
    tn_order_status = db.Column(db.String(50))
    tn_payment_status = db.Column(db.String(50))
    tn_paid_at = db.Column(db.DateTime)
    tn_cancelled_at = db.Column(db.DateTime)
    tn_fulfillment_id = db.Column(db.String(50))
    tn_fulfillment_status = db.Column(db.String(80))
    tn_shipping_type = db.Column(db.String(80))
    tn_shipping_carrier = db.Column(db.String(100))
    tn_shipping_option = db.Column(db.String(200))
    tn_tracking_number = db.Column(db.String(100))
    tn_tracking_url = db.Column(db.String(300))
    ultima_sync_tn = db.Column(db.DateTime)

    # =====================
    # APB MERCADO LIBRE
    # =====================
    ml_buyer_id = db.Column(db.String(50))
    ml_buyer_nickname = db.Column(db.String(120))
    ml_nombre_real = db.Column(db.Boolean, default=False)
    ml_datos_fiscales_ok = db.Column(db.Boolean, default=False)
    ml_billing_nombre = db.Column(db.String(200))
    ml_billing_documento = db.Column(db.String(30))
    ml_billing_direccion = db.Column(db.String(300))
    ml_campos_faltantes = db.Column(db.Text)
    ml_mensaje_contacto = db.Column(db.Text)
    contacto_iniciado = db.Column(db.Boolean, default=False)
    fecha_contacto = db.Column(db.DateTime)
    ml_mensajes_pendientes = db.Column(db.Boolean, default=False)
    ml_mensajes_pendientes_count = db.Column(db.Integer, default=0)
    ultima_sync_mensajes_ml = db.Column(db.DateTime)

    # =====================
    # IA RECOLECTOR ML / ACORDÁS (FASE 4 - ANÁLISIS + AUTOCOMPLETADO SEGURO)
    # =====================
    ia_recolector_estado = db.Column(db.String(40))
    ia_datos_detectados = db.Column(db.Text)
    ia_faltantes = db.Column(db.Text)
    ia_resumen = db.Column(db.Text)
    ia_requiere_operador = db.Column(db.Boolean, default=False)
    # WhatsApp Bot
    wa_estado            = db.Column(db.String(100))
        # APB:
    # Subestado operacional del flujo WhatsApp.
    # Evita depender de IA libre para pasos críticos.
    wa_paso_operativo = db.Column(db.String(100))
    wa_ultimo_contacto   = db.Column(db.DateTime)
    wa_recordatorio_1    = db.Column(db.Boolean, default=False)
    wa_recordatorio_2    = db.Column(db.Boolean, default=False)
    wa_listo_retirar_enviado = db.Column(db.Boolean, default=False)
    wa_postventa_enviada = db.Column(db.Boolean, default=False)
    correo_sucursales_ofrecidas = db.Column(db.Text)
    costo_envio = db.Column(db.Float)
    costo_envio_sucursal = db.Column(db.Float)
    costo_envio_domicilio = db.Column(db.Float)
    ia_ultimo_mensaje_hash = db.Column(db.String(80))
    ia_ultimo_analisis = db.Column(db.DateTime)
    ia_error = db.Column(db.Text)
    # IA RECOLECTOR ML / ACORDÁS (FASE 3 - RESPUESTA ASISTIDA)
    ia_respuesta_sugerida = db.Column(db.Text)
    ia_sucursales_ofrecidas = db.Column(db.Text)  # JSON con IDs de sucursales ofrecidas al cliente
    ia_respuesta_enviada_hash = db.Column(db.String(80))
    ia_ultima_respuesta_enviada = db.Column(db.DateTime)

    # =====================
    # APB CONVERSACIONAL ML / WA
    # =====================
    ia_esperando_respuesta = db.Column(db.Boolean, default=False)
    ia_ultimo_mensaje_bot = db.Column(db.DateTime)
    ia_ultimo_mensaje_cliente = db.Column(db.DateTime)
    ia_canal_activo = db.Column(db.String(30))
    ia_ultimo_timeout_operador = db.Column(db.DateTime)

    # =====================
    # APB CANAL MANAGER
    # =====================
    ultimo_mensaje_automatico_texto = db.Column(db.Text)
    ultimo_mensaje_automatico_canal = db.Column(db.String(30))
    ultimo_mensaje_automatico_fecha = db.Column(db.DateTime)

    # =====================
    # APB RECLAMOS ML
    # =====================
    ml_claim_id = db.Column(db.String(50))
    ml_claim_abierto = db.Column(db.Boolean, default=False)
    ml_claim_status = db.Column(db.String(50))
    ml_claim_reason = db.Column(db.String(200))
    ultima_sync_claim_ml = db.Column(db.DateTime)

    id = db.Column(db.Integer, primary_key=True)

    cliente = db.Column(db.String(120), nullable=False)
    dni = db.Column(db.String(20))
    telefono = db.Column(db.String(30))
    mail = db.Column(db.String(120))

    canal = db.Column(db.String(50), nullable=False)
    id_venta = db.Column(db.String(50))

    ml_tipo = db.Column(db.String(50))
    empresa_envio = db.Column(db.String(50))
    tipo_entrega = db.Column(db.String(30))

    direccion = db.Column(db.String(200))
    codigo_postal = db.Column(db.String(10))
    localidad = db.Column(db.String(100))
    provincia = db.Column(db.String(100))
    cpa = db.Column(db.String(20))
    ubicacion_fuente = db.Column(db.String(50))
    ubicacion_confianza = db.Column(db.String(30))
    latitud_cliente = db.Column(db.Float)
    longitud_cliente = db.Column(db.Float)
    observaciones = db.Column(db.String(300))

    sucursal_nombre = db.Column(db.String(150))
    autorizado_nombre = db.Column(db.String(120))
    autorizado_dni = db.Column(db.String(20))
    autorizado_telefono = db.Column(db.String(30))

    seguimiento = db.Column(db.String(100))
    andreani_estado = db.Column(db.String(200))
    andreani_ultima_sync = db.Column(db.DateTime)
    andreani_eventos_json = db.Column(db.Text)
    tracking_estado_externo = db.Column(db.String(300))
    tracking_ultima_sync = db.Column(db.DateTime)
    tracking_error = db.Column(db.Text)
    tracking_transportista = db.Column(db.String(80))
    tracking_url_consultada = db.Column(db.String(500))
    comprobante_dux_archivo = db.Column(db.String(255))
    comprobante_pago_archivo = db.Column(db.String(255))
    agregado_pendiente_revision = db.Column(db.Boolean, default=False)
    agregado_revision_fecha = db.Column(db.DateTime)
    agregado_revision_usuario = db.Column(db.String(100))
    etiqueta_archivo = db.Column(db.String(255))
    estado = db.Column(db.String(50), default="Cargando Pedido")

    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive)
    fecha_etiqueta_impresa = db.Column(db.DateTime)
    fecha_embalado = db.Column(db.DateTime)
    fecha_despachado = db.Column(db.DateTime)
    fecha_entregado = db.Column(db.DateTime)

    # =====================
    # CAMPOS RECLAMOS
    # =====================
    numero_reclamo = db.Column(db.String(100))
    fecha_hora_reclamo = db.Column(db.DateTime)
    ultima_revision_reclamo = db.Column(db.DateTime)
    observacion_reclamo = db.Column(db.String(300))

    # =====================
    # NO ENTREGADO
    # =====================
    motivo_no_entregado = db.Column(db.String(300))
    # =====================
    # DEVOLUCIÓN
    # =====================
    fecha_devolucion = db.Column(db.DateTime)
    estado_devolucion = db.Column(db.String(50))  # pendiente / parcial / completa
    observacion_devolucion = db.Column(db.String(300))

    # =====================
    # RECLAMO MERCADO LIBRE POR DEVOLUCIÓN
    # =====================
    numero_reclamo_ml = db.Column(db.String(100))
    resultado_reclamo_ml = db.Column(db.String(50))  # reintegrado / rechazado / parcial
    monto_recuperado_ml = db.Column(db.Float)
    observacion_reclamo_ml = db.Column(db.String(300))


    items = db.relationship("PedidoItem", cascade="all, delete-orphan")
