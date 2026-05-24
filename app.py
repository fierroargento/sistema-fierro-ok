import os
import re
import json
import hashlib
import hmac
import base64
import logging
import sentry_sdk
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlencode
import pandas as pd
import numpy as np
import fitz
import cloudinary
import cloudinary.uploader
from datetime import datetime, timedelta, time, timezone
from functools import wraps
from zoneinfo import ZoneInfo


SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[FlaskIntegration()],
        traces_sample_rate=float(
            os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.05")
        ),
        environment=os.getenv(
            "RENDER_SERVICE_NAME",
            "development",
        ),
    )

from flask import Flask, request, redirect, render_template, url_for, jsonify, send_from_directory, session, flash
from sentry_sdk.integrations.flask import FlaskIntegration
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, inspect, or_
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from domain.estados import (
    Estado,
    ESTADOS_FINALES,
    ESTADOS_CERRADOS,
)

from modules.whatsapp.runtime import (
    wa_ventana_24h_abierta_service,
    registrar_whatsapp_mensaje_service,
)

from services.ml_importacion import (
    ml_prevalidar_importacion_order_service,
    ml_preparar_pedido_base_importacion_service,
    ml_intentar_contacto_inicial_acordas_service,
    ml_limpiar_pedidos_ml_no_operables_existentes_service,
    ml_procesar_orders_sync_service,
    ml_actualizar_resumen_sync_service,                
)    

from services.telefonos import normalizar_telefono_service
from services.busqueda_pedidos import buscar_pedido_activo_por_telefono_service
from services.ml_operacion import ml_validar_orden_operable_antes_de_despacho_service
from services.ml_items import ml_sincronizar_items_pedido_service
from services.ml_etiquetas import (
    ml_preparar_etiqueta_mercado_envios_service,
)

from services.tracking_info import tracking_info_pedido_service

from services.ml_ignorados import (
    ml_pedido_esta_ignorado_service,
    ml_registrar_pedido_ignorado_service,
    ml_registrar_order_ignorado_service,
)

from services.ml_estados import (
    ml_estado_order_service,
    ml_estado_shipment_service,
    ml_order_esta_entregado_service,
    ml_logistica_no_operable_service,
    ml_es_envio_full_service,
    ml_es_mercado_envios_order_service,
    ml_envio_ya_despachado_service,
    ml_order_debe_omitirse_service,
    ml_marcar_pedido_finalizado_por_entrega_service,
    ml_borrar_pedido_importado_si_corresponde_service,                
)

from services.ml_claims import (
    ml_pedido_tiene_claim_service,
    ml_marcar_claim_en_pedido_service,
    ml_sync_claims_pedidos_operativos_service,
    ml_obtener_claim_de_order_service,    
)

from services.conversacional import (
    obtener_estado_conversacional_service,
    actualizar_estado_conversacional_service,
)

from services.eventos_operativos import registrar_evento_operativo_service

from services.ia import (
    ia_chat_completion_json_service,
    ia_llamar_openai_chat_service,
)

from services.workflow import (
    aplicar_autoavance_post_despacho_service,
    actualizar_estado_automatico_service,
)
from services.andreani import andreani_configurada, andreani_trazas_envio, resumen_evento_andreani
from services.tracking_externo import consultar_tracking_url, interpretar_estado_logistico, consultar_correo_formulario
from services.tracking_workflow import aplicar_estado_tracking_seguro_service
from services.pedidos_estado import (
    requiere_contacto_cliente,
    despacho_completo,
    siguiente_estado,
    ESTADOS_POST_DESPACHO,
    ESTADOS_DESPACHO_OPERATIVO,
)
from services.canal_manager import (
    puede_enviar_mensaje,
    registrar_envio_automatico,
)

from services.motor_bloqueo import (
    validar_datos_basicos,
    validar_datos_entrega,
    validar_datos_ml,
    validar_transportes,
    validar_regla_via_cargo_pp6040,
    validar_transporte_obligatorio,
)

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

database_url = os.getenv("DATABASE_URL", "").strip()
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///pedidos.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

_engine_options = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

if database_url:
    _engine_options["connect_args"] = {
        "sslmode": "require"
    }

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = _engine_options
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "uploads")
_secret_key = os.getenv("SECRET_KEY", "")
if not _secret_key:
    raise RuntimeError("SECRET_KEY no está configurada. Definila en las variables de entorno.")

app.config["SECRET_KEY"] = _secret_key

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)

ROLES_SISTEMA = ["admin", "carga", "despacho"]



class UsuarioSistema(db.Model):
    __tablename__ = "usuario_sistema"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    rol = db.Column(db.String(30), nullable=False, default="carga")
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    creado_por = db.Column(db.String(80))
    actualizado_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Auditoria(db.Model):
    __tablename__ = "auditoria"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer)
    username = db.Column(db.String(80))
    nombre = db.Column(db.String(120))
    rol = db.Column(db.String(30))
    accion = db.Column(db.String(120), nullable=False)
    entidad = db.Column(db.String(80))
    entidad_id = db.Column(db.String(80))
    detalle = db.Column(db.Text)
    fecha = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ip = db.Column(db.String(80))
    metodo = db.Column(db.String(10))
    path = db.Column(db.String(300))


class Pedido(db.Model):
    origen = db.Column(db.String(30))
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

    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
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


class PedidoItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedido.id"))
    sku = db.Column(db.String(50))
    descripcion = db.Column(db.String(200))
    cantidad = db.Column(db.Integer)

    # =====================
    # DEVOLUCIÓN POR ITEM
    # =====================
    cantidad_devuelta_ok = db.Column(db.Integer)
    cantidad_devuelta_danada = db.Column(db.Integer)
    estado_devolucion_item = db.Column(db.String(50))  # ok / parcial / danado
    observacion_devolucion_item = db.Column(db.String(300))




class PedidoAgregadoAPB(db.Model):
    """Agrupador APB de items agregados manualmente a un pedido.
    Guarda comprobante DUX, comprobante de pago y snapshot de los items agregados.
    """
    __tablename__ = "pedido_agregado_apb"

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedido.id"), nullable=False, index=True)
    usuario = db.Column(db.String(100))
    rol = db.Column(db.String(50))
    fecha = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    comprobante_dux_url = db.Column(db.String(500), nullable=False)
    comprobante_dux_public_id = db.Column(db.String(255))
    comprobante_pago_url = db.Column(db.String(500), nullable=False)
    comprobante_pago_public_id = db.Column(db.String(255))
    items_json = db.Column(db.Text, nullable=False)


class NotaPedido(db.Model):
    """Bitácora de notas internas por pedido. Solo visible para admin y carga."""
    id          = db.Column(db.Integer, primary_key=True)
    pedido_id   = db.Column(db.Integer, db.ForeignKey("pedido.id"), nullable=False)
    texto       = db.Column(db.Text, nullable=False)
    usuario     = db.Column(db.String(100))   # username del operador
    rol         = db.Column(db.String(50))    # rol en el momento de crear
    fecha       = db.Column(db.DateTime, default=datetime.utcnow)



class ConfiguracionSistema(db.Model):
    """Configuraciones simples para escalar a CRM sin hardcodes dispersos."""
    __tablename__ = "configuracion_sistema"
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(100), unique=True, nullable=False, index=True)
    valor = db.Column(db.String(300))
    descripcion = db.Column(db.Text)
    actualizado_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TrackingEvento(db.Model):
    """Historial de eventos de tracking externo por pedido."""
    __tablename__ = "tracking_evento"
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedido.id"), nullable=False, index=True)
    empresa = db.Column(db.String(80))
    seguimiento = db.Column(db.String(100))
    estado = db.Column(db.String(300))
    clasificacion = db.Column(db.String(50))
    raw_json = db.Column(db.Text)
    origen = db.Column(db.String(50))
    fecha_evento = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class EventoOperativo(db.Model):
    """Registro APB de eventos operativos/conversacionales del pedido.

    Esta tabla no modifica el flujo actual.
    Sirve como base futura para auditoría, motor conversacional,
    debugging, métricas y arquitectura SaaS.
    """
    __tablename__ = "evento_operativo"

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedido.id"), nullable=True, index=True)

    tipo_evento = db.Column(db.String(120), nullable=False, index=True)
    origen = db.Column(db.String(50))          # sistema / bot / operador / webhook / scheduler
    canal = db.Column(db.String(30))           # ml / wa / tn / sistema
    owner = db.Column(db.String(30))           # bot / operador / sistema

    estado_conversacional = db.Column(db.String(80))
    flujo_base = db.Column(db.String(80))

    payload_json = db.Column(db.Text)
    resultado = db.Column(db.String(80))
    detalle = db.Column(db.Text)

    usuario = db.Column(db.String(100))
    procesado = db.Column(db.Boolean, default=False, index=True)

    fecha = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class EstadoConversacionalPedido(db.Model):
    """Estado conversacional/ownership APB del pedido.

    NO reemplaza todavía flags legacy.
    Convive con el sistema actual mientras migramos.
    """
    __tablename__ = "estado_conversacional_pedido"

    id = db.Column(db.Integer, primary_key=True)

    pedido_id = db.Column(
        db.Integer,
        db.ForeignKey("pedido.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    owner_actual = db.Column(db.String(30), default="bot", index=True)
    estado_conversacional = db.Column(
        db.String(80),
        default="recolectando_datos",
        index=True,
    )

    canal_activo = db.Column(db.String(30), default="ml")
    flujo_base = db.Column(db.String(80))

    takeover_activo = db.Column(db.Boolean, default=False)
    bot_pausado = db.Column(db.Boolean, default=False)

    cross_sell_activo = db.Column(db.Boolean, default=False)

    ultima_interaccion = db.Column(db.DateTime)
    ultimo_mensaje_cliente = db.Column(db.DateTime)
    ultimo_mensaje_bot = db.Column(db.DateTime)

    fecha_creacion = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        index=True,
    )

    fecha_actualizacion = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )

class WhatsAppMensaje(db.Model):
    """Historial real de conversación WhatsApp API asociado al pedido."""
    __tablename__ = "whatsapp_mensaje"
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedido.id"), index=True)
    telefono = db.Column(db.String(30), index=True)
    direccion = db.Column(db.String(10))  # in / out
    autor = db.Column(db.String(30))      # cliente / bot / operador / sistema
    texto = db.Column(db.Text)
    message_id_meta = db.Column(db.String(120), index=True)
    estado = db.Column(db.String(40))     # recibido / enviado / error / pendiente
    error = db.Column(db.Text)
    fecha = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(80), nullable=False, index=True)
    descripcion = db.Column(db.String(255), nullable=False, index=True)


class MercadoLibreCuenta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id_ml = db.Column(db.String(50))
    nickname = db.Column(db.String(120))
    access_token = db.Column(db.Text)
    refresh_token = db.Column(db.Text)
    token_expires_at = db.Column(db.DateTime)
    scope = db.Column(db.Text)
    estado_conexion = db.Column(db.String(30), default="desconectada")
    last_sync_at = db.Column(db.DateTime)
    last_sync_status = db.Column(db.String(30))
    last_sync_detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)



class PedidoIgnoradoML(db.Model):
    """Ventas de Mercado Libre eliminadas manualmente para que el sync no las reimporte al flujo operativo."""
    __tablename__ = "pedido_ignorado_ml"

    id = db.Column(db.Integer, primary_key=True)
    id_venta = db.Column(db.String(100), unique=True, nullable=False, index=True)
    motivo = db.Column(db.String(255))
    pedido_local_id = db.Column(db.Integer)
    usuario = db.Column(db.String(100))
    fecha = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class WebhookML(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(80))
    resource = db.Column(db.String(300))
    payload = db.Column(db.Text)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    ok = db.Column(db.Boolean, default=False)
    detalle = db.Column(db.Text)


class TiendaNubeCuenta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.String(50))
    estado_conexion = db.Column(db.String(30), default="configurada")
    last_sync_at = db.Column(db.DateTime)
    last_sync_status = db.Column(db.String(30))
    last_sync_detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TiendaNubeWebhookLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event = db.Column(db.String(120))
    tn_order_id = db.Column(db.String(50))
    payload = db.Column(db.Text)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    procesado = db.Column(db.Boolean, default=False)
    error = db.Column(db.Text)

def asegurar_columna_si_no_existe(nombre_columna, definicion_sql):
    inspector = inspect(db.engine)
    columnas = [col["name"] for col in inspector.get_columns("pedido")]

    if nombre_columna not in columnas:
        db.session.execute(text(f"ALTER TABLE pedido ADD COLUMN {nombre_columna} {definicion_sql}"))
        db.session.commit()

def asegurar_columna_item_si_no_existe(nombre_columna, definicion_sql):
    inspector = inspect(db.engine)
    columnas = [col["name"] for col in inspector.get_columns("pedido_item")]

    if nombre_columna not in columnas:
        db.session.execute(text(f"ALTER TABLE pedido_item ADD COLUMN {nombre_columna} {definicion_sql}"))
        db.session.commit()


def asegurar_columnas_extra():
    asegurar_columna_si_no_existe("etiqueta_archivo", "VARCHAR(255)")
    asegurar_columna_si_no_existe("andreani_estado", "VARCHAR(200)")
    asegurar_columna_si_no_existe("andreani_ultima_sync", "TIMESTAMP")
    asegurar_columna_si_no_existe("andreani_eventos_json", "TEXT")
    asegurar_columna_si_no_existe("tracking_estado_externo", "VARCHAR(300)")
    asegurar_columna_si_no_existe("tracking_ultima_sync", "TIMESTAMP")
    asegurar_columna_si_no_existe("tracking_error", "TEXT")
    asegurar_columna_si_no_existe("tracking_transportista", "VARCHAR(80)")
    asegurar_columna_si_no_existe("tracking_url_consultada", "VARCHAR(500)")
    asegurar_columna_si_no_existe("comprobante_dux_archivo", "VARCHAR(255)")
    asegurar_columna_si_no_existe("comprobante_pago_archivo", "VARCHAR(255)")
    asegurar_columna_si_no_existe("agregado_pendiente_revision", "BOOLEAN DEFAULT FALSE")
    asegurar_columna_si_no_existe("agregado_revision_fecha", "TIMESTAMP")
    asegurar_columna_si_no_existe("agregado_revision_usuario", "VARCHAR(100)")
    asegurar_columna_si_no_existe("sucursal_nombre", "VARCHAR(150)")
    asegurar_columna_si_no_existe("autorizado_nombre", "VARCHAR(120)")
    asegurar_columna_si_no_existe("autorizado_dni", "VARCHAR(20)")
    asegurar_columna_si_no_existe("autorizado_telefono", "VARCHAR(30)")
    asegurar_columna_si_no_existe("fecha_etiqueta_impresa", "TIMESTAMP")
    asegurar_columna_si_no_existe("fecha_embalado", "TIMESTAMP")
    asegurar_columna_si_no_existe("fecha_despachado", "TIMESTAMP")
    asegurar_columna_si_no_existe("fecha_entregado", "TIMESTAMP")
   # =====================
    # CAMPOS RECLAMOS
    # =====================
    asegurar_columna_si_no_existe("numero_reclamo", "TEXT")
    asegurar_columna_si_no_existe("fecha_hora_reclamo", "TIMESTAMP")
    asegurar_columna_si_no_existe("ultima_revision_reclamo", "TIMESTAMP")
    asegurar_columna_si_no_existe("observacion_reclamo", "TEXT")

    # =====================
    # NO ENTREGADO
    # =====================
    asegurar_columna_si_no_existe("motivo_no_entregado", "TEXT")
    # =====================
    # DEVOLUCIÓN
    # =====================
    asegurar_columna_si_no_existe("fecha_devolucion", "TIMESTAMP")
    asegurar_columna_si_no_existe("estado_devolucion", "TEXT")
    asegurar_columna_si_no_existe("observacion_devolucion", "TEXT")
    
    # =====================
    # RECLAMO MERCADO LIBRE POR DEVOLUCIÓN
    # =====================
    asegurar_columna_si_no_existe("numero_reclamo_ml", "TEXT")
    asegurar_columna_si_no_existe("resultado_reclamo_ml", "TEXT")
    asegurar_columna_si_no_existe("monto_recuperado_ml", "FLOAT")
    asegurar_columna_si_no_existe("observacion_reclamo_ml", "TEXT")

    # =====================
    # DEVOLUCIÓN POR ITEM
    # =====================
    asegurar_columna_item_si_no_existe("cantidad_devuelta_ok", "INTEGER")
    asegurar_columna_item_si_no_existe("cantidad_devuelta_danada", "INTEGER")
    asegurar_columna_item_si_no_existe("estado_devolucion_item", "TEXT")
    asegurar_columna_item_si_no_existe("observacion_devolucion_item", "TEXT")


def asegurar_columnas_integracion_ml():
    asegurar_columna_si_no_existe("origen", "VARCHAR(30)")
    asegurar_columna_si_no_existe("ml_pack_id", "VARCHAR(50)")
    asegurar_columna_si_no_existe("ml_order_status", "VARCHAR(50)")
    asegurar_columna_si_no_existe("ml_shipping_status", "VARCHAR(50)")
    asegurar_columna_si_no_existe("ml_shipping_id", "VARCHAR(50)")
    asegurar_columna_si_no_existe("ml_logistic_type", "VARCHAR(50)")
    asegurar_columna_si_no_existe("ml_shipping_mode", "VARCHAR(50)")
    asegurar_columna_si_no_existe("ultima_sync_ml", "TIMESTAMP")

    # =====================
    # APB MERCADO LIBRE
    # =====================
    asegurar_columna_si_no_existe("ml_buyer_id", "VARCHAR(50)")
    asegurar_columna_si_no_existe("ml_buyer_nickname", "VARCHAR(120)")
    asegurar_columna_si_no_existe("ml_nombre_real", "BOOLEAN DEFAULT FALSE")
    asegurar_columna_si_no_existe("ml_datos_fiscales_ok", "BOOLEAN DEFAULT FALSE")
    asegurar_columna_si_no_existe("ml_billing_nombre", "VARCHAR(200)")
    asegurar_columna_si_no_existe("ml_billing_documento", "VARCHAR(30)")
    asegurar_columna_si_no_existe("ml_billing_direccion", "VARCHAR(300)")
    asegurar_columna_si_no_existe("ml_campos_faltantes", "TEXT")
    asegurar_columna_si_no_existe("ml_mensaje_contacto", "TEXT")
    asegurar_columna_si_no_existe("contacto_iniciado", "BOOLEAN DEFAULT FALSE")
    asegurar_columna_si_no_existe("fecha_contacto", "TIMESTAMP")
    asegurar_columna_si_no_existe("ml_mensajes_pendientes", "BOOLEAN DEFAULT FALSE")
    asegurar_columna_si_no_existe("ml_mensajes_pendientes_count", "INTEGER DEFAULT 0")
    asegurar_columna_si_no_existe("ultima_sync_mensajes_ml", "TIMESTAMP")

    # =====================
    # IA RECOLECTOR ML / ACORDÁS (FASE 4 - ANÁLISIS + AUTOCOMPLETADO SEGURO)
    # =====================
    asegurar_columna_si_no_existe("ia_recolector_estado", "VARCHAR(40)")
    asegurar_columna_si_no_existe("ia_datos_detectados", "TEXT")
    asegurar_columna_si_no_existe("ia_faltantes", "TEXT")
    asegurar_columna_si_no_existe("ia_resumen", "TEXT")
    asegurar_columna_si_no_existe("ia_requiere_operador", "BOOLEAN DEFAULT FALSE")
    asegurar_columna_si_no_existe("wa_estado", "VARCHAR(100)")
    asegurar_columna_si_no_existe("wa_paso_operativo", "VARCHAR(100)")    
    asegurar_columna_si_no_existe("wa_ultimo_contacto", "TIMESTAMP")
    asegurar_columna_si_no_existe("wa_recordatorio_1", "BOOLEAN DEFAULT FALSE")
    asegurar_columna_si_no_existe("wa_recordatorio_2", "BOOLEAN DEFAULT FALSE")
    asegurar_columna_si_no_existe("wa_listo_retirar_enviado", "BOOLEAN DEFAULT FALSE")
    asegurar_columna_si_no_existe("wa_postventa_enviada", "BOOLEAN DEFAULT FALSE")
    asegurar_columna_si_no_existe("correo_sucursales_ofrecidas", "TEXT")
    asegurar_columna_si_no_existe("costo_envio", "FLOAT")
    asegurar_columna_si_no_existe("costo_envio_sucursal", "FLOAT")
    asegurar_columna_si_no_existe("costo_envio_domicilio", "FLOAT")
    asegurar_columna_si_no_existe("ia_ultimo_mensaje_hash", "VARCHAR(80)")
    asegurar_columna_si_no_existe("ia_ultimo_analisis", "TIMESTAMP")
    asegurar_columna_si_no_existe("ia_error", "TEXT")
    # IA RECOLECTOR ML / ACORDÁS (FASE 3 - RESPUESTA ASISTIDA)
    asegurar_columna_si_no_existe("ia_respuesta_sugerida", "TEXT")
    asegurar_columna_si_no_existe("ia_sucursales_ofrecidas", "TEXT")
    asegurar_columna_si_no_existe("ia_respuesta_enviada_hash", "VARCHAR(80)")
    asegurar_columna_si_no_existe("ia_ultima_respuesta_enviada", "TIMESTAMP")
    asegurar_columna_si_no_existe("ia_esperando_respuesta", "BOOLEAN DEFAULT FALSE")
    asegurar_columna_si_no_existe("ia_ultimo_mensaje_bot", "TIMESTAMP")
    asegurar_columna_si_no_existe("ia_ultimo_mensaje_cliente", "TIMESTAMP")
    asegurar_columna_si_no_existe("ia_canal_activo", "VARCHAR(30)")
    asegurar_columna_si_no_existe("ia_ultimo_timeout_operador", "TIMESTAMP")

    # =====================
    # APB CANAL MANAGER
    # =====================
    asegurar_columna_si_no_existe("ultimo_mensaje_automatico_texto", "TEXT")
    asegurar_columna_si_no_existe("ultimo_mensaje_automatico_canal", "VARCHAR(30)")
    asegurar_columna_si_no_existe("ultimo_mensaje_automatico_fecha", "TIMESTAMP")

    # =====================
    # APB RECLAMOS ML
    # =====================
    asegurar_columna_si_no_existe("ml_claim_id", "VARCHAR(50)")
    asegurar_columna_si_no_existe("ml_claim_abierto", "BOOLEAN DEFAULT FALSE")
    asegurar_columna_si_no_existe("ml_claim_status", "VARCHAR(50)")
    asegurar_columna_si_no_existe("ml_claim_reason", "VARCHAR(200)")
    asegurar_columna_si_no_existe("ultima_sync_claim_ml", "TIMESTAMP")


def asegurar_columnas_integracion_tn():
    asegurar_columna_si_no_existe("tn_order_id", "VARCHAR(50)")
    asegurar_columna_si_no_existe("tn_order_number", "VARCHAR(50)")
    asegurar_columna_si_no_existe("tn_order_status", "VARCHAR(50)")
    asegurar_columna_si_no_existe("tn_payment_status", "VARCHAR(50)")
    asegurar_columna_si_no_existe("tn_paid_at", "TIMESTAMP")
    asegurar_columna_si_no_existe("tn_cancelled_at", "TIMESTAMP")
    asegurar_columna_si_no_existe("tn_fulfillment_id", "VARCHAR(50)")
    asegurar_columna_si_no_existe("tn_fulfillment_status", "VARCHAR(80)")
    asegurar_columna_si_no_existe("tn_shipping_type", "VARCHAR(80)")
    asegurar_columna_si_no_existe("tn_shipping_carrier", "VARCHAR(100)")
    asegurar_columna_si_no_existe("tn_shipping_option", "VARCHAR(200)")
    asegurar_columna_si_no_existe("tn_tracking_number", "VARCHAR(100)")
    asegurar_columna_si_no_existe("tn_tracking_url", "VARCHAR(300)")
    asegurar_columna_si_no_existe("ultima_sync_tn", "TIMESTAMP")


def productos_desde_excel(archivo_excel):
    df = pd.read_excel(archivo_excel)

    productos = []
    for _, row in df.iterrows():
        sku = "" if pd.isna(row.iloc[0]) else str(row.iloc[0]).strip()
        descripcion = "" if pd.isna(row.iloc[1]) else str(row.iloc[1]).strip()

        if descripcion:
            productos.append({
                "sku": sku,
                "descripcion": descripcion
            })
    return productos


def sincronizar_productos_desde_excel(archivo_excel):
    productos = productos_desde_excel(archivo_excel)

    db.session.query(Producto).delete()
    for prod in productos:
        db.session.add(Producto(sku=prod["sku"], descripcion=prod["descripcion"]))
    db.session.commit()

    return len(productos)


def guardar_etiqueta_subida(archivo):
    if not archivo or not archivo.filename:
        return ""

    try:
        resultado = cloudinary.uploader.upload(
            archivo,
            resource_type="image",
            use_filename=True,
            unique_filename=True,
            overwrite=False
        )
        return {
            "url": resultado.get("secure_url", ""),
            "public_id": resultado.get("public_id", "")
        }
    except Exception as e:
        print("Error subiendo a Cloudinary:", e)
        return {"url": "", "public_id": ""}


def guardar_comprobante_dux_subido(archivo):
    if not archivo or not archivo.filename:
        return {"url": "", "public_id": ""}

    try:
        resultado = cloudinary.uploader.upload(
            archivo,
            resource_type="auto",
            use_filename=True,
            unique_filename=True,
            overwrite=False
        )
        return {
            "url": resultado.get("secure_url", ""),
            "public_id": resultado.get("public_id", "")
        }
    except Exception as e:
        print("Error subiendo comprobante DUX a Cloudinary:", e)
        return {"url": "", "public_id": ""}





def guardar_comprobante_pago_agregado_subido(archivo):
    if not archivo or not archivo.filename:
        return {"url": "", "public_id": ""}

    try:
        resultado = cloudinary.uploader.upload(
            archivo,
            resource_type="auto",
            use_filename=True,
            unique_filename=True,
            overwrite=False
        )
        return {
            "url": resultado.get("secure_url", ""),
            "public_id": resultado.get("public_id", "")
        }
    except Exception as e:
        print("Error subiendo comprobante de pago del agregado a Cloudinary:", e)
        return {"url": "", "public_id": ""}


def _items_agregado_desde_json(raw):
    try:
        data = json.loads(raw or "[]")
    except Exception:
        data = []

    items = []
    for item in data:
        sku = str((item or {}).get("sku") or "").strip().upper()
        descripcion = str((item or {}).get("descripcion") or "").strip()
        cantidad_raw = (item or {}).get("cantidad") or 1
        try:
            cantidad = int(float(str(cantidad_raw).replace(",", ".")))
        except Exception:
            cantidad = 1
        if cantidad < 1:
            cantidad = 1
        if sku:
            if not descripcion:
                producto = Producto.query.filter(Producto.sku.ilike(sku)).first()
                descripcion = producto.descripcion if producto else sku
            items.append({
                "sku": sku,
                "descripcion": descripcion,
                "cantidad": cantidad,
            })
    return items

def asegurar_pdf_local_desde_url(url_pdf, prefijo="etiqueta"):
    if not url_pdf or not url_pdf.startswith("http"):
        return None

    parsed = urlparse(url_pdf)
    extension = os.path.splitext(parsed.path)[1].lower() or ".pdf"
    firma = hashlib.md5(url_pdf.encode("utf-8")).hexdigest()[:12]
    nombre_archivo = secure_filename(f"{prefijo}_{firma}{extension}")
    ruta_pdf = os.path.join(app.config["UPLOAD_FOLDER"], nombre_archivo)

    if os.path.exists(ruta_pdf) and os.path.getsize(ruta_pdf) > 0:
        return nombre_archivo

    try:
        with urlopen(url_pdf) as response, open(ruta_pdf, "wb") as salida:
            salida.write(response.read())
        return nombre_archivo
    except Exception as e:
        print("No se pudo descargar PDF para preview:", e)
        return None


def _recortar_preview_pdf(doc, proveedor="default", margen_px=12, zoom=3):
    page = doc[0]
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)

    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
    mask = np.any(arr < 245, axis=2)

    if not mask.any():
        return page.get_pixmap(matrix=matrix, alpha=False)

    width = pix.width
    height = pix.height
    landscape = width > height

    col_threshold = 0.001
    row_threshold = 0.001

    if proveedor == "correo" and landscape:
        col_threshold = 0.005
        row_threshold = 0.002
    elif proveedor == "mercado" and landscape:
        col_threshold = 0.02
        row_threshold = 0.002

    col_density = mask.mean(axis=0)
    cols = np.where(col_density > col_threshold)[0]
    if cols.size == 0:
        cols = np.where(col_density > 0.001)[0]
    if cols.size == 0:
        cols = np.arange(width)

    row_density = mask[:, cols[0]:cols[-1] + 1].mean(axis=1)
    rows = np.where(row_density > row_threshold)[0]
    if rows.size == 0:
        rows = np.where(mask.mean(axis=1) > 0.001)[0]
    if rows.size == 0:
        rows = np.arange(height)

    min_x = max(0, int(cols[0]) - margen_px)
    max_x = min(width - 1, int(cols[-1]) + margen_px)
    min_y = max(0, int(rows[0]) - margen_px)
    max_y = min(height - 1, int(rows[-1]) + margen_px)

    clip_rect = fitz.Rect(
        min_x / zoom,
        min_y / zoom,
        (max_x + 1) / zoom,
        (max_y + 1) / zoom,
    )
    return page.get_pixmap(matrix=matrix, clip=clip_rect, alpha=False)


def generar_preview_etiqueta_pdf(nombre_archivo, proveedor="default"):
    ruta_pdf = os.path.join(app.config["UPLOAD_FOLDER"], nombre_archivo)

    if not os.path.exists(ruta_pdf):
        return None

    base_nombre = os.path.splitext(nombre_archivo)[0]
    nombre_preview = f"{base_nombre}__preview_recortado_{proveedor}.png"
    ruta_preview = os.path.join(app.config["UPLOAD_FOLDER"], nombre_preview)

    if os.path.exists(ruta_preview):
        try:
            if os.path.getmtime(ruta_preview) >= os.path.getmtime(ruta_pdf):
                return nombre_preview
        except OSError:
            pass

    try:
        doc = fitz.open(ruta_pdf)
    except Exception as e:
        print("No se pudo abrir PDF para preview:", e)
        return None

    try:
        pix_recortado = _recortar_preview_pdf(doc, proveedor=proveedor, margen_px=12, zoom=3)
        pix_recortado.save(ruta_preview)
        return nombre_preview
    except Exception as e:
        print("No se pudo generar preview recortada:", e)
        return None
    finally:
        doc.close()

def hay_autorizado(pedido):
    return bool(
        (pedido.autorizado_nombre and str(pedido.autorizado_nombre).strip()) or
        (pedido.autorizado_dni and str(pedido.autorizado_dni).strip()) or
        (pedido.autorizado_telefono and str(pedido.autorizado_telefono).strip())
    )


def hay_reclamo_generado(pedido):
    return bool(
        (pedido.numero_reclamo and str(pedido.numero_reclamo).strip()) or
        (pedido.observacion_reclamo and str(pedido.observacion_reclamo).strip()) or
        (pedido.motivo_no_entregado and str(pedido.motivo_no_entregado).strip())
    )


def normalizar_telefono(raw):
    return normalizar_telefono_service(raw)

def buscar_pedido_activo_por_telefono(telefono):
    return buscar_pedido_activo_por_telefono_service(
        telefono,
        Pedido,
    )

def obtener_estado_conversacional(
    pedido,
    crear_si_no_existe=True,
):
    return obtener_estado_conversacional_service(
        pedido,
        EstadoConversacionalPedido,
        db,
        crear_si_no_existe=crear_si_no_existe,
    )


def actualizar_estado_conversacional(
    pedido,
    owner_actual=None,
    estado_conversacional=None,
    canal_activo=None,
    flujo_base=None,
    takeover_activo=None,
    bot_pausado=None,
    cross_sell_activo=None,
    ultimo_mensaje_cliente=None,
    ultimo_mensaje_bot=None,
):
    return actualizar_estado_conversacional_service(
        pedido,
        EstadoConversacionalPedido,
        db,
        owner_actual=owner_actual,
        estado_conversacional=estado_conversacional,
        canal_activo=canal_activo,
        flujo_base=flujo_base,
        takeover_activo=takeover_activo,
        bot_pausado=bot_pausado,
        cross_sell_activo=cross_sell_activo,
        ultimo_mensaje_cliente=ultimo_mensaje_cliente,
        ultimo_mensaje_bot=ultimo_mensaje_bot,
    )

def registrar_evento_operativo(
    pedido=None,
    tipo_evento="",
    origen="sistema",
    canal="sistema",
    owner="sistema",
    estado_conversacional="",
    flujo_base="",
    payload=None,
    resultado="",
    detalle="",
    usuario="",
    procesado=False,
):
    return registrar_evento_operativo_service(
        EventoOperativo,
        db,
        pedido=pedido,
        tipo_evento=tipo_evento,
        origen=origen,
        canal=canal,
        owner=owner,
        estado_conversacional=estado_conversacional,
        flujo_base=flujo_base,
        payload=payload,
        resultado=resultado,
        detalle=detalle,
        usuario=usuario,
        procesado=procesado,
    )

def wa_ventana_24h_abierta(
    pedido=None,
    telefono="",
):
    return wa_ventana_24h_abierta_service(
        WhatsAppMensaje,
        pedido=pedido,
        telefono=telefono,
    )

def registrar_whatsapp_mensaje(
    pedido=None,
    telefono="",
    direccion="",
    autor="",
    texto="",
    message_id_meta="",
    estado="",
    error="",
):
    return registrar_whatsapp_mensaje_service(
        WhatsAppMensaje,
        actualizar_estado_conversacional,
        registrar_evento_operativo,
        Pedido,
        db,
        pedido=pedido,
        telefono=telefono,
        direccion=direccion,
        autor=autor,
        texto=texto,
        message_id_meta=message_id_meta,
        estado=estado,
        error=error,
    )



# =========================
# VIA CARGO - SUCURSALES CERCANAS
# =========================

# Coordenadas centroide de barrios CABA (fallback si no hay CP ni dirección)
_BARRIOS_CABA_COORDS = {
    "agronomia": (-34.5958, -58.4950), "almagro": (-34.6097, -58.4196),
    "balvanera": (-34.6126, -58.4023), "barracas": (-34.6476, -58.3889),
    "barrio norte": (-34.5876, -58.3930), "belgrano": (-34.5623, -58.4581),
    "boca": (-34.6361, -58.3632), "la boca": (-34.6361, -58.3632),
    "boedo": (-34.6289, -58.4109), "caballito": (-34.6155, -58.4399),
    "chacarita": (-34.5861, -58.4588), "coghlan": (-34.5666, -58.4781),
    "colegiales": (-34.5736, -58.4476), "constitucion": (-34.6269, -58.3838),
    "flores": (-34.6302, -58.4681), "floresta": (-34.6219, -58.4952),
    "la paternal": (-34.5956, -58.4804), "paternal": (-34.5956, -58.4804),
    "liniers": (-34.6413, -58.5261), "mataderos": (-34.6618, -58.5103),
    "microcentro": (-34.6063, -58.3745), "monserrat": (-34.6156, -58.3798),
    "monte castro": (-34.6136, -58.5094), "nueva pompeya": (-34.6567, -58.4085),
    "nuñez": (-34.5476, -58.4614), "once": (-34.6126, -58.4023),
    "palermo": (-34.5885, -58.4328), "parque avellaneda": (-34.6526, -58.4750),
    "parque chacabuco": (-34.6422, -58.4410), "parque patricios": (-34.6425, -58.3991),
    "puerto madero": (-34.6158, -58.3637), "puente saavedra": (-34.5476, -58.4883),
    "recoleta": (-34.5876, -58.3930), "retiro": (-34.5909, -58.3749),
    "saavedra": (-34.5538, -58.4883), "san cristobal": (-34.6236, -58.3978),
    "san nicolas": (-34.6033, -58.3801), "san telmo": (-34.6233, -58.3722),
    "tribunales": (-34.6013, -58.3876), "velez sarsfield": (-34.6393, -58.5168),
    "versalles": (-34.6334, -58.5250), "villa crespo": (-34.5969, -58.4480),
    "villa del parque": (-34.5996, -58.4944), "villa devoto": (-34.6050, -58.5099),
    "villa lugano": (-34.6844, -58.4752), "villa luro": (-34.6324, -58.5068),
    "villa ortuzar": (-34.5796, -58.4680), "villa pueyrredon": (-34.5853, -58.5036),
    "villa real": (-34.6246, -58.5250), "villa riachuelo": (-34.6879, -58.4601),
    "villa soldati": (-34.6796, -58.4524), "villa urquiza": (-34.5796, -58.4912),
}

_CABA_CENTROIDE = (-34.6037, -58.3816)


def _distancia_km(lat1, lng1, lat2, lng2):
    import math
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _obtener_coords_cliente(codigo_postal, direccion, localidad, provincia):
    """
    Obtiene lat/lng del cliente para ordenar sucursales por distancia.
    Estrategia en orden de prioridad:
      1. Nominatim con dirección completa + localidad (más preciso)
      2. Nominatim con solo localidad/barrio
      3. Diccionario interno de barrios CABA
      4. CP del cliente -> sucursal con CP más cercano como referencia (fallback sin internet)
      5. Centroide de CABA como último recurso
    Devuelve (lat, lng, metodo)
    """
    import urllib.request
    import urllib.parse
    import json as _json

    es_caba = any(x in (provincia or "").lower()
                  for x in ["capital federal", "caba", "ciudad autonoma", "ciudad autónoma"])

    sufijo_caba = "Ciudad Autónoma de Buenos Aires, Argentina"
    sufijo_gen = f"{localidad or ''}, Argentina"

    headers = {"User-Agent": "fierro-sistema/1.0"}

    def nominatim(q):
        try:
            params = urllib.parse.urlencode({"q": q, "format": "json", "limit": 1, "countrycodes": "ar"})
            url = f"https://nominatim.openstreetmap.org/search?{params}"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3) as r:
                res = _json.loads(r.read())
                if res:
                    return float(res[0]["lat"]), float(res[0]["lon"])
        except Exception as e:
            print(f"[NOMINATIM] Error '{q}':", e)
        return None

    # 1) Nominatim con dirección completa — más preciso que CP
    if direccion and localidad:
        coords = nominatim(f"{direccion}, {sufijo_caba if es_caba else sufijo_gen}")
        if coords:
            return coords[0], coords[1], "nominatim_direccion"

    # 2) Nominatim con solo localidad/barrio
    if localidad:
        coords = nominatim(f"{localidad}, {sufijo_caba if es_caba else 'Argentina'}")
        if coords:
            return coords[0], coords[1], "nominatim_localidad"

    # 3) Diccionario de barrios CABA
    if es_caba and localidad:
        loc_norm = (localidad or "").lower().strip()
        for barrio, coords in _BARRIOS_CABA_COORDS.items():
            if barrio in loc_norm or loc_norm in barrio:
                return coords[0], coords[1], "diccionario_barrio"

    # 4) CP como fallback cuando no hay internet o Nominatim falla
    cp_str = str(codigo_postal or "").strip()
    if cp_str and cp_str.isdigit():
        cp_int = int(cp_str)
        try:
            with open("via_cargo_sucursales.json", "r", encoding="utf-8") as f:
                data_suc = _json.load(f)
            pool = [s for s in data_suc if s.get("cp") and s.get("lat") and s.get("lng")]
            if es_caba:
                pool_caba = [s for s in pool if "capital federal" in (s.get("provincia") or "").lower()]
                pool = pool_caba or pool
            if pool:
                ref = min(pool, key=lambda s: abs(int(s["cp"]) - cp_int))
                return float(ref["lat"]), float(ref["lng"]), "cp_fallback"
        except Exception as e:
            print("[VIA CARGO] Error buscando CP de referencia:", e)

    # 5) Centroide CABA
    if es_caba:
        return _CABA_CENTROIDE[0], _CABA_CENTROIDE[1], "centroide_caba"

    return None, None, "sin_coords"


def sugerir_sucursales(pedido):
    """
    Devuelve un mensaje con las 3 sucursales Via Cargo más cercanas al cliente,
    ordenadas por distancia usando CP, Nominatim o barrio como referencia.
    Devuelve None si ya eligió sucursal, si no hay datos de ubicación, o si no hay sucursales.
    """
    if getattr(pedido, "sucursal_nombre", None):
        return None

    import unicodedata as _ud, re as _re
    def _norm(s):
        """Normaliza: minúsculas, sin tildes, sin contenido entre paréntesis."""
        s = (s or "").lower().strip()
        s = _ud.normalize("NFD", s)
        s = "".join(c for c in s if _ud.category(c) != "Mn")
        s = _re.sub(r"\s*\(.*?\)", "", s).strip()
        return s
    loc = _norm(pedido.localidad)
    prov = _norm(pedido.provincia)
    direccion = (pedido.direccion or "").strip()
    cp = str(pedido.codigo_postal or "").strip()

    es_caba = loc in ["caba", "capital federal", "ciudad autonoma de buenos aires",
                      "ciudad autonoma de buenos aires"] or \
              any(x in prov for x in ["capital federal", "caba", "ciudad autonoma"])

    # APB: exigir CP válido antes de ofrecer sucursales
    # Sin CP el ordenamiento por distancia no es confiable
    if not cp or not cp.isdigit() or len(cp) < 4:
        return None

    try:
        with open("via_cargo_sucursales.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print("[VIA CARGO] No se pudo leer via_cargo_sucursales.json:", e)
        return None

    # Filtrar candidatas por zona
    if es_caba:
        candidatas = [s for s in data if "capital federal" in (s.get("provincia") or "").lower()]
    else:
        # 1) CP exacto
        candidatas = [s for s in data if cp and str(s.get("cp", "")) == cp]
        # 2) Localidad + provincia normalizadas (sin tildes, sin paréntesis)
        if not candidatas:
            candidatas = [
                s for s in data
                if loc and loc in _norm(s.get("localidad"))
                and prov in _norm(s.get("provincia"))
            ]
        # 3) Solo provincia normalizada
        if not candidatas and prov:
            candidatas = [s for s in data if prov in _norm(s.get("provincia"))]

    if not candidatas:
        return None

    # Ordenar por distancia
    candidatas_con_coords = [s for s in candidatas if s.get("lat") and s.get("lng")]
    if candidatas_con_coords:
        lat_cli, lng_cli, metodo = _obtener_coords_cliente(cp, direccion, pedido.localidad, pedido.provincia)
        print(f"[VIA CARGO] Ubicación cliente: método={metodo} lat={lat_cli} lng={lng_cli} cp={cp}")
        if lat_cli and lng_cli:
            candidatas_con_coords.sort(
                key=lambda s: _distancia_km(lat_cli, lng_cli, float(s["lat"]), float(s["lng"]))
            )
            candidatas = candidatas_con_coords

    sucs = candidatas[:3]

    # Guardar IDs de las candidatas ofrecidas para detectar la elección por número después
    try:
        from app import db
        ids_ofrecidas = [s.get("id") for s in sucs if s.get("id")]
        pedido.ia_sucursales_ofrecidas = json.dumps(ids_ofrecidas)
        db.session.commit()
    except Exception as e:
        print("[VIA CARGO] Error guardando sucursales ofrecidas:", e)

    lista = ""
    for i, s in enumerate(sucs, 1):
        nombre = s.get("nombre") or "Sucursal"
        dir_suc = s.get("direccion") or ""
        lista += f"{i}) {nombre}\n{dir_suc}\n\n"

    return (
        "Genial 👍\n\n"
        "Te paso sucursales cercanas para que elijas:\n\n"
        f"{lista}"
        "Decime cuál preferís y despachamos 🚀"
    )


def _es_consulta_no_eleccion(texto):
    """
    Detecta si el mensaje del cliente es una pregunta o consulta,
    no una elección concreta de sucursal.
    En ese caso NO se debe detectar sucursal — escalar al operador.
    """
    texto = texto.lower().strip()
    patrones_consulta = [
        r'\?',                          # tiene signo de pregunta
        r'no lo tienen',                 # preguntando si existe
        r'ese no',                       # dudando
        r'tienen ese',
        r'queda cerca',
        r'está cerca',
        r'esta cerca',
        r'me queda',
        r'hay alguna',
        r'tienen alguna',
        r'podría ser',
        r'podria ser',
        r'o ese',
        r'sino',                         # "sino ese otro"
        r'si no',
        r'en cambio',
        r'por ejemplo',
        r'pero.*\?',
        r'\bno\b.*\bsé\b',
        r'\bno\b.*\bse\b',
        r'me parece',
        r'creo que',
    ]
    return any(re.search(p, texto) for p in patrones_consulta)


def _texto_parece_eleccion_sucursal(texto):
    """Determina si un texto realmente intenta elegir una sucursal ofrecida.

    Evita que un mensaje largo con datos de domicilio/localidad se confunda con
    una opción de sucursal solo porque contiene una palabra parecida.
    """
    t = str(texto or "").lower().strip()
    if not t:
        return False
    if re.search(r"\b([1-3])\b", t):
        return True
    if any(x in t for x in [
        "elijo", "elegí", "elegi", "elegimos", "prefiero", "quiero la",
        "quiero esa", "me quedo", "opcion", "opción", "numero", "número",
        "la 1", "la 2", "la 3", "primera", "segunda", "tercera", "la de"
    ]):
        return True
    # Mensaje corto tipo "San Martín" puede ser elección. Mensaje largo con
    # DNI/dirección/CP/contacto NO debe matchear sucursal.
    palabras_datos = ["dni", "documento", "direccion", "dirección", "cp", "codigo", "código", "telefono", "teléfono", "contacto", "envio", "envío", "calle", "altura"]
    if len(t) <= 45 and not any(x in t for x in palabras_datos):
        return True
    return False


def detectar_sucursal(pedido, mensaje):
    """
    Detecta la sucursal elegida por el cliente en su respuesta.

    REGLAS DE SEGURIDAD:
    - Si el mensaje parece una consulta o pregunta → devuelve None (escalar al operador)
    - Solo matchea sucursales dentro de las candidatas ofrecidas si las hay
    - Valida que la provincia de la sucursal coincida con la del cliente
    - Nunca asume una elección de un texto ambiguo

    Estrategias en orden de prioridad:
      1. Si eligió por número (1, 2, 3) y el pedido tiene candidatas guardadas → usar índice
      2. Match flexible por palabras clave del nombre (solo dentro de candidatas ofrecidas)
      3. Match por dirección (solo dentro de candidatas ofrecidas)
    """
    try:
        with open("via_cargo_sucursales.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print("[VIA CARGO] No se pudo leer via_cargo_sucursales.json:", e)
        return None

    texto = (mensaje or "").lower().strip()
    if not texto:
        return None

    # REGLA 1: Si es consulta/pregunta → no detectar, escalar al operador
    if _es_consulta_no_eleccion(texto):
        print(f"[VIA CARGO] Mensaje detectado como consulta, no elección: '{texto[:80]}'")
        return None

    # Obtener candidatas ofrecidas (las que le mostramos al cliente)
    candidatas_ids = []
    try:
        candidatas_ids = json.loads(getattr(pedido, "ia_sucursales_ofrecidas", "") or "[]")
    except Exception:
        pass

    # Si hay candidatas ofrecidas, solo detectar sucursal cuando el cliente
    # realmente esté eligiendo una opción. No asignar por haber mencionado una
    # localidad/dirección dentro de los datos del envío.
    if candidatas_ids and not _texto_parece_eleccion_sucursal(texto):
        print(f"[VIA CARGO] No se asigna sucursal: texto no parece elección explícita: '{texto[:100]}'")
        return None

    # Pool de búsqueda: SOLO las candidatas ofrecidas si las tenemos
    # Esto evita matchear sucursales de otras provincias/localidades
    if candidatas_ids:
        pool = [s for s in data if s.get("id") in candidatas_ids]
    else:
        # Si no hay candidatas guardadas, filtrar por CP + localidad + provincia del cliente
        cp_cliente = str(getattr(pedido, "codigo_postal", "") or "").strip()
        loc_cliente = (getattr(pedido, "localidad", "") or "").lower().strip()
        prov_cliente = (getattr(pedido, "provincia", "") or "").lower().strip()

        pool = []
        for s in data:
            # Validar provincia obligatoriamente
            prov_suc = (s.get("provincia") or "").lower()
            if prov_cliente and prov_cliente not in prov_suc:
                continue
            # Validar localidad si la tenemos
            loc_suc = (s.get("localidad") or "").lower()
            if loc_cliente and loc_cliente not in loc_suc and loc_suc not in loc_cliente:
                continue
            # Validar CP si lo tenemos: el CP de la sucursal debe estar en el mismo rango
            # Para CABA (CP 1000-1499): rango de ±100
            # Para el interior: rango de ±50
            cp_suc = str(s.get("cp") or "").strip()
            if cp_cliente and cp_cliente.isdigit() and cp_suc and cp_suc.isdigit():
                cp_int = int(cp_cliente)
                cp_suc_int = int(cp_suc)
                rango = 100 if cp_int < 1500 else 50
                if abs(cp_int - cp_suc_int) > rango:
                    continue
            pool.append(s)

        # Si el filtro quedó vacío (caso edge) no matchear nada
        if not pool:
            return None

    if not pool:
        return None

    # ESTRATEGIA 1: Eligió por número
    if candidatas_ids:
        patrones_num = [
            (r'(?<!\d)1(?!\d)|primero|primera', 0),
            (r'(?<!\d)2(?!\d)|segundo|segunda', 1),
            (r'(?<!\d)3(?!\d)|tercero|tercera', 2),
        ]
        for patron, idx in patrones_num:
            if re.search(patron, texto) and idx < len(candidatas_ids):
                suc_id = candidatas_ids[idx]
                encontrada = next((s for s in pool if s.get("id") == suc_id), None)
                if encontrada:
                    return encontrada

    # ESTRATEGIA 2: Match por palabras clave del nombre (solo en pool)
    for s in pool:
        nombre = (s.get("nombre") or "").lower()
        if not nombre:
            continue
        palabras = [p for p in re.split(r'\W+', nombre) if len(p) > 3 and p not in ("agencia", "encomiendas", "logistica")]
        if palabras and all(p in texto for p in palabras):
            return s

    # ESTRATEGIA 3: Match por dirección (solo en pool)
    for s in pool:
        direccion = re.sub(r'nro\.?\s*', '', (s.get("direccion") or "").lower()).strip()
        if direccion and len(direccion) > 5 and direccion in texto:
            return s

    return None



def requiere_seguimiento_retiro(pedido):
    """
    APB:
    El flujo "Listo para retirar" depende del tipo de entrega,
    NO del canal ni de la empresa de envío.
    """

    entrega_es_sucursal = bool(
        pedido.tipo_entrega == "Sucursal"
        or str(pedido.sucursal_nombre or "").strip()
    )

    return bool(
        pedido.estado in [
            Estado.DESPACHADO,
            Estado.VERIFICAR_DESTINO,
            "Con demora de entrega",
            "Con reclamo en transporte",
        ]
        and entrega_es_sucursal
    )



def pedido_tiene_parrilla(pedido):
    for item in (pedido.items or []):
        texto = f"{item.sku or ''} {item.descripcion or ''}".lower()
        if "parrilla" in texto:
            return True
    return False


def mensaje_whatsapp_despachado(pedido):
    tracking_info = tracking_info_pedido(pedido)
    seguimiento = (
        getattr(pedido, "seguimiento", None)
        or getattr(pedido, "tn_tracking_number", None)
        or (tracking_info or {}).get("seguimiento")
        or "no disponible"
    )
    link_tracking = (tracking_info or {}).get("url") or ""
    partes = [
        "Hola!",
        "",
        "Tu pedido ya fue despachado.",
        "",
        f"Seguimiento: {seguimiento}",
    ]
    if link_tracking:
        partes += ["Podés seguirlo acá:", link_tracking]
    partes += ["", "Cualquier duda estoy por acá."]
    return "\n".join(partes)


def mensaje_whatsapp_confirmar_entrega(pedido):
    sucursal = (pedido.sucursal_nombre or "a confirmar").strip()
    direccion_partes = [
        (pedido.direccion or "").strip(),
        (pedido.localidad or "").strip(),
        (pedido.provincia or "").strip(),
    ]
    direccion_sucursal = ", ".join([parte for parte in direccion_partes if parte]) or "a confirmar"
    seguimiento = (pedido.seguimiento or pedido.tn_tracking_number or "no disponible").strip()
    return (
        f"Hola {pedido.cliente or ''}, te escribimos de Fierro por tu pedido #{pedido.id}.\n\n"
        "Tu compra ya está disponible para retirar en sucursal.\n\n"
        f"Sucursal: {sucursal}\n"
        f"Dirección sucursal: {direccion_sucursal}\n"
        f"Seguimiento: {seguimiento}\n\n"
        "Tenés 5 días para retirarlo antes de que vuelva a origen.\n\n"
        "Cuando lo retires, por favor avisame así cerramos la entrega."
    )


def mensaje_whatsapp_postventa(pedido):
    if pedido_tiene_parrilla(pedido):
        return (
            "Buenas!\n\n"
            "Vimos que ya recibiste tu parrilla.\n"
            "Esperamos haber cumplido con tus expectativas, ¡gracias por confiar en nosotros!\n\n"
            "Te dejamos algunos tips para que te dure muchos años:\n\n"
            "• Evitá “quemarla” a fuego directo, ese calor puede doblar las varillas.\n"
            "• Limpiala con un cepillo mientras está caliente, justo después de usarla.\n"
            "• Usá la grasa del asado para pasarle y “curarla”; ayuda a evitar el óxido.\n"
            "• Si queda al aire libre, podés pasarle aceite comestible con una esponja.\n\n"
            "Si tenés alguna duda con el uso, escribinos.\n\n"
            "Gracias nuevamente.\n"
            "Y si querés, seguinos en Instagram para ver lo nuevo que vamos sumando:\n"
            "https://www.instagram.com/fierroargento"
        )
    return (
        "Buenas!\n\n"
        "Vimos que ya recibiste tu compra.\n"
        "Esperamos haber cumplido con tus expectativas, ¡gracias por confiar en nosotros!\n\n"
        "Si tenés alguna duda con el producto, escribinos y te ayudamos.\n\n"
        "Gracias nuevamente.\n"
        "Y si querés, seguinos en Instagram para ver lo nuevo que vamos sumando:\n"
        "https://www.instagram.com/fierroargento"
    )


def es_mercado_envios(pedido):
    return pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Mercado Envíos"


def es_tnube(pedido):
    return pedido.canal == "Tienda Nube"


def es_tnube_via_cargo(pedido):
    return es_tnube(pedido) and es_via_cargo(pedido.empresa_envio)


def es_mayorista(pedido):
    return pedido.canal == "Mayorista"


def es_mayorista_via_cargo(pedido):
    return es_mayorista(pedido) and es_via_cargo(pedido.empresa_envio)


def usa_flujo_etiqueta_directa(pedido):
    return es_mercado_envios(pedido) or (es_tnube(pedido) and pedido.empresa_envio in ["Andreani", "Correo Argentino"])


def es_ml_acordas_entrega(pedido):
    return pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Acordás la Entrega"


def es_ml_acordas_via_cargo(pedido):
    return bool(
        pedido
        and pedido.canal == "Mercado Libre"
        and pedido.ml_tipo == "Acordás la Entrega"
        and es_via_cargo(pedido.empresa_envio)
    )


def aplicar_default_tipo_entrega(pedido):
    """
    Regla APB preventiva:
    Mercado Libre + Acordás la Entrega
    con transportista externo nace como Sucursal,
    salvo que carga/admin ya haya definido
    otro tipo de entrega.

    Aplica a:
    - Vía Cargo
    - Andreani
    - Correo Argentino
    """

    if not pedido:
        return

    if not es_ml_acordas_entrega(pedido):
        return

    if (pedido.tipo_entrega or "").strip():
        return

    empresa = str(
        getattr(pedido, "empresa_envio", "") or ""
    ).strip().lower()

    transportistas_externos = [
        "via cargo",
        "vía cargo",
        "andreani",
        "correo argentino",
        "correo",
    ]

    if any(t in empresa for t in transportistas_externos):
        pedido.tipo_entrega = "Sucursal"


def usa_flujo_acordas_entrega(pedido):
    return es_ml_acordas_entrega(pedido) or es_tnube_via_cargo(pedido) or es_mayorista_via_cargo(pedido)


def puede_imprimir_etiqueta_directamente(pedido):
    return bool(
        usa_flujo_etiqueta_directa(pedido)
        and pedido.etiqueta_archivo
        and len(pedido.items) > 0
    )


def despacho_completo_old(pedido):
    aplicar_default_tipo_entrega(pedido)

    if not pedido.empresa_envio or not pedido.tipo_entrega:
        return False

    if pedido.tipo_entrega == "Domicilio":
        return bool(
            pedido.direccion
            and pedido.codigo_postal
            and pedido.localidad
            and pedido.provincia
        )

    if pedido.tipo_entrega == "Sucursal":
        if not (pedido.sucursal_nombre and pedido.direccion and pedido.localidad and pedido.provincia):
            return False

        if hay_autorizado(pedido):
            return bool(
                pedido.autorizado_nombre
                and pedido.autorizado_dni
                and pedido.autorizado_telefono
            )
        return True

    return False


def puede_imprimir_acordas_entrega(pedido):
    return bool(
        usa_flujo_acordas_entrega(pedido)
        and len(pedido.items) > 0
        and despacho_completo(pedido)
        and (
            es_via_cargo(pedido.empresa_envio)
            or bool(pedido.etiqueta_archivo)
        )
    )


def requiere_contacto_cliente_old(pedido):
    return bool(
        usa_flujo_acordas_entrega(pedido)
        and not despacho_completo(pedido)
    )


def debe_pasar_a_demora_entrega(pedido):
    if not pedido:
        return False

    if pedido.estado != "Despachado":
        return False

    if hay_reclamo_generado(pedido):
        return False

    if not pedido.fecha_despachado:
        return False

    horas = max(0, (datetime.utcnow() - pedido.fecha_despachado).total_seconds() / 3600)
    return horas >= 7 * 24


def actualizar_estado_automatico(pedido):
    actualizar_estado_automatico_service(
        pedido,
        puede_imprimir_etiqueta_directamente,
        puede_imprimir_acordas_entrega,
        debe_pasar_a_demora_entrega,
    )


def aplicar_autoavance_post_despacho(pedido):
    aplicar_autoavance_post_despacho_service(pedido)


def aplicar_estado_y_fechas(pedido, nuevo_estado):
    if not nuevo_estado:
        return

    pedido.estado = nuevo_estado
    ahora = datetime.utcnow()

    if nuevo_estado == Estado.ETIQUETA_IMPRESA:
        if not pedido.fecha_etiqueta_impresa:
            pedido.fecha_etiqueta_impresa = ahora
    elif nuevo_estado == Estado.EMBALADO:
        pedido.fecha_embalado = ahora
    elif nuevo_estado == Estado.DESPACHADO:
        pedido.fecha_despachado = ahora
        aplicar_autoavance_post_despacho(pedido)

        # APB:
        # Al despachar un pedido con seguimiento,
        # iniciamos automáticamente el flujo WhatsApp
        # de despacho/seguimiento.
        if (
            pedido.telefono
            and not es_via_cargo(pedido.empresa_envio)
            and (
                pedido.seguimiento
                or pedido.tn_tracking_number
            )
            and pedido.wa_estado != "despachado"
        ):
            try:
                from modules.whatsapp.flows import wa_enviar_numero_seguimiento

                wa_enviar_numero_seguimiento(pedido)

            except Exception as e:
                print(f"[WA-DESPACHO] Error iniciando flujo WA despacho: {e}")
    elif nuevo_estado == Estado.ENTREGADO:
        pedido.fecha_entregado = ahora

        if pedido.canal == "Tienda Nube" or usa_flujo_etiqueta_directa(pedido) or es_tnube_via_cargo(pedido) or es_mayorista_via_cargo(pedido):
            pedido.estado = Estado.FINALIZADO


def motor_bloqueo(pedido):
    errores = []

    if tn_pedido_bloqueado_cancelado(pedido):
        errores.append("NO DESPACHAR - Pedido cancelado en Tienda Nube.")

    errores.extend(validar_datos_basicos(pedido))

    error_via_pp6040 = validar_regla_via_cargo_pp6040(pedido)
    if error_via_pp6040:
        errores.append(error_via_pp6040)

    errores.extend(validar_datos_ml(pedido, parece_nickname_ml))

    errores.extend(validar_datos_entrega(pedido))

    errores.extend(validar_transporte_obligatorio(pedido, usa_flujo_etiqueta_directa))

    errores.extend(validar_transportes(pedido, es_tnube))

    return errores

def texto_boton_estado(pedido):
    if pedido.estado == "Cargando Pedido":
        if requiere_contacto_cliente(pedido):
            return "Contactar cliente"
        if puede_imprimir_etiqueta_directamente(pedido):
            return "Imprimir etiqueta"
        if es_via_cargo(pedido.empresa_envio):
            return "Preparar pedido"
        return "Generar etiqueta"

    if pedido.estado == Estado.ETIQUETA_LISTA:
        return "Imprimir etiqueta"

    if pedido.estado == Estado.ETIQUETA_IMPRESA:
        return "Marcar embalado"

    if pedido.estado == Estado.EMBALADO:
        return "Marcar despachado"

    if pedido.estado in ESTADOS_POST_DESPACHO[:3]:
        if es_via_cargo(pedido.empresa_envio) and not pedido.seguimiento:
            return "Cargar seguimiento"
        return "Marcar entregado"

    if pedido.estado == Estado.VERIFICAR_DESTINO:
        if pedido.tipo_entrega == "Sucursal":
            return "Marcar listo para retirar"
        return "Marcar entregado"

    if pedido.estado == Estado.LISTO_RETIRAR:
        return "Marcar entregado"

    if pedido.estado == "No entregado":
        return "Gestionar devolución"

    if pedido.estado == "Reclamar a Mercado Libre":
        return "Gestionar reclamo Meli"

    if pedido.estado == "Entregado":
        
        if pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Acordás la Entrega":
            return "Ya avisé Mercado Libre"
        return "Sin acción"

    return "Avanzar estado"


def texto_feedback_estado(estado):
    mensajes = {
        "Etiqueta Impresa": "Etiqueta impresa correctamente.",
        "Embalado": "Pedido embalado correctamente.",
        "Despachado": "Pedido despachado correctamente.",
        Estado.VERIFICAR_DESTINO: "Pedido despachado correctamente.",
        Estado.LISTO_RETIRAR: "Cliente avisado correctamente.",
        "Entregado": "Pedido entregado correctamente.",
        "Finalizado": "Pedido finalizado correctamente.",
        "No entregado": "Pedido marcado como no entregado.",
        "Con reclamo en transporte": "Reclamo cargado correctamente.",
    }
    return mensajes.get(estado, "Acción realizada correctamente.")


def accion_sugerida_pedido(pedido):
    # APB: si Mercado Libre tiene reclamo activo, esta es siempre la prioridad visual/operativa.
    if pedido.canal == "Mercado Libre" and getattr(pedido, "ml_claim_abierto", False):
        return "⚠️ Atender reclamo ML"

    if tn_pedido_bloqueado_cancelado(pedido):
        return "⚠️ NO DESPACHAR - Cancelado TN"

    if (
        getattr(pedido, "agregado_pendiente_revision", False)
        and pedido.estado in ESTADOS_DESPACHO_OPERATIVO
    ):
        return "⚠️ Revisar agregado pendiente"

    if pedido.estado == "Cargando Pedido":
        if not pedido.cliente:
            return "Falta cargar cliente"

        if not pedido.canal:
            return "Falta elegir canal"

        if pedido.canal == "Mercado Libre" and not pedido.ml_tipo:
            return "Falta elegir tipo ML"

        if pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Mercado Envíos" and not pedido.etiqueta_archivo:
            return "Falta adjuntar etiqueta"

        if pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Acordás la Entrega" and not pedido.empresa_envio:
            if not getattr(pedido, "contacto_iniciado", False):
                return "Contactar cliente"
            return "Falta elegir transporte"

        if pedido.canal == "Tienda Nube" and not pedido.empresa_envio:
            return "Falta elegir transporte"

        if pedido.canal == "Tienda Nube" and pedido.empresa_envio in ["Andreani", "Correo Argentino"] and (not pedido.etiqueta_archivo or not pedido.seguimiento):
            return "Completar carga"

        if pedido.empresa_envio and not pedido.tipo_entrega:
            return "Falta elegir tipo de entrega"

        if pedido.empresa_envio and pedido.tipo_entrega == "Domicilio":
            if not pedido.direccion or not pedido.localidad or not pedido.provincia or not pedido.codigo_postal:
                return "Faltan datos de domicilio"

        if pedido.empresa_envio and pedido.tipo_entrega == "Sucursal":
            if not pedido.sucursal_nombre or not pedido.direccion or not pedido.localidad or not pedido.provincia:
                return "Faltan datos de sucursal"

            if hay_autorizado(pedido):
                if not pedido.autorizado_nombre or not pedido.autorizado_dni or not pedido.autorizado_telefono:
                    return "Faltan datos del autorizado"

        if not pedido.items:
            return "Falta cargar productos"

        if requiere_contacto_cliente(pedido):
            return "Contactar cliente por WhatsApp"

        if puede_imprimir_etiqueta_directamente(pedido):
            return "Imprimir etiqueta"

        if es_via_cargo(pedido.empresa_envio):
            return "Pedido listo para imprimir etiqueta"

        return "Pedido listo para generar etiqueta"

    if pedido.estado == Estado.ETIQUETA_LISTA:
        return "Imprimir etiqueta"

    if pedido.estado == Estado.ETIQUETA_IMPRESA:
        return "Embalar pedido"

    if pedido.estado == Estado.EMBALADO:
        return "Despachar pedido"

    if pedido.estado == Estado.DEMORA:
        return "Iniciar reclamo"

    if pedido.estado in ["Despachado", "Con reclamo en transporte"]:
        if es_via_cargo(pedido.empresa_envio) and not pedido.seguimiento:
            return "Cargar seguimiento"
        return "Confirmar entrega"

    if pedido.estado == "Verificar llegada a destino":
        return "Hacer seguimiento"

    if pedido.estado == Estado.LISTO_RETIRAR:
        return "Confirmar entrega"

    if pedido.estado == "No entregado":
        return "Gestionar devolución"

    if pedido.estado == "Reclamar a Mercado Libre":
        return "Gestionar reclamo Meli"

    if pedido.estado == "Entregado":
        if pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Acordás la Entrega":
            return "Avisar a Mercado Libre"
        return "Pedido terminado"

    return ""


def primer_paso_pendiente_carga(pedido):
    if not pedido:
        return 1

    # Paso 1: Cliente
    if not pedido.cliente:
        return 1

    # En ML Acordás suele faltar info operativa del cliente.
    # Lo mandamos primero a Cliente para completar DNI / teléfono antes de coordinar envío.
    if pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Acordás la Entrega":
        if not pedido.dni or not pedido.telefono:
            return 1

    # Paso 2: Venta
    if not pedido.canal:
        return 2

    if pedido.canal == "Mercado Libre":
        if not pedido.id_venta or not pedido.ml_tipo:
            return 2

    # Paso 3: Envío / datos logísticos / etiqueta.
    # APB: si falta transporte, tipo de entrega, datos de entrega o etiqueta,
    # Completar carga debe caer directo en el módulo de envío, no en Cliente.
    if requiere_contacto_cliente(pedido):
        return 3

    if not pedido.empresa_envio:
        return 3

    if pedido.empresa_envio and not pedido.tipo_entrega:
        return 3

    if pedido.tipo_entrega == "Domicilio":
        if not pedido.direccion or not pedido.localidad or not pedido.provincia or not pedido.codigo_postal:
            return 3

    if pedido.tipo_entrega == "Sucursal":
        if not pedido.sucursal_nombre or not pedido.direccion or not pedido.localidad or not pedido.provincia:
            return 3
        if hay_autorizado(pedido) and (not pedido.autorizado_nombre or not pedido.autorizado_dni or not pedido.autorizado_telefono):
            return 3

    if pedido.empresa_envio in ["Andreani", "Correo Argentino"] and not pedido.etiqueta_archivo:
        return 3

    # Paso 4: Productos
    if not pedido.items or len(pedido.items) == 0:
        return 4

    return 1


def accion_principal_pedido(pedido, origen="inicio"):
    rol = rol_actual()
    es_inicio = origen == "inicio"

    clase_base = "btn btn-accion-rapida"
    clase_confirmar = "btn btn-accion-rapida btn-confirmar"

    if tn_pedido_bloqueado_cancelado(pedido):
        return None

    if tn_necesita_completar_carga(pedido):
        return {
            "tipo": "completar_carga",
            "texto": "Completar carga",
            "url": url_for("editar_pedido", id=pedido.id, paso=primer_paso_pendiente_carga(pedido)),
            "clases": clase_confirmar,
            "target": "",
        }

    if requiere_contacto_cliente(pedido) and pedido.estado not in (
        ESTADOS_POST_DESPACHO
        + ESTADOS_DESPACHO_OPERATIVO
        + ["Entregado", "Finalizado"]
    ):
        return {
            "tipo": "completar_carga",
            "texto": "Completar carga",
            "url": url_for("editar_pedido", id=pedido.id, paso=primer_paso_pendiente_carga(pedido)),
            "clases": clase_confirmar,
            "target": "",
        }

    if puede_imprimir_pedido(pedido):
        url_impresion = (
            url_for("imprimir_etiqueta", id=pedido.id, origen="mobile")
            if origen == "mobile"
            else url_for("lanzar_impresion", id=pedido.id, origen=origen)
        )
        return {
            "tipo": "imprimir_etiqueta",
            "texto": "Imprimir etiqueta",
            "url": url_impresion,
            "clases": "btn btn-accion-rapida btn-confirmar" if es_inicio else "btn btn-accion-rapida btn-confirmar",
            "target": "_blank" if es_inicio else "",
        }

    entrega_es_sucursal = (
        pedido.tipo_entrega == "Sucursal"
        or bool(
            str(
                getattr(
                    pedido,
                    "sucursal_nombre",
                    ""
                ) or ""
            ).strip()
        )
    )

    entrega_es_domicilio = (
        pedido.tipo_entrega == "Domicilio"
        and not entrega_es_sucursal
    )


    if (
        pedido.estado in ["Despachado", "Verificar llegada a destino", "Con demora de entrega", "Con reclamo en transporte"]
        and rol in ["carga", "admin"]
        and entrega_es_sucursal
        and not (
            es_via_cargo(pedido.empresa_envio)
            and not pedido.seguimiento
        )
    ):
        return {
            "tipo": "marcar_listo_retirar",
            "texto": "Marcar listo para retirar",
            "url": url_for("confirmar_entrega", id=pedido.id),
            "clases": clase_confirmar,
            "target": "",
        }

    if pedido.estado == Estado.LISTO_RETIRAR and rol in ["carga", "admin"] and entrega_es_sucursal:
        return {
            "tipo": "marcar_entregado",
            "texto": "Marcar entregado",
            "url": url_for("avanzar_pedido", id=pedido.id),
            "clases": clase_confirmar,
            "target": "",
        }

    if pedido.estado == "Verificar llegada a destino" and rol in ["carga", "admin"] and entrega_es_domicilio:
        return {
            "tipo": "marcar_entregado",
            "texto": "Marcar entregado",
            "url": url_for("avanzar_pedido", id=pedido.id),
            "clases": clase_confirmar,
            "target": "",
        }

    if pedido.estado == "Entregado" and rol in ["carga", "admin"]:

        # APB:
        # Mercado Libre Acordás requiere
        # confirmación manual de aviso
        # antes de finalizar.
        if (
            pedido.canal == "Mercado Libre"
            and pedido.ml_tipo == "Acordás la Entrega"
        ):
            return {
                "tipo": "aviso_ml_confirmado",
                "texto": "Ya avisé Mercado Libre",
                "url": url_for("cerrar_pedido", id=pedido.id),
                "clases": clase_confirmar,
                "target": "",
            }

        return {
            "tipo": "cerrar_pedido",
            "texto": "Cerrar pedido",
            "url": url_for("cerrar_pedido", id=pedido.id),
            "clases": clase_confirmar,
            "target": "",
        }

    if pedido.estado == "No entregado" and rol in ["admin", "carga"]:
        return {
            "tipo": "gestionar_devolucion",
            "texto": "Gestionar devolución",
            "url": url_for("gestionar_devolucion", id=pedido.id),
            "clases": clase_confirmar,
            "target": "",
        }

    if pedido.estado == "Reclamar a Mercado Libre" and rol in ["admin", "carga"]:
        return {
            "tipo": "reclamar_ml_devolucion",
            "texto": "Gestionar reclamo Meli",
            "url": url_for("cerrar_reclamo_ml_devolucion", id=pedido.id),
            "clases": clase_confirmar,
            "target": "",
        }

    if pedido.estado in ["Entregado", "Finalizado"]:
        return None

    if (rol == "admin") or (
        rol == "carga"
        and pedido.estado in [
            "Cargando Pedido",
            Estado.DESPACHADO,
            "Con demora de entrega",
            "Con reclamo en transporte",
            "No entregado"
        ]
    ) or (
        rol == "despacho"
        and pedido.estado in [
    Estado.ETIQUETA_IMPRESA,
    Estado.EMBALADO,
]
    ):
        texto = texto_boton_estado(pedido)

        if texto == "Cargar seguimiento":
            url = url_for("editar_pedido", id=pedido.id, modo="seguimiento", volver=origen)
        else:
            url = url_for("avanzar_pedido", id=pedido.id)

        return {
            "tipo": "accion_estado",
            "texto": texto,
            "url": url,
            "clases": clase_confirmar,
            "target": "",
        }

    return None


def fecha_referencia_estado(pedido):
    if pedido.estado == Estado.ETIQUETA_IMPRESA:
        return pedido.fecha_etiqueta_impresa or pedido.fecha_creacion

    if pedido.estado == Estado.EMBALADO:
        return pedido.fecha_embalado or pedido.fecha_etiqueta_impresa or pedido.fecha_creacion

    if pedido.estado in ESTADOS_POST_DESPACHO:
        return pedido.fecha_despachado or pedido.fecha_embalado or pedido.fecha_creacion

    if pedido.estado == "Entregado":
        return pedido.fecha_entregado or pedido.fecha_despachado or pedido.fecha_creacion

    return pedido.fecha_creacion


def tiempo_transcurrido(fecha):
    if not fecha:
        return ""

    ahora = datetime.utcnow()
    diff = ahora - fecha
    minutos = max(0, int(diff.total_seconds() // 60))
    horas = minutos // 60
    dias = horas // 24

    if minutos < 60:
        return f"hace {minutos} min"
    if horas < 24:
        return f"hace {horas} hs"
    return f"hace {dias} días"


def semaforo_pedido(pedido):
    if not pedido:
        return "gris"

    ahora = datetime.utcnow()

    # RECLAMOS / BLOQUEOS SIEMPRE CRÍTICOS
    if pedido.estado == "Reclamar a Mercado Libre" or tn_pedido_bloqueado_cancelado(pedido):
        return "rojo"
    # ---------------------------
    # PEDIDOS DESPACHADOS (seguimiento)
    # ---------------------------
    if pedido.estado in ESTADOS_POST_DESPACHO:
        if not pedido.fecha_despachado:
            return "gris"

        diff_horas = max(0, (ahora - pedido.fecha_despachado).total_seconds() / 3600)

        if diff_horas < 72:
            return "verde"
        if diff_horas < 96:
            return "amarillo"
        return "rojo"

    # ---------------------------
    # PEDIDOS INTERNOS (operación)
    # ---------------------------
    if not pedido.fecha_creacion:
        return "gris"

    diff_horas = max(0, (ahora - pedido.fecha_creacion).total_seconds() / 3600)

    if diff_horas < 12:
        return "verde"
    if diff_horas < 24:
        return "amarillo"
    return "rojo"


def prioridad_pedido(pedido):
    color = semaforo_pedido(pedido)

    if color == "rojo":
        return 0
    if color == "amarillo":
        return 1
    if color == "verde":
        return 2
    return 3


def pedido_con_datos_pendientes(pedido):
    return bool(
        pedido
        and pedido.estado == "Cargando Pedido"
    )


def orden_inicio_pedido(pedido):
    rol = rol_actual()
    prioridad = prioridad_pedido(pedido)
    id_orden = -(pedido.id or 0)

    if rol == "carga":
        grupo = 0 if pedido_con_datos_pendientes(pedido) else 1
        return (grupo, prioridad, id_orden)

    if rol == "despacho":
        grupo = 0 if pedido_sin_despacho(pedido) else 1
        return (grupo, prioridad, id_orden)

    return (prioridad, id_orden)


def alertas_operativas():
    ahora = datetime.utcnow()
    alertas = []
    rol = rol_actual()

    estados_activos = [
        "Cargando Pedido",
        Estado.ETIQUETA_LISTA,
        Estado.ETIQUETA_IMPRESA,
        "Embalado",
        Estado.DESPACHADO,
        "Con demora de entrega",
        "Con reclamo en transporte",
        Estado.VERIFICAR_DESTINO,
        "Listo para retirar",
        "No entregado",
        "Reclamar a Mercado Libre",
    ]
    pedidos = Pedido.query.filter(Pedido.estado.in_(estados_activos)).all()

    sin_despachar = 0
    sin_carga = 0
    seguimiento = 0
    andreani_alertas = 0
    reclamos_sin_revision = 0

    for pedido in pedidos:
        if pedido.estado == "Cargando Pedido" and pedido.fecha_creacion:
            if (ahora - pedido.fecha_creacion).total_seconds() >= 4 * 3600:
                sin_carga += 1

        if pedido.estado in [
    Estado.ETIQUETA_LISTA,
    Estado.ETIQUETA_IMPRESA,
    Estado.EMBALADO,
]:
            ref = fecha_referencia_estado(pedido)
            if ref and (ahora - ref).total_seconds() >= 24 * 3600:
                sin_despachar += 1

        if es_via_cargo(pedido.empresa_envio) and pedido.estado in ESTADOS_POST_DESPACHO:
            ref = pedido.fecha_despachado or fecha_referencia_estado(pedido)
            if ref and (ahora - ref).total_seconds() >= 72 * 3600:
                seguimiento += 1

        if es_andreani_pedido(pedido) and pedido.estado in ESTADOS_POST_DESPACHO:
            if andreani_alerta_pedido(pedido):
                andreani_alertas += 1

        if pedido.estado == Estado.RECLAMO:
            ref_reclamo = pedido.ultima_revision_reclamo or pedido.fecha_hora_reclamo
            if ref_reclamo and (ahora - ref_reclamo).total_seconds() >= 24 * 3600:
                reclamos_sin_revision += 1

    ml_me_sin_etiqueta = int(session.get("ml_me_sin_etiqueta_count") or 0)
    if ml_me_sin_etiqueta and rol in ["carga", "admin"]:
        alertas.append({
            "tipo": "amarilla",
            "texto": f"{ml_me_sin_etiqueta} venta(s) de Mercado Envíos sin etiqueta no ingresaron a Fierro",
            "url": "https://www.mercadolibre.com.ar/ventas/omni/listado",
            "boton": "Ver en ML",
        })

    if rol in ["despacho", "admin"]:
        if sin_despachar:
            alertas.append({"tipo": "roja", "texto": f"{sin_despachar} pedidos sin despacho desde hace más de 24 hs"})

    if rol in ["carga", "admin"]:

        if andreani_alertas:
            alertas.append({"tipo": "amarilla", "texto": f"{andreani_alertas} pedidos Andreani requieren revisión de tracking"})

        if reclamos_sin_revision:
            alertas.append({"tipo": "roja", "texto": f"{reclamos_sin_revision} pedidos con reclamo sin revisar desde hace más de 24 hs"})

    return alertas


def pedido_sin_despacho(pedido):
    return bool(
        pedido
        and pedido.estado not in ESTADOS_POST_DESPACHO + ESTADOS_FINALES[:2]
    )


# TODO APB ESTADOS:
# resumen_operativo separa estados post-despacho en dos familias:
# - seguimiento normal
# - demora/reclamo/no entregado
# Conviene centralizar estas listas como constantes separadas
# cuando se refactoricen KPIs y tablero.
def resumen_operativo(pedidos):

    resumen = {
        "sin_despacho": 0,
        "seguimiento": 0,
        "demora": 0,
        "mercado_envios": 0,
        "total": 0,
    }

    for pedido in pedidos:

        estado = str(pedido.estado or "")

        if pedido_sin_despacho(pedido):

            resumen["sin_despacho"] += 1

        elif estado in [
            "Despachado",
            "Verificar llegada a destino",
            Estado.LISTO_RETIRAR,
        ]:

            resumen["seguimiento"] += 1

        elif estado in [
            "Con demora de entrega",
            "Con reclamo en transporte",
            "No entregado",
        ]:

            resumen["demora"] += 1

        if str(pedido.ml_tipo or "") == "Mercado Envíos":

            resumen["mercado_envios"] += 1

        resumen["total"] += 1

    return resumen




def accion_guardado_paso2():
    return (request.form.get("accion_paso2") or "").strip()


def es_guardado_parcial_acordas():
    canal = request.form.get("canal")
    ml_tipo = request.form.get("ml_tipo")
    empresa_envio = request.form.get("empresa_envio")

    return bool(
        request.method == "POST"
        and (
            (canal == "Mercado Libre" and ml_tipo == "Acordás la Entrega")
            or (canal == "Tienda Nube" and es_via_cargo(empresa_envio))
        )
        and accion_guardado_paso2() == "guardar_y_seguir_despues"
    )

def es_via_cargo(valor):
    """Compara empresa_envio con Vía Cargo tolerando variantes con/sin tilde."""
    if not valor:
        return False
    return valor.strip().lower().replace('\u00ed', 'i') == 'via cargo'


def usuario_actual():
    user_id = session.get("user_id")
    username = session.get("username")

    usuario = None
    if user_id:
        usuario = UsuarioSistema.query.get(user_id)
    elif username:
        usuario = UsuarioSistema.query.filter_by(username=username).first()
        if usuario:
            session["user_id"] = usuario.id

    if not usuario or not usuario.activo:
        return None
    return usuario


def rol_actual():
    usuario = usuario_actual()
    if not usuario:
        return ""
    return usuario.rol


def es_dispositivo_movil():
    ua = (request.headers.get("User-Agent") or "").lower()
    return any(x in ua for x in ["mobile", "android", "iphone", "ipad", "ipod"])

def es_despacho_mobile():
    return rol_actual() == "despacho" and es_dispositivo_movil()



def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not usuario_actual():
            return redirect(url_for("login"))
        if rol_actual() != "admin":
            return redirect(url_for("inicio", error="No tenés permisos para esta acción."))
        return fn(*args, **kwargs)
    return wrapper


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not usuario_actual():
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def registrar_auditoria(accion, entidad=None, entidad_id=None, detalle=None, usuario=None):
    try:
        usuario = usuario or usuario_actual()
        aud = Auditoria(
            usuario_id=getattr(usuario, "id", None) if usuario else None,
            username=getattr(usuario, "username", None) if usuario else (session.get("username") or "sistema"),
            nombre=getattr(usuario, "nombre", None) if usuario else None,
            rol=getattr(usuario, "rol", None) if usuario else None,
            accion=str(accion or "acción")[:120],
            entidad=str(entidad or "")[:80] if entidad else None,
            entidad_id=str(entidad_id or "")[:80] if entidad_id is not None else None,
            detalle=str(detalle or "")[:2000] if detalle else None,
            ip=(request.headers.get("X-Forwarded-For") or request.remote_addr or "")[:80] if request else None,
            metodo=(request.method or "")[:10] if request else None,
            path=(request.path or "")[:300] if request else None,
        )
        db.session.add(aud)
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print("[AUDITORIA] No se pudo registrar:", e)


ACCIONES_GET_AUDITADAS = {
    "avanzar_pedido", "lanzar_impresion", "imprimir_etiqueta", "imprimir_etiqueta_interna",
    "confirmar_entrega", "cerrar_ml", "test_tienda_nube", "sync_tienda_nube",
    "registrar_webhooks_tienda_nube", "borrar_pedidos_tn_prueba", "ml_sync_manual",
    "ml_borrar_prueba", "ml_reset_total", "ml_desconectar",
}


def es_accion_auditable():
    endpoint = request.endpoint or ""
    if endpoint in ["static", "login"]:
        return False
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        return True
    return endpoint in ACCIONES_GET_AUDITADAS


@app.after_request
def auditar_acciones(response):
    try:
        if response.status_code >= 400:
            return response
        if not usuario_actual():
            return response
        if not es_accion_auditable():
            return response

        endpoint = request.endpoint or "acción"
        entidad = None
        entidad_id = None
        if request.view_args and "id" in request.view_args:
            entidad = "pedido"
            entidad_id = request.view_args.get("id")
        elif "pedido_id" in request.form:
            entidad = "pedido"
            entidad_id = request.form.get("pedido_id")

        acciones_legibles = {
            "avanzar_pedido": "Avanzó estado del pedido",
            "lanzar_impresion": "Lanzó impresión de etiqueta",
            "imprimir_etiqueta": "Imprimió etiqueta",
            "imprimir_etiqueta_interna": "Imprimió etiqueta interna",
            "confirmar_entrega": "Avisó / confirmó entrega",
            "cerrar_ml": "Cerró aviso Mercado Libre",
            "sync_tienda_nube": "Sincronizó Tienda Nube",
            "registrar_webhooks_tienda_nube": "Registró webhooks Tienda Nube",
            "borrar_pedidos_tn_prueba": "Borró pedidos TN de prueba",
            "ml_sync_manual": "Sincronizó Mercado Libre",
            "ml_borrar_prueba": "Borró pedidos ML de prueba",
            "ml_reset_total": "Reset total Mercado Libre",
            "ml_desconectar": "Desconectó Mercado Libre",
        }
        accion = acciones_legibles.get(endpoint, endpoint.replace("_", " ").capitalize())
        detalle = f"{request.method} {request.path}"
        registrar_auditoria(accion, entidad=entidad, entidad_id=entidad_id, detalle=detalle)
    except Exception as e:
        print("[AUDITORIA] Error after_request:", e)
    return response


def estados_visibles_inicio():
    rol = rol_actual()

    if rol == "admin":
        return [
            "Cargando Pedido",
            Estado.ETIQUETA_LISTA,
            Estado.ETIQUETA_IMPRESA,
            "Embalado",
            Estado.DESPACHADO,
            "Con demora de entrega",
            "Con reclamo en transporte",
            Estado.VERIFICAR_DESTINO,
            Estado.LISTO_RETIRAR,
            "No entregado",
            "Reclamar a Mercado Libre",
            "Entregado",
        ]

    if rol == "carga":
        # APB:
        # Los pedidos de preparación/despacho no deben mezclarse en Inicio.
        return [
            "Cargando Pedido",
            Estado.DESPACHADO,
            "Con demora de entrega",
            "Con reclamo en transporte",
            Estado.VERIFICAR_DESTINO,
            Estado.LISTO_RETIRAR,
            "No entregado",
            "Reclamar a Mercado Libre",
            "Entregado",
        ]

    if rol == "despacho":
        return ESTADOS_DESPACHO_OPERATIVO

    return []


def puede_ver_pedidos_preparacion():
    return rol_actual() in ["admin", "carga"]


def estados_visibles_preparacion():
    if not puede_ver_pedidos_preparacion():
        return []

    return ESTADOS_DESPACHO_OPERATIVO

def titulo_inicio_por_rol():
    rol = rol_actual()

    if rol == "admin":
        return "Panel administrador"

    if rol == "carga":
        return "Panel operador de carga"

    if rol == "despacho":
        return "Panel embalaje y despacho"

    return "Pedidos"


def subtitulo_inicio_por_rol():
    rol = rol_actual()

    if rol == "admin":
        return "Control total del sistema"

    if rol == "carga":
        return "Carga, edición y seguimiento final"

    if rol == "despacho":
        return "Pedidos listos para imprimir, embalar y despachar"

    return "Vista general de trabajo"


def puede_ver_pedido(pedido):
    rol = rol_actual()

    if rol == "admin":
        return True

    if rol == "carga":
        return (
            pedido.estado in estados_visibles_inicio()
            or pedido.estado in estados_visibles_preparacion()
        )

    if rol == "despacho":
        return pedido.estado in ESTADOS_DESPACHO_OPERATIVO

    return False





def puede_editar_pedido(pedido):
    rol = rol_actual()

    if rol == "admin":
        return True

    if rol == "carga":
        return pedido.estado in ["Cargando Pedido"] + ESTADOS_POST_DESPACHO + ["Reclamar a Mercado Libre", "Entregado"]

    return False


def puede_eliminar_pedido(pedido):
    # APB: solo Admin puede borrar pedidos, sin importar estado/canal/instancia.
    return rol_actual() == "admin"


def puede_cerrar_pedido(pedido):
    # APB:
    # Cerrar pedido implica moverlo a Finalizado.
    # Solo Admin o Carga pueden cerrar, y únicamente desde Entregado.
    if rol_actual() not in ["admin", "carga"]:
        return False

    if not pedido or pedido.estado != "Entregado":
        return False

    if getattr(pedido, "ml_claim_abierto", False):
        return False

    return True


def puede_agregar_item(pedido):
    # APB:
    # Agregar ítems modifica la composición real del pedido.
    # Solo Admin o Carga pueden hacerlo, y nunca después del despacho/cierre.
    if rol_actual() not in ["admin", "carga"]:
        return False

    if not pedido:
        return False

    if pedido.estado in [
        Estado.DESPACHADO,
        "Con demora de entrega",
        "Con reclamo en transporte",
        Estado.VERIFICAR_DESTINO,
        Estado.LISTO_RETIRAR,
        "No entregado",
        "Entregado",
        "Finalizado",
        "Cancelado",
    ]:
        return False

    return True


def puede_operar_whatsapp(pedido):
    # APB:
    # WhatsApp operativo solo puede ser manejado por Admin o Carga.
    # Despacho no debe intervenir conversaciones con clientes.
    if rol_actual() not in ["admin", "carga"]:
        return False

    if not pedido:
        return False

    if not puede_ver_pedido(pedido):
        return False

    return True


def puede_crear_pedido():
    return rol_actual() in ["admin", "carga"]

def puede_ver_historico():
    return rol_actual() in ["admin", "carga"]

def etiqueta_es_archivo_local(etiqueta_archivo):
    archivo = os.path.basename(str(etiqueta_archivo or ""))
    if not archivo:
        return False
    return os.path.exists(os.path.join(app.config["UPLOAD_FOLDER"], archivo))

def puede_imprimir_pedido(pedido):
    rol = rol_actual()

    imprimible = pedido.estado == Estado.ETIQUETA_LISTA

    if rol == "admin":
        return pedido.estado not in ["Entregado", "Finalizado"] and imprimible

    if rol == "despacho":
        return pedido.estado not in ["Entregado", "Finalizado"] and imprimible

    return False


def requiere_cargar_seguimiento(pedido):
    return bool(
        pedido.estado in ["Despachado", "Con reclamo en transporte"]
        and es_via_cargo(pedido.empresa_envio)
        and not pedido.seguimiento
    )


def puede_avanzar_segun_rol(pedido):
    rol = rol_actual()

    if rol == "admin":
        return True, []

    if rol == "carga":

        # Carga puede cerrar la carga inicial del pedido manual / DUX.
        if pedido.estado == "Cargando Pedido":
            return True, []

        if pedido.estado in [
            "Despachado",
            "Con demora de entrega",
            "Con reclamo en transporte",
            "Verificar llegada a destino",
            "Listo para retirar",
            "No entregado",
            "Reclamar a Mercado Libre",
        ]:
            return True, []

        return False, ["Este estado lo trabaja Embalaje y Despacho."]

    if rol == "despacho":
        if pedido.estado in [Estado.ETIQUETA_IMPRESA, Estado.EMBALADO]:
            return True, []
        return False, ["Este estado lo trabaja el operador de Carga."]

    return False, ["No tenés permisos para esta acción."]

# TODO APB WORKFLOW:
# Este guard ya funciona como motor preliminar de transición.
# Pendiente futuro:
# - evitar calcular siguiente_estado() dos veces entre validación y ejecución;
# - separar resultado en objeto/estructura con permitido, errores y nuevo_estado;
# - hacer que rutas, mobile, automatizaciones y futuras APIs usen esta única validación;
# - agregar tests específicos de transición por rol/estado/canal.
# APB:
# Guard oficial para avanzar estados operativos.
# Toda transición manual por botón "avanzar" debe pasar por acá antes de ejecutar
# siguiente_estado() + aplicar_estado_y_fechas().
# No saltear este guard desde rutas, mobile, automatizaciones ni futuras APIs.
def puede_avanzar_pedido(pedido):
    errores = motor_bloqueo(pedido)

    if pedido.estado == Estado.CARGANDO and errores:
        return False, errores

    if pedido.estado == Estado.DESPACHADO:
        if es_via_cargo(pedido.empresa_envio) and not pedido.seguimiento:
            return False, ["En Vía Cargo el seguimiento se carga después del despacho."]

    nuevo_estado = siguiente_estado(pedido.estado)
    if (
        nuevo_estado == Estado.DESPACHADO
        and getattr(pedido, "agregado_pendiente_revision", False)
    ):
        return False, [
            "AGREGADO PENDIENTE: antes de marcar despachado, despacho debe revisar los items agregados y confirmar la revisión."
        ]

    puede_por_rol, errores_rol = puede_avanzar_segun_rol(pedido)
    if not puede_por_rol:
        return False, errores_rol

    return True, []


def cargar_items_desde_texto(pedido, items_texto):
    PedidoItem.query.filter_by(pedido_id=pedido.id).delete()

    items = items_texto.splitlines()

    for linea in items:
        if linea.strip():
            partes = [p.strip() for p in linea.split("|")]

            if len(partes) >= 3:
                sku = partes[0]
                descripcion = partes[1]
                cantidad = int(partes[2])

                item = PedidoItem(
                    pedido_id=pedido.id,
                    sku=sku,
                    descripcion=descripcion,
                    cantidad=cantidad
                )
                db.session.add(item)


def items_a_texto(pedido):
    lineas = []
    for item in pedido.items:
        lineas.append(f"{item.sku}|{item.descripcion}|{item.cantidad}")
    return "\n".join(lineas)


def _clave_item_control(sku, descripcion):
    sku_norm = str(sku or "").strip().lower()
    desc_norm = re.sub(r"\s+", " ", str(descripcion or "").strip().lower())
    return f"{sku_norm}|{desc_norm}"


def resumen_items_desde_texto(items_texto):
    resumen = {}
    for linea in str(items_texto or "").splitlines():
        if not linea.strip():
            continue
        partes = [p.strip() for p in linea.split("|")]
        if len(partes) < 3:
            continue
        sku, descripcion, cantidad_raw = partes[0], partes[1], partes[2]
        try:
            cantidad = int(float(str(cantidad_raw).replace(",", ".")))
        except Exception:
            cantidad = 0
        clave = _clave_item_control(sku, descripcion)
        resumen[clave] = resumen.get(clave, 0) + max(cantidad, 0)
    return resumen


def resumen_items_actuales_pedido(pedido):
    resumen = {}
    for item in (pedido.items or []):
        clave = _clave_item_control(item.sku, item.descripcion)
        resumen[clave] = resumen.get(clave, 0) + int(item.cantidad or 0)
    return resumen


def hay_productos_agregados(items_antes, items_despues):
    for clave, cantidad_nueva in (items_despues or {}).items():
        if int(cantidad_nueva or 0) > int((items_antes or {}).get(clave, 0) or 0):
            return True
    return False


def requiere_comprobante_dux_por_agregado(pedido, canal, ml_tipo, items_texto_nuevo):
    return bool(
        pedido
        and canal == "Mercado Libre"
        and ml_tipo == "Acordás la Entrega"
        and hay_productos_agregados(
            resumen_items_actuales_pedido(pedido),
            resumen_items_desde_texto(items_texto_nuevo)
        )
    )




def extraer_datos_cliente_comprobante_dux_desde_pdf(archivo_pdf):
    """Extrae datos de cabecera de un comprobante DUX PDF.

    APB:
    - Completa solo los campos que DUX informa con claridad.
    - No inventa teléfono ni mail si no figuran en el comprobante.
    - Devuelve también el texto recortado para auditoría/diagnóstico.
    """
    if not archivo_pdf or not archivo_pdf.filename:
        return {"ok": False, "datos": {}, "texto": "", "error": "No se recibió archivo PDF."}

    try:
        archivo_pdf.stream.seek(0)
        contenido = archivo_pdf.read()
        archivo_pdf.stream.seek(0)

        doc = fitz.open(stream=contenido, filetype="pdf")
        try:
            partes = []
            for page in doc:
                partes.append(page.get_text("text") or "")
            texto = "\n".join(partes)
        finally:
            doc.close()
    except Exception as e:
        try:
            archivo_pdf.stream.seek(0)
        except Exception:
            pass
        return {"ok": False, "datos": {}, "texto": "", "error": f"No se pudo leer la cabecera del PDF DUX: {e}"}

    def _limpiar(valor):
        return re.sub(r"\s+", " ", str(valor or "").strip()).strip(" -:")

    datos = {}

    m_numero = re.search(r"N[º°]\s*([0-9]{4,5}-[0-9]{6,10})", texto, re.IGNORECASE)
    if m_numero:
        datos["id_venta"] = _limpiar(m_numero.group(1))

    m_cliente = re.search(r"SEÑOR/ES:\s*(.*?)(?:\s+IVA:|\s+CUIT:|\n)", texto, re.IGNORECASE | re.S)
    if m_cliente:
        datos["cliente"] = _limpiar(m_cliente.group(1))

    m_cuit = re.search(r"CUIT:\s*([0-9.\-]{7,20})", texto, re.IGNORECASE)
    if m_cuit:
        datos["dni"] = re.sub(r"\D", "", m_cuit.group(1))

    m_domicilio = re.search(r"DOMICILIO:\s*(.*?)(?:\s+LOCALIDAD:|\n)", texto, re.IGNORECASE | re.S)
    if m_domicilio:
        datos["direccion"] = _limpiar(m_domicilio.group(1))

    m_localidad = re.search(r"LOCALIDAD:\s*(.*?)(?:\s+PROVINCIA:|\n)", texto, re.IGNORECASE | re.S)
    if m_localidad:
        datos["localidad"] = _limpiar(m_localidad.group(1))

    m_provincia = re.search(r"PROVINCIA:\s*(.*?)(?:\s+CONDICION|\s+CONDICIÓN|\n)", texto, re.IGNORECASE | re.S)
    if m_provincia:
        datos["provincia"] = _limpiar(m_provincia.group(1))

    return {
        "ok": bool(datos),
        "datos": datos,
        "texto": texto[:4000],
        "error": "" if datos else "No se detectaron datos de cliente en el comprobante DUX.",
    }

def canal_requiere_dux_obligatorio(canal):
    return canal in ["Mayorista", "Presencial"]


def items_detectados_a_texto(items):
    lineas = []
    for item in items or []:
        sku = str(item.get("sku") or "").strip()
        descripcion = str(item.get("descripcion") or sku).strip()
        try:
            cantidad = int(float(str(item.get("cantidad") or 1).replace(",", ".")))
        except Exception:
            cantidad = 1
        if sku:
            lineas.append(f"{sku}|{descripcion}|{max(cantidad, 1)}")
    return "\n".join(lineas)


def puede_administrar_integraciones():
    return rol_actual() == "admin"


def tn_store_id():
    return (os.getenv("TN_STORE_ID") or "").strip()


def tn_access_token():
    return (os.getenv("TN_ACCESS_TOKEN") or "").strip()


def tn_app_secret():
    return (os.getenv("TN_APP_SECRET") or "").strip()


def tn_config_faltante():
    faltantes = []
    if not tn_store_id():
        faltantes.append("TN_STORE_ID")
    if not tn_access_token():
        faltantes.append("TN_ACCESS_TOKEN")
    return faltantes


def cuenta_tn_actual():
    cuenta = TiendaNubeCuenta.query.order_by(TiendaNubeCuenta.id.asc()).first()
    if not cuenta and tn_store_id():
        cuenta = TiendaNubeCuenta(store_id=tn_store_id(), estado_conexion="configurada")
        db.session.add(cuenta)
        db.session.commit()
    return cuenta


def tn_http_json(method, path, data=None, params=None):
    if tn_config_faltante():
        raise ValueError(f"Faltan variables TN: {', '.join(tn_config_faltante())}")

    params = params or {}
    query = urlencode(params)
    url = f"https://api.tiendanube.com/v1/{tn_store_id()}{path}"
    if query:
        url = f"{url}?{query}"

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")

    req = Request(url, data=body, method=method.upper())
    req.add_header("Authentication", f"bearer {tn_access_token()}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Sistema Fierro APB (contacto: fierroargento)")

    try:
        with urlopen(req, timeout=15) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except HTTPError as e:
        body_error = e.read().decode("utf-8", errors="ignore")
        raise ValueError(f"TN API {e.code}: {body_error[:500]}")
    except URLError as e:
        raise ValueError(f"TN conexión fallida: {e.reason}")


def tn_parse_datetime(valor):
    if not valor:
        return None
    try:
        limpio = str(valor).replace("Z", "+00:00")
        return datetime.fromisoformat(limpio).replace(tzinfo=None)
    except Exception:
        return None


def tn_texto_multilenguaje(valor):
    if isinstance(valor, dict):
        return valor.get("es") or valor.get("pt") or valor.get("en") or next(iter(valor.values()), "")
    return valor or ""


def tn_extraer_order_id(payload):
    if not payload:
        return None
    for key in ("id", "order_id"):
        if payload.get(key):
            return str(payload.get(key))
    resource = str(payload.get("resource") or "")
    match = re.search(r"/orders/(\d+)", resource)
    if match:
        return match.group(1)
    return None


def tn_webhook_firma_valida(raw_body):
    secret = tn_app_secret()
    if not secret:
        return True

    firma_recibida = (
        request.headers.get("X-Linkedstore-Hmac-SHA256")
        or request.headers.get("X-TiendaNube-Hmac-SHA256")
        or request.headers.get("X-Hmac-Sha256")
        or ""
    ).strip()
    if not firma_recibida:
        return False

    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    firma_base64 = base64.b64encode(digest).decode("utf-8")
    firma_hex = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(firma_recibida, firma_base64) or hmac.compare_digest(firma_recibida, firma_hex)


def tn_direccion_desde_order(order):
    shipping = order.get("shipping_address") or {}
    direccion_partes = []
    calle = shipping.get("address") or shipping.get("street") or order.get("billing_address") or ""
    numero = shipping.get("number") or order.get("billing_number") or ""
    piso = shipping.get("floor") or order.get("billing_floor") or ""
    if calle:
        direccion_partes.append(str(calle))
    if numero:
        direccion_partes.append(str(numero))
    if piso:
        direccion_partes.append(f"Piso/Depto: {piso}")

    return {
        "direccion": " ".join(direccion_partes).strip(),
        "codigo_postal": str(shipping.get("zipcode") or order.get("billing_zipcode") or "").strip(),
        "localidad": str(shipping.get("city") or shipping.get("locality") or order.get("billing_city") or order.get("billing_locality") or "").strip(),
        "provincia": str(shipping.get("province") or order.get("billing_province") or "").strip(),
    }


def tn_mapear_envio(order):
    shipping_option = order.get("shipping_option") or ""
    shipping_carrier = order.get("shipping_carrier_name") or order.get("shipping_carrier") or ""
    shipping_type = order.get("shipping_type") or order.get("shipping_pickup_type") or ""

    shipping_data = order.get("shipping") if isinstance(order.get("shipping"), dict) else {}
    if shipping_data:
        shipping_option = shipping_option or shipping_data.get("option") or shipping_data.get("name") or ""
        shipping_carrier = shipping_carrier or shipping_data.get("carrier") or shipping_data.get("carrier_name") or ""
        shipping_type = shipping_type or shipping_data.get("type") or ""

    texto_envio = " ".join([str(shipping_option), str(shipping_carrier), str(shipping_type)]).lower()
    empresa = ""
    if "andreani" in texto_envio:
        empresa = "Andreani"
    elif "correo" in texto_envio:
        empresa = "Correo Argentino"
    elif "via cargo" in texto_envio or "vía cargo" in texto_envio or "viacargo" in texto_envio:
        empresa = "Vía Cargo"

    tipo_entrega = "Domicilio"
    if "sucursal" in texto_envio or "pickup" in texto_envio or "retiro" in texto_envio:
        tipo_entrega = "Sucursal"

    return shipping_type, shipping_carrier, shipping_option, empresa, tipo_entrega


def tn_estado_apb(order):
    status = str(order.get("status") or "").lower()
    payment_status = str(order.get("payment_status") or order.get("financial_status") or "").lower()
    observaciones = []

    if status in ("cancelled", "canceled", "voided") or order.get("cancelled_at"):
        observaciones.append("NO DESPACHAR - Pedido cancelado en Tienda Nube.")
    if payment_status and payment_status not in ("paid", "authorized", "approved"):
        observaciones.append(f"NO DESPACHAR - Pago TN en estado: {payment_status}.")

    return "Cargando Pedido", " ".join(observaciones)


def tn_guardar_items(pedido, order):
    productos = order.get("products") or []
    PedidoItem.query.filter_by(pedido_id=pedido.id).delete()
    for producto in productos:
        sku = str(producto.get("sku") or producto.get("barcode") or "").strip()
        nombre = tn_texto_multilenguaje(producto.get("name")) or producto.get("product_name") or "Producto TN"
        try:
            cantidad = int(float(producto.get("quantity") or 1))
        except Exception:
            cantidad = 1
        db.session.add(PedidoItem(
            pedido_id=pedido.id,
            sku=sku,
            descripcion=str(nombre)[:200],
            cantidad=cantidad,
        ))


def tn_pago_confirmado(order):
    payment_status = str(order.get("payment_status") or order.get("financial_status") or "").lower().strip()
    return payment_status in ("paid", "approved", "authorized", "received", "recibido")


def tn_pedido_ya_enviado(order):
    """Devuelve True solo si TN ya considera el pedido enviado/cumplido.

    APB TN:
    - Por empaquetar => entra
    - Por enviar => entra
    - Enviada => no entra

    Importante: en Tienda Nube un pedido pagado puede venir con status=closed,
    por eso NO usamos closed como indicador de enviado.
    """
    fulfillment_status = str(
        order.get("fulfillment_status")
        or order.get("shipping_status")
        or ""
    ).lower().strip()

    shipping_status = ""
    shipping_data = order.get("shipping") if isinstance(order.get("shipping"), dict) else {}
    if shipping_data:
        shipping_status = str(
            shipping_data.get("status")
            or shipping_data.get("fulfillment_status")
            or shipping_data.get("shipment_status")
            or ""
        ).lower().strip()

    estados_enviados = {
        "fulfilled", "delivered", "shipped", "completed",
        "enviada", "enviado", "despachado", "despachada", "entregado", "entregada",
    }
    if fulfillment_status in estados_enviados or shipping_status in estados_enviados:
        return True

    texto = " ".join([fulfillment_status, shipping_status])
    indicadores_enviado = [
        "fulfilled", "delivered", "shipped", "completed",
        "enviada", "enviado", "despachado", "despachada", "entregado", "entregada",
    ]
    return any(indicador in texto for indicador in indicadores_enviado)


def tn_pedido_cancelado(order):
    status = str(order.get("status") or "").lower().strip()
    return bool(status in ("cancelled", "canceled", "voided") or order.get("cancelled_at"))


def tn_extraer_tracking(order):
    """Extrae tracking TN de forma defensiva y evita confundirlo con numero de orden.

    Caso real detectado: Tienda Nube puede traer campos genericos como `number`
    dentro de shipping/fulfillment. Ese `number` puede ser el numero de pedido o
    paquete (ej. 319) y NO el seguimiento real. Por eso solo aceptamos claves
    explicitamente relacionadas con tracking/seguimiento y descartamos valores
    iguales al id/numero de orden o demasiado cortos.
    """
    candidatos = []

    order_id = str(order.get("id") or "").strip()
    order_number = str(order.get("number") or order.get("order_number") or "").strip()

    claves_numero = {
        "tracking_number", "tracking_code", "tracking", "tracking_id",
        "shipping_tracking_number", "shipping_tracking_code", "shipping_tracking",
        "shipment_tracking_number", "shipment_tracking_code",
        "tracking_codes", "tracking_numbers", "code_tracking",
        "codigo_seguimiento", "numero_seguimiento", "nro_seguimiento",
    }
    claves_url = {
        "tracking_url", "tracking_link", "tracking_page", "tracking_url_public",
        "shipping_tracking_url", "shipment_tracking_url",
    }

    def valor_valido(numero):
        numero = str(numero or "").strip()
        if not numero:
            return ""
        if numero in {order_id, order_number}:
            return ""
        if numero.isdigit() and len(numero) < 8:
            return ""
        return numero

    def agregar(numero="", url=""):
        numero = valor_valido(numero)
        url = str(url or "").strip()
        if numero or url:
            candidatos.append((numero, url))

    def recorrer(obj):
        if isinstance(obj, dict):
            tracking_info = obj.get("tracking_info")
            if isinstance(tracking_info, dict):
                agregar(tracking_info.get("code"), tracking_info.get("url"))

            tracking_history = obj.get("tracking_info_history") or []
            if isinstance(tracking_history, list):
                for hist in tracking_history:
                    if isinstance(hist, dict):
                        to_info = hist.get("to_tracking_info")
                        from_info = hist.get("from_tracking_info")
                        if isinstance(to_info, dict):
                            agregar(to_info.get("code"), to_info.get("url"))
                        if isinstance(from_info, dict):
                            agregar(from_info.get("code"), from_info.get("url"))

            numero = ""
            url = ""
            for k, v in obj.items():
                kl = str(k).lower().strip()
                if kl in claves_numero:
                    if isinstance(v, list):
                        for item in v:
                            agregar(item, "")
                    elif isinstance(v, dict):
                        recorrer(v)
                    else:
                        numero = numero or str(v or "").strip()
                elif kl in claves_url:
                    url = url or str(v or "").strip()
            agregar(numero, url)
            for v in obj.values():
                if isinstance(v, (dict, list)):
                    recorrer(v)
        elif isinstance(obj, list):
            for item in obj:
                recorrer(item)

    recorrer(order)

    con_numero = [(n, u) for n, u in candidatos if n]
    if con_numero:
        con_numero.sort(key=lambda par: (len(par[0]), any(c.isalpha() for c in par[0])), reverse=True)
        return con_numero[0]

    for numero, url in candidatos:
        if url:
            return numero, url
    return "", ""



def tn_tracking_sospechoso(valor):
    valor = str(valor or "").strip()
    if not valor:
        return True
    if valor.isdigit() and len(valor) < 8:
        return True
    return False


def tn_enriquecer_order_con_fulfillment(order_id):
    order_id = str(order_id or "").strip()
    if not order_id:
        return {}
    try:
        order = tn_http_json("GET", f"/orders/{order_id}", params={"aggregates": "fulfillment_orders"})
    except Exception:
        order = tn_http_json("GET", f"/orders/{order_id}")
    if not isinstance(order, dict):
        return {}

    fulfillment_orders = []
    existentes = order.get("fulfillment_orders") or []
    if isinstance(existentes, list):
        fulfillment_orders.extend([x for x in existentes if isinstance(x, dict)])

    try:
        respuesta = tn_http_json("GET", f"/orders/{order_id}/fulfillment-orders")
        if isinstance(respuesta, list):
            fulfillment_orders.extend([x for x in respuesta if isinstance(x, dict)])
    except Exception as e:
        print(f"[TN] No se pudieron leer fulfillment-orders de {order_id}: {e}")

    enriquecidos = []
    vistos = set()
    for fulfillment in fulfillment_orders:
        fid = str(fulfillment.get("id") or fulfillment.get("fulfillment_id") or "").strip()
        clave = fid or json.dumps(fulfillment, sort_keys=True, default=str)[:80]
        if clave in vistos:
            continue
        vistos.add(clave)
        detalle = fulfillment
        if fid:
            try:
                detalle_full = tn_http_json("GET", f"/orders/{order_id}/fulfillment-orders/{fid}")
                if isinstance(detalle_full, dict):
                    detalle = detalle_full
            except Exception as e:
                print(f"[TN] No se pudo leer fulfillment {fid} de {order_id}: {e}")
            try:
                eventos = tn_http_json("GET", f"/orders/{order_id}/fulfillment-orders/{fid}/tracking-events")
                if isinstance(eventos, list):
                    detalle["_tracking_events_api"] = eventos
            except Exception as e:
                print(f"[TN] No se pudieron leer tracking-events {fid} de {order_id}: {e}")
        enriquecidos.append(detalle)
    if enriquecidos:
        order["_fulfillment_orders_api"] = enriquecidos
    return order

def tn_marcar_cancelado_existente(pedido, order):
    if not pedido:
        return None
    pedido.tn_order_status = str(order.get("status") or pedido.tn_order_status or "cancelled")[:50]
    pedido.tn_payment_status = str(order.get("payment_status") or order.get("financial_status") or pedido.tn_payment_status or "")[:50]
    pedido.tn_cancelled_at = tn_parse_datetime(order.get("cancelled_at")) or pedido.tn_cancelled_at or datetime.utcnow()
    pedido.ultima_sync_tn = datetime.utcnow()
    aviso = "NO DESPACHAR - Pedido cancelado en Tienda Nube."
    obs = str(pedido.observaciones or "")
    if aviso not in obs:
        pedido.observaciones = (f"{aviso} {obs}".strip())[:300]
    # Lo dejamos en Cargando Pedido para que sea visible para Carga/Admin y bloqueado por motor_bloqueo.
    if pedido.estado not in ["Finalizado", "Entregado"]:
        pedido.estado = "Cargando Pedido"
    return pedido


def tn_actualizar_enviado_existente(pedido, order):
    if not pedido:
        return None
    numero, url_tracking = tn_extraer_tracking(order)
    pedido.tn_order_status = str(order.get("status") or pedido.tn_order_status or "")[:50]
    pedido.tn_payment_status = str(order.get("payment_status") or order.get("financial_status") or pedido.tn_payment_status or "")[:50]
    pedido.tn_fulfillment_status = str(order.get("fulfillment_status") or order.get("shipping_status") or pedido.tn_fulfillment_status or "")[:80]
    if numero:
        pedido.tn_tracking_number = numero[:100]
        pedido.seguimiento = numero[:100]
    elif tn_tracking_sospechoso(pedido.seguimiento):
        pedido.tn_tracking_number = None
        pedido.seguimiento = None
    if url_tracking:
        pedido.tn_tracking_url = url_tracking[:300]
    pedido.ultima_sync_tn = datetime.utcnow()

    if pedido.estado not in ["Entregado", "Finalizado", "No entregado", "Reclamar a Mercado Libre"]:
        if not pedido.fecha_despachado:
            pedido.fecha_despachado = datetime.utcnow()
        pedido.estado = Estado.VERIFICAR_DESTINO if (pedido.seguimiento or pedido.tn_tracking_url) else Estado.DESPACHADO
    return pedido


def tn_pedido_bloqueado_cancelado(pedido):
    return bool(
        pedido
        and pedido.canal == "Tienda Nube"
        and (
            str(pedido.tn_order_status or "").lower() in ["cancelled", "canceled", "voided"]
            or "NO DESPACHAR - Pedido cancelado en Tienda Nube" in str(pedido.observaciones or "")
        )
    )


def tn_tipo_envio_visual(pedido):
    if not pedido or pedido.canal != "Tienda Nube":
        return ""
    texto = " ".join([
        str(pedido.tn_shipping_option or ""),
        str(pedido.tn_shipping_carrier or ""),
        str(pedido.tn_shipping_type or ""),
        str(pedido.empresa_envio or ""),
    ]).lower()
    if (
        "contact" in texto
        or "contactar" in texto
        or "contactamos" in texto
        or "te vamos a contactar" in texto
        or "coordin" in texto
        or "acord" in texto
        or "personalizado" in texto
        or "via cargo" in texto
        or "vía cargo" in texto
    ):
        return "Acordás la Entrega"
    if pedido.empresa_envio in ["Andreani", "Correo Argentino"]:
        return pedido.empresa_envio
    return pedido.empresa_envio or pedido.tn_shipping_option or "Pendiente"


def tn_admin_base_url():
    base = (os.getenv("TN_ADMIN_BASE_URL") or "https://fierro100argento.mitiendanube.com").strip()
    return base.rstrip("/")


def link_detalle_venta(pedido):
    if not pedido or not pedido.id_venta:
        return ""
    if pedido.canal == "Mercado Libre":
        return ml_link_detalle_venta(pedido)
    if pedido.canal == "Tienda Nube":
        return f"{tn_admin_base_url()}/admin/orders/{pedido.id_venta}"
    return ""


def tn_necesita_completar_carga(pedido):
    if not pedido or pedido.canal != "Tienda Nube" or pedido.estado != "Cargando Pedido":
        return False
    if tn_pedido_bloqueado_cancelado(pedido):
        return False
    return bool(motor_bloqueo(pedido)) or not puede_imprimir_pedido(pedido)


def tn_pedido_apto_para_fierro(order):
    if not order:
        return False, "pedido vacío"

    if tn_pedido_cancelado(order):
        return False, "pedido cancelado"

    if not tn_pago_confirmado(order):
        estado_pago = str(order.get("payment_status") or order.get("financial_status") or "sin estado")
        return False, f"pago no confirmado: {estado_pago}"

    if tn_pedido_ya_enviado(order):
        return False, "pedido ya enviado/entregado"

    return True, "ok"


def tn_importar_o_actualizar_pedido(order):
    tn_id = str(order.get("id") or "").strip()
    if not tn_id:
        return None, "omitido_sin_id"

    apto, motivo_omision = tn_pedido_apto_para_fierro(order)
    pedido = Pedido.query.filter_by(tn_order_id=tn_id).first()

    # APB TN:
    # - Pedido nuevo cancelado/enviado/no pago: no ingresa.
    # - Pedido existente cancelado: se bloquea con NO DESPACHAR.
    # - Pedido existente enviado: se actualiza seguimiento/estado operativo.
    if not apto:
        if pedido and tn_pedido_cancelado(order):
            tn_marcar_cancelado_existente(pedido, order)
            return pedido, "actualizado_cancelado_no_despachar"
        if pedido and tn_pedido_ya_enviado(order):
            tn_actualizar_enviado_existente(pedido, order)
            return pedido, "actualizado_enviado"
        return pedido, f"omitido_{motivo_omision}"

    creado = False
    if not pedido:
        pedido = Pedido(
            origen="tiendanube",
            canal="Tienda Nube",
            id_venta=tn_id,
            tn_order_id=tn_id,
            estado="Cargando Pedido",
            cliente="Cliente TN",
        )
        db.session.add(pedido)
        db.session.flush()
        creado = True

    customer = order.get("customer") or {}
    direccion = tn_direccion_desde_order(order)
    shipping_type, shipping_carrier, shipping_option, empresa, tipo_entrega = tn_mapear_envio(order)
    estado_sugerido, observacion_apb = tn_estado_apb(order)

    nombre_cliente = (
        order.get("contact_name")
        or customer.get("name")
        or order.get("billing_name")
        or pedido.cliente
        or "Cliente TN"
    )
    pedido.cliente = str(nombre_cliente).strip()[:120] or "Cliente TN"
    pedido.mail = (order.get("contact_email") or customer.get("email") or pedido.mail or "")[:120]
    pedido.telefono = str(order.get("contact_phone") or customer.get("phone") or order.get("billing_phone") or pedido.telefono or "")[:30]
    pedido.dni = str(order.get("contact_identification") or customer.get("identification") or order.get("billing_document") or pedido.dni or "")[:20]

    pedido.origen = "tiendanube"
    pedido.canal = "Tienda Nube"
    pedido.id_venta = tn_id
    pedido.tn_order_id = tn_id
    pedido.tn_order_number = str(order.get("number") or order.get("order_number") or "")[:50]
    pedido.tn_order_status = str(order.get("status") or "")[:50]
    pedido.tn_payment_status = str(order.get("payment_status") or order.get("financial_status") or "")[:50]
    pedido.tn_paid_at = tn_parse_datetime(order.get("paid_at"))
    pedido.tn_cancelled_at = tn_parse_datetime(order.get("cancelled_at"))
    pedido.tn_shipping_type = str(shipping_type or "")[:80]
    pedido.tn_shipping_carrier = str(shipping_carrier or "")[:100]
    pedido.tn_shipping_option = str(shipping_option or "")[:200]
    numero_tracking, url_tracking = tn_extraer_tracking(order)
    if numero_tracking:
        pedido.tn_tracking_number = numero_tracking[:100]
        pedido.seguimiento = numero_tracking[:100]
    elif tn_tracking_sospechoso(pedido.seguimiento):
        pedido.tn_tracking_number = None
        pedido.seguimiento = None
    if url_tracking:
        pedido.tn_tracking_url = url_tracking[:300]
    pedido.empresa_envio = empresa or pedido.empresa_envio
    pedido.tipo_entrega = tipo_entrega or pedido.tipo_entrega
    pedido.direccion = direccion["direccion"][:200] or pedido.direccion
    pedido.codigo_postal = direccion["codigo_postal"][:10] or pedido.codigo_postal
    pedido.localidad = direccion["localidad"][:100] or pedido.localidad
    pedido.provincia = direccion["provincia"][:100] or pedido.provincia
    pedido.ultima_sync_tn = datetime.utcnow()

    if creado or pedido.estado == "Cargando Pedido":
        pedido.estado = estado_sugerido

    notas = []
    if observacion_apb:
        notas.append(observacion_apb)
    if order.get("note"):
        notas.append(f"Nota cliente TN: {order.get('note')}")
    if order.get("owner_note"):
        notas.append(f"Nota interna TN: {order.get('owner_note')}")
    if notas:
        pedido.observaciones = " ".join(notas)[:300]

    tn_guardar_items(pedido, order)
    return pedido, "creado" if creado else "actualizado"


def tn_importar_pedido_por_id(order_id):
    order = tn_enriquecer_order_con_fulfillment(order_id)
    pedido, accion = tn_importar_o_actualizar_pedido(order)
    db.session.commit()
    return pedido, accion


def tn_sync_manual(limit=50):
    limit = max(1, min(int(limit or 50), 100))
    orders = tn_http_json("GET", "/orders", params={"per_page": limit})
    if not isinstance(orders, list):
        orders = []

    resultado = {"leidos": len(orders), "creados": 0, "actualizados": 0, "omitidos": 0}
    for order in orders:
        order_id = str(order.get("id") or "").strip() if isinstance(order, dict) else ""
        if order_id:
            try:
                order = tn_enriquecer_order_con_fulfillment(order_id)
            except Exception as e:
                print(f"[TN] Sync manual: no se pudo enriquecer orden {order_id}: {e}")
        _, accion = tn_importar_o_actualizar_pedido(order)
        if accion == "creado":
            resultado["creados"] += 1
        elif accion == "actualizado":
            resultado["actualizados"] += 1
        else:
            resultado["omitidos"] += 1

    cuenta = cuenta_tn_actual()
    if cuenta:
        cuenta.store_id = tn_store_id()
        cuenta.estado_conexion = "configurada"
        cuenta.last_sync_at = datetime.utcnow()
        cuenta.last_sync_status = "ok"
        cuenta.last_sync_detail = json.dumps(resultado, ensure_ascii=False)
    db.session.commit()
    return resultado


def tn_registrar_webhooks_sistema_fierro():
    webhook_url = request.url_root.rstrip("/") + "/webhook/tiendanube"
    eventos = ["order/created", "order/paid", "order/cancelled", "order/fulfilled", "fulfillment_order/status_updated", "fulfillment_order/tracking_event_created", "fulfillment_order/tracking_event_updated"]
    resultados = []

    for evento in eventos:
        try:
            respuesta = tn_http_json("POST", "/webhooks", data={"event": evento, "url": webhook_url})
            resultados.append({"event": evento, "ok": True, "detalle": respuesta})
        except Exception as e:
            resultados.append({"event": evento, "ok": False, "detalle": str(e)})

    cuenta = cuenta_tn_actual()
    if cuenta:
        cuenta.store_id = tn_store_id()
        cuenta.last_sync_at = datetime.utcnow()
        cuenta.last_sync_status = "webhooks_configurados"
        cuenta.last_sync_detail = json.dumps(resultados, ensure_ascii=False)[:1000]
        db.session.commit()

    return resultados


def cuenta_ml_actual():
    return MercadoLibreCuenta.query.order_by(MercadoLibreCuenta.id.asc()).first()


def ml_client_id():
    return (os.getenv("MELI_CLIENT_ID") or "").strip()


def ml_client_secret():
    return (os.getenv("MELI_CLIENT_SECRET") or "").strip()


def ml_redirect_uri():
    return (os.getenv("MELI_REDIRECT_URI") or "").strip()


def ml_config_faltante():
    faltantes = []
    if not ml_client_id():
        faltantes.append("MELI_CLIENT_ID")
    if not ml_client_secret():
        faltantes.append("MELI_CLIENT_SECRET")
    if not ml_redirect_uri():
        faltantes.append("MELI_REDIRECT_URI")
    return faltantes


def ml_token_vencido(cuenta):
    if not cuenta or not cuenta.token_expires_at:
        return True
    return cuenta.token_expires_at <= datetime.utcnow() + timedelta(minutes=2)


def ml_http_json(method, url, data=None, headers=None):
    headers = headers or {}
    body = None

    if data is not None:
        encoded = urlencode(data).encode("utf-8")
        body = encoded
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

    req = Request(url, data=body, method=method.upper())
    headers.setdefault("Accept", "application/json")

    for key, value in headers.items():
        req.add_header(key, value)

    try:
        with urlopen(req, timeout=10) as response:
            raw = response.read().decode("utf-8")
            if not raw.strip():
                return {}
            return json.loads(raw)
    except HTTPError as e:
        body_error = e.read().decode("utf-8", errors="ignore")
        raise ValueError(f"ML API {e.code}: {body_error[:200]}")
    except URLError as e:
        raise ValueError(f"ML conexión fallida: {e.reason}")

def ml_exchange_code_for_token(code):
    payload = {
        "grant_type": "authorization_code",
        "client_id": ml_client_id(),
        "client_secret": ml_client_secret(),
        "code": code,
        "redirect_uri": ml_redirect_uri(),
    }
    return ml_http_json("POST", "https://api.mercadolibre.com/oauth/token", data=payload)


def ml_refresh_access_token(cuenta):
    if not cuenta or not cuenta.refresh_token:
        raise ValueError("La cuenta de Mercado Libre no tiene refresh token guardado.")

    payload = {
        "grant_type": "refresh_token",
        "client_id": ml_client_id(),
        "client_secret": ml_client_secret(),
        "refresh_token": cuenta.refresh_token,
    }
    token_data = ml_http_json("POST", "https://api.mercadolibre.com/oauth/token", data=payload)
    ml_guardar_token_en_cuenta(cuenta, token_data)
    return cuenta


def ml_guardar_token_en_cuenta(cuenta, token_data):
    cuenta.access_token = token_data.get("access_token") or cuenta.access_token
    cuenta.refresh_token = token_data.get("refresh_token") or cuenta.refresh_token
    expires_in = int(token_data.get("expires_in") or 0)
    if expires_in > 0:
        cuenta.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    cuenta.scope = token_data.get("scope") or cuenta.scope
    cuenta.estado_conexion = "conectada" if cuenta.access_token else "error"


def ml_access_token_vigente():
    cuenta = cuenta_ml_actual()
    if not cuenta:
        raise ValueError("No hay una cuenta de Mercado Libre conectada.")

    if ml_token_vencido(cuenta):
        cuenta = ml_refresh_access_token(cuenta)
        db.session.commit()

    if not cuenta.access_token:
        raise ValueError("La cuenta conectada no tiene access token válido.")

    return cuenta.access_token


def ml_api_get(path, params=None):
    token = ml_access_token_vigente()
    params = params or {}
    query = urlencode(params)
    url = f"https://api.mercadolibre.com{path}"
    if query:
        url = f"{url}?{query}"
    return ml_http_json("GET", url, headers={"Authorization": f"Bearer {token}"})



def ml_api_post_json(path, payload=None):
    token = ml_access_token_vigente()
    url = f"https://api.mercadolibre.com{path}"
    data = json.dumps(payload or {}).encode("utf-8")

    req = Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    try:
        with urlopen(req) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except HTTPError as e:
        detalle = e.read().decode("utf-8", errors="ignore")
        raise ValueError(f"Mercado Libre rechazó el mensaje: {detalle or e}")


def ml_api_get_binario(path, params=None, accept="application/pdf"):
    token = ml_access_token_vigente()
    params = params or {}
    query = urlencode(params)
    url = f"https://api.mercadolibre.com{path}"
    if query:
        url = f"{url}?{query}"

    req = Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", accept)

    with urlopen(req) as response:
        contenido = response.read()
        content_type = response.headers.get("Content-Type", "")
        return contenido, content_type


def ml_guardar_etiqueta_pdf(shipping_id):
    shipping_id = str(shipping_id or "").strip()
    if not shipping_id:
        return None

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    nombre_archivo = secure_filename(f"ml_{shipping_id}.pdf")
    ruta_pdf = os.path.join(app.config["UPLOAD_FOLDER"], nombre_archivo)

    if os.path.exists(ruta_pdf) and os.path.getsize(ruta_pdf) > 0:
        return nombre_archivo

    intentos = [
        {"shipment_ids": shipping_id, "response_type": "pdf"},
        {"shipment_ids": shipping_id},
    ]

    for params in intentos:
        try:
            contenido, content_type = ml_api_get_binario(
                "/shipment_labels",
                params=params,
                accept="application/pdf",
            )

            if contenido and (contenido[:4] == b"%PDF" or "pdf" in str(content_type).lower()):
                with open(ruta_pdf, "wb") as salida:
                    salida.write(contenido)

                if os.path.exists(ruta_pdf) and os.path.getsize(ruta_pdf) > 0:
                    return nombre_archivo

            try:
                data = json.loads(contenido.decode("utf-8"))
                results = data.get("results") or []
                if results and results[0].get("url"):
                    nombre_descargado = asegurar_pdf_local_desde_url(results[0].get("url"), prefijo="ml")
                    if nombre_descargado:
                        return os.path.basename(str(nombre_descargado))
            except Exception:
                pass

        except Exception as e:
            print("No se pudo descargar etiqueta ML:", e)

    return None


def ml_obtener_usuario_actual():
    return ml_api_get("/users/me")


def ml_obtener_orders_recientes(cuenta, limit=None, horas=48, max_paginas=20):
    """
    Trae órdenes operativas recientes de ML con paginación por ventana de tiempo.
    Evita depender de un límite fijo que puede quedar tapado por ventas Full/omitidas.
    """
    if not cuenta or not cuenta.user_id_ml:
        raise ValueError("La cuenta de Mercado Libre no tiene user_id asociado.")

    hasta = datetime.utcnow()
    desde = hasta - timedelta(hours=horas)
    limit = 50
    offset = 0
    orders = []

    for _ in range(max_paginas):
        data = ml_api_get(
            "/orders/search",
            params={
                "seller": cuenta.user_id_ml,
                "sort": "date_desc",
                "limit": limit,
                "offset": offset,
                "order.date_created.from": desde.strftime("%Y-%m-%dT%H:%M:%S.000-00:00"),
                "order.date_created.to": hasta.strftime("%Y-%m-%dT%H:%M:%S.999-00:00"),
            },
        )

        resultados = data.get("results") or []
        if not resultados:
            break

        orders.extend(resultados)

        paging = data.get("paging") or {}
        total = int(paging.get("total") or 0)
        offset += limit
        if offset >= total:
            break

    return orders

def ml_obtener_order(order_id):
    order_id = str(order_id or "").strip()
    if not order_id:
        return {}
    try:
        return ml_api_get(f"/orders/{order_id}")
    except Exception as e:
        print("No se pudo consultar order ML:", e)
        return {}



def ml_obtener_shipment(shipping_id):
    if not shipping_id:
        return {}

    try:
        return ml_api_get(f"/shipments/{shipping_id}")
    except Exception as e:
        print("No se pudo consultar shipment ML:", e)
        return {}


def ml_obtener_billing_info(order_id):
    order_id = str(order_id or "").strip()
    if not order_id:
        return {}

    try:
        token = ml_access_token_vigente()
        url = f"https://api.mercadolibre.com/orders/{order_id}/billing_info"
        req = Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/json")
        req.add_header("x-version", "2")

        with urlopen(req) as response:
            raw = response.read().decode("utf-8")
            if not raw.strip():
                return {}
            return json.loads(raw)
    except Exception as e:
        print("No se pudo consultar billing_info ML:", e)
        return {}


def buscar_valor_recursivo(data, claves):
    if not isinstance(claves, (list, tuple, set)):
        claves = [claves]

    claves_normalizadas = {str(c).lower().strip() for c in claves}

    if isinstance(data, dict):
        for key, value in data.items():
            if str(key).lower().strip() in claves_normalizadas and value not in [None, ""]:
                return value

        for value in data.values():
            encontrado = buscar_valor_recursivo(value, claves_normalizadas)
            if encontrado not in [None, ""]:
                return encontrado

    if isinstance(data, list):
        for item in data:
            encontrado = buscar_valor_recursivo(item, claves_normalizadas)
            if encontrado not in [None, ""]:
                return encontrado

    return ""


def ml_billing_base(billing_info):
    """Devuelve el bloque real buyer.billing_info cuando ML responde V2."""
    if not isinstance(billing_info, dict):
        return {}

    buyer = billing_info.get("buyer") or {}
    if isinstance(buyer, dict):
        info = buyer.get("billing_info") or {}
        if isinstance(info, dict) and info:
            return info

    info = billing_info.get("billing_info") or {}
    if isinstance(info, dict) and info:
        return info

    return billing_info


def ml_billing_additional_info_map(billing_info):
    info = ml_billing_base(billing_info)
    adicionales = info.get("additional_info") or billing_info.get("additional_info") or []
    salida = {}

    if isinstance(adicionales, list):
        for item in adicionales:
            if not isinstance(item, dict):
                continue
            tipo = str(item.get("type") or item.get("key") or item.get("name") or "").lower().strip()
            valor = item.get("value")
            if tipo and valor not in [None, ""]:
                salida[tipo] = valor

    return salida


def ml_extraer_documento_billing(billing_info):
    info = ml_billing_base(billing_info)
    adicionales = ml_billing_additional_info_map(billing_info)

    identificacion = info.get("identification") or {}
    atributos = info.get("attributes") or {}

    candidatos = [
        identificacion.get("number") if isinstance(identificacion, dict) else "",
        adicionales.get("doc_number"),
        adicionales.get("secondary_doc_number"),
        atributos.get("doc_type_number") if isinstance(atributos, dict) else "",
        info.get("doc_number"),
        info.get("document_number"),
        info.get("dni"),
        info.get("cuit"),
        buscar_valor_recursivo(info.get("identification") or {}, ["number"]),
    ]

    for candidato in candidatos:
        valor = re.sub(r"\D", "", str(candidato or ""))
        if valor and valor not in ["0", "00", "00000000", "000000000", "0000000000", "00000000000"]:
            return valor

    return ""


def ml_extraer_nombre_billing(billing_info):
    info = ml_billing_base(billing_info)
    adicionales = ml_billing_additional_info_map(billing_info)

    business_name = str(info.get("business_name") or adicionales.get("business_name") or "").strip()
    if business_name:
        return business_name

    nombre = str(info.get("name") or adicionales.get("first_name") or "").strip()
    apellido = str(info.get("last_name") or adicionales.get("last_name") or "").strip()
    nombre_completo = f"{nombre} {apellido}".strip()
    if nombre_completo and not nombre_completo.isdigit():
        return nombre_completo

    for clave in ["full_name", "legal_name"]:
        valor = str(info.get(clave) or adicionales.get(clave) or "").strip()
        if valor and not valor.isdigit():
            return valor

    return ""


def ml_extraer_direccion_billing(billing_info):
    info = ml_billing_base(billing_info)
    adicionales = ml_billing_additional_info_map(billing_info)

    address = info.get("address") or {}
    if not isinstance(address, dict):
        address = {}

    estado = address.get("state") or {}
    if not isinstance(estado, dict):
        estado = {}

    calle = str(address.get("street_name") or adicionales.get("street_name") or "").strip()
    numero = str(address.get("street_number") or adicionales.get("street_number") or "").strip()
    comentario = str(address.get("comment") or adicionales.get("comment") or "").strip()
    ciudad = str(address.get("city_name") or adicionales.get("city_name") or "").strip()
    provincia = str(estado.get("name") or address.get("state_name") or adicionales.get("state_name") or "").strip()
    cp = str(address.get("zip_code") or adicionales.get("zip_code") or "").strip()

    direccion = ""
    if calle and numero:
        direccion = f"{calle} {numero}".strip()
    elif calle:
        direccion = calle

    partes = [direccion, comentario, ciudad, provincia, cp]
    salida = []
    for valor in partes:
        valor = str(valor or "").strip()
        if valor and valor not in salida:
            salida.append(valor)

    return ", ".join(salida).strip()


def ml_extraer_telefono(order, shipment):
    buyer = order.get("buyer") or {}
    phone = buyer.get("phone") or {}
    receiver_address = (shipment or {}).get("receiver_address") or {}

    candidatos = []
    area = str(phone.get("area_code") or "").strip()
    number = str(phone.get("number") or "").strip()
    if area or number:
        candidatos.append(f"{area}{number}")

    candidatos.extend([
        phone.get("extension"),
        receiver_address.get("receiver_phone"),
        receiver_address.get("phone"),
        shipment.get("receiver_phone") if isinstance(shipment, dict) else "",
    ])

    for candidato in candidatos:
        normalizado = normalizar_telefono(candidato)
        digitos = re.sub(r"\D", "", normalizado or "")
        if digitos and digitos not in ["5490", "54900", "54900000000", "5490000000000"] and len(digitos) >= 10:
            return normalizado

    return ""


def ml_buyer_tiene_nombre_real(order):
    buyer = order.get("buyer") or {}
    first = str(buyer.get("first_name") or "").strip()
    last = str(buyer.get("last_name") or "").strip()
    return bool(first and last)


def parece_nickname_ml(nombre, nickname=""):
    nombre = str(nombre or "").strip()
    nickname = str(nickname or "").strip()

    if not nombre:
        return True

    if nombre.lower() in ["cliente mercado libre", "cliente ml", "mercado libre"]:
        return True

    if nickname and nombre.lower() == nickname.lower():
        return True

    if " " not in nombre and re.search(r"\d", nombre):
        return True

    if " " not in nombre and nombre.upper() == nombre and len(nombre) >= 5:
        return True

    return False


def ml_datos_apb_pedido(pedido):
    faltantes = []

    if not pedido:
        return faltantes

    if es_ml_acordas_entrega(pedido):
        if parece_nickname_ml(pedido.cliente, pedido.ml_buyer_nickname) and not (pedido.ml_billing_nombre or "").strip():
            faltantes.append("nombre real")

        if not (pedido.dni or "").strip() and not (pedido.ml_billing_documento or "").strip():
            faltantes.append("DNI/CUIT")

        if not (pedido.telefono or "").strip():
            faltantes.append("teléfono")

        if not despacho_completo(pedido):
            faltantes.append("datos de entrega")

    return faltantes


def pedido_es_plegable_pp6040(pedido):
    """Detecta parrilla plegable para usar mensaje neutro ML Acordas."""
    if not pedido:
        return False

    for item in (pedido.items or []):
        sku = str(getattr(item, "sku", "") or "").upper()
        descripcion = str(getattr(item, "descripcion", "") or "").upper()
        if "PP6040" in sku or "PP6040" in descripcion or "PLEGABLE" in descripcion:
            return True

    return False

def generar_mensaje_contacto_ml(pedido):
    if not pedido or not es_ml_acordas_entrega(pedido):
        return ""

    if pedido_es_plegable_pp6040(pedido):
        texto = (
            "Hola! Desde Fierro 100% Argento agradecemos tu compra.\n\n"
            "Tenes envio gratis, pero necesitamos coordinar para que llegue correctamente a destino.\n\n"
            "Por favor confirmanos:\n"
            "- Nombre completo de quien recibe\n"
            "- Documento\n"
            "- Direccion\n"
            "- Telefono de contacto\n\n"
            "Gracias! Quedamos atentos para continuar con el despacho."
        )
    else:
        texto = (
            "Hola! Desde Fierro 100% Argento agradecemos tu compra.\n\n"
            "Tu pedido tiene envio sin cargo con retiro en sucursal Via Cargo. Para coordinar correctamente, necesitamos que nos confirmes:\n\n"
            "- Nombre completo\n"
            "- Documento\n"
            "- Direccion\n"
            "- Telefono\n\n"
            "Con esto verificamos la sucursal mas cercana a tu domicilio.\n\n"
            "Gracias! Quedamos atentos."
        )

    if len(texto) > 348:
        texto = texto[:345] + "..."

    return texto


def ml_aplicar_apb_en_pedido(pedido, order, shipment, billing_info=None):
    buyer = order.get("buyer") or {}
    billing_info = billing_info or {}

    pedido.ml_buyer_id = str(buyer.get("id") or pedido.ml_buyer_id or "").strip()
    pedido.ml_buyer_nickname = str(buyer.get("nickname") or pedido.ml_buyer_nickname or "").strip()

    nombre_ml = ml_nombre_cliente(order, shipment)
    nombre_billing = ml_extraer_nombre_billing(billing_info)
    documento_billing = ml_extraer_documento_billing(billing_info)
    direccion_billing = ml_extraer_direccion_billing(billing_info)
    telefono_ml = ml_extraer_telefono(order, shipment)

    pedido.ml_nombre_real = bool(ml_buyer_tiene_nombre_real(order) or (nombre_ml and not parece_nickname_ml(nombre_ml, pedido.ml_buyer_nickname)))
    pedido.ml_datos_fiscales_ok = bool(documento_billing or nombre_billing)
    pedido.ml_billing_nombre = nombre_billing or pedido.ml_billing_nombre
    pedido.ml_billing_documento = documento_billing or pedido.ml_billing_documento
    pedido.ml_billing_direccion = direccion_billing or pedido.ml_billing_direccion

    if nombre_ml and not parece_nickname_ml(nombre_ml, pedido.ml_buyer_nickname):
        pedido.cliente = nombre_ml
    elif nombre_billing and parece_nickname_ml(pedido.cliente, pedido.ml_buyer_nickname):
        pedido.cliente = nombre_billing

    if documento_billing and not (pedido.dni or "").strip():
        pedido.dni = documento_billing

    if telefono_ml and not (pedido.telefono or "").strip():
        pedido.telefono = telefono_ml

    faltantes = ml_datos_apb_pedido(pedido)
    pedido.ml_campos_faltantes = ", ".join(faltantes)
    pedido.ml_mensaje_contacto = generar_mensaje_contacto_ml(pedido) if faltantes else ""



def es_andreani_pedido(pedido):
    transporte = str(getattr(pedido, "empresa_envio", "") or "").strip().lower()
    return "andreani" in transporte


def es_via_cargo_pedido(pedido):
    transporte = str(getattr(pedido, "empresa_envio", "") or "").strip().lower()
    return "vía cargo" in transporte or "via cargo" in transporte


def es_correo_argentino_pedido(pedido):
    transporte = str(getattr(pedido, "empresa_envio", "") or "").strip().lower()
    tipo_ml = str(getattr(pedido, "ml_tipo", "") or "").strip().lower()
    return "correo" in transporte or "mercado envios" in tipo_ml or "mercado envíos" in tipo_ml


def puede_actualizar_tracking_externo(pedido):
    if not pedido or rol_actual() not in ["admin", "carga"]:
        return False
    seguimiento = str(getattr(pedido, "seguimiento", None) or getattr(pedido, "tn_tracking_number", None) or "").strip()
    if not seguimiento:
        return False
    if pedido.estado in ["Finalizado"]:
        return False
    return es_andreani_pedido(pedido) or es_via_cargo_pedido(pedido) or es_correo_argentino_pedido(pedido)


def aplicar_estado_tracking_seguro(pedido, clasificacion):
    return aplicar_estado_tracking_seguro_service(pedido, clasificacion)


def andreani_eventos_pedido(pedido):
    raw = str(getattr(pedido, "andreani_eventos_json", "") or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            eventos = data.get("eventos") or []
        else:
            eventos = data
        return eventos if isinstance(eventos, list) else []
    except Exception:
        return []


def andreani_ultimo_evento_pedido(pedido):
    eventos = andreani_eventos_pedido(pedido)
    eventos_validos = [e for e in eventos if isinstance(e, dict)]
    if not eventos_validos:
        return None
    def clave(ev):
        return str(ev.get("Fecha") or ev.get("fecha") or ev.get("fechaEstado") or "")
    return sorted(eventos_validos, key=clave)[-1]


def andreani_texto_ultimo_evento(pedido):
    evento = andreani_ultimo_evento_pedido(pedido)
    if not evento:
        return ""
    return resumen_evento_andreani(evento)


def andreani_fecha_ultimo_evento(pedido):
    evento = andreani_ultimo_evento_pedido(pedido)
    if not isinstance(evento, dict):
        return None
    valor = str(evento.get("Fecha") or evento.get("fecha") or evento.get("fechaEstado") or "").strip()
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00").replace("+00:00", ""))
    except Exception:
        return None


def andreani_alerta_pedido(pedido):
    if not pedido or not es_andreani_pedido(pedido):
        return None
    texto = " ".join([
        str(getattr(pedido, "andreani_estado", "") or ""),
        andreani_texto_ultimo_evento(pedido),
    ]).lower()
    if any(x in texto for x in ["no entreg", "fallid", "rechaz", "devol", "incid", "siniestr"]):
        return {"tipo": "roja", "texto": "Andreani informa incidencia/no entrega. Revisar y gestionar."}
    if "entreg" in texto and "no entreg" not in texto:
        return {"tipo": "verde", "texto": "Andreani informa entregado. Confirmar y marcar Entregado si corresponde."}
    fecha = andreani_fecha_ultimo_evento(pedido) or getattr(pedido, "andreani_ultima_sync", None)
    if fecha:
        horas = (datetime.utcnow() - fecha).total_seconds() / 3600
        if horas >= 96:
            return {"tipo": "roja", "texto": "Andreani sin movimientos recientes hace más de 96 hs."}
        if horas >= 72:
            return {"tipo": "amarilla", "texto": "Andreani sin movimientos recientes hace más de 72 hs."}
    return None

def tracking_info_pedido(pedido):
    return tracking_info_pedido_service(
        pedido
    )


def ml_link_detalle_venta(pedido):
    if not pedido or pedido.canal != "Mercado Libre" or not pedido.id_venta:
        return ""
    return f"https://www.mercadolibre.com.ar/ventas/{pedido.id_venta}/detalle"


def ml_link_chat_venta(pedido):
    if not pedido or pedido.canal != "Mercado Libre":
        return ""

    # El chat de ML puede requerir pack_id en lugar del ID de venta.
    # El detalle de venta sigue usando id_venta; la mensajeria usa ml_pack_id con fallback a id_venta.
    id_chat = str(getattr(pedido, "ml_pack_id", None) or getattr(pedido, "id_venta", None) or "").strip()
    if not id_chat:
        return ""

    return (
        f"https://www.mercadolibre.com.ar/ventas/nueva/mensajeria/{id_chat}"
        "?source=ml&callbackWording=Ventas"
        "&callbackUrl=https%3A%2F%2Fwww.mercadolibre.com.ar%2Fventas%2Fomni%2Flistado"
    )


def ml_extraer_ids_mensaje_ml(obj):
    """
    Extrae IDs relacionados a mensajes ML de forma robusta.
    Contempla pack_id, order_id, recursos /packs/{id}/orders/{id}
    y el formato frecuente de ML message_resources: [{id, name: packs/orders}].
    """
    ids = set()

    def agregar(valor):
        valor = str(valor or "").strip()
        if not valor:
            return
        if re.fullmatch(r"\d{8,}", valor):
            ids.add(valor)

    def recorrer(valor, clave=""):
        clave_l = str(clave or "").lower()

        if isinstance(valor, dict):
            nombre_recurso = str(
                valor.get("name")
                or valor.get("resource")
                or valor.get("resource_type")
                or valor.get("type")
                or ""
            ).lower()
            id_recurso = valor.get("id") or valor.get("resource_id") or valor.get("pack_id") or valor.get("order_id")
            if any(x in nombre_recurso for x in ["pack", "order"]):
                agregar(id_recurso)

            for k, v in valor.items():
                recorrer(v, k)
            return

        if isinstance(valor, list):
            for v in valor:
                recorrer(v, clave_l)
            return

        texto = str(valor or "").strip()
        if not texto:
            return

        if any(x in clave_l for x in ["pack", "order"]):
            agregar(texto)

        for patron in [
            r"/packs/([^/?#]+)",
            r"/orders/([^/?#]+)",
            r"pack_id[=:]([^&/?#]+)",
            r"order_id[=:]([^&/?#]+)",
        ]:
            for match in re.finditer(patron, texto):
                agregar(match.group(1))

    recorrer(obj)
    return ids


def ml_marcar_mensajes_pendientes_por_ids(ids, count=1, commit=False):
    """Marca pedidos con mensajes pendientes usando id_venta o ml_pack_id."""
    ids_limpios = {str(x or "").strip() for x in (ids or []) if str(x or "").strip()}
    if not ids_limpios:
        return 0

    pedidos = Pedido.query.filter(Pedido.canal == "Mercado Libre").all()
    ahora = datetime.utcnow()
    marcados = 0

    for pedido in pedidos:
        ids_pedido = {
            str(getattr(pedido, "id_venta", "") or "").strip(),
            str(getattr(pedido, "ml_pack_id", "") or "").strip(),
        }
        ids_pedido.discard("")

        if ids_pedido.intersection(ids_limpios):
            pedido.ml_mensajes_pendientes = True
            pedido.ml_mensajes_pendientes_count = max(int(pedido.ml_mensajes_pendientes_count or 0), int(count or 1))
            pedido.ultima_sync_mensajes_ml = ahora
            marcados += 1

    if commit and marcados:
        db.session.commit()

    return marcados


def ml_resolver_ids_desde_recurso_mensaje(resource):
    """Intenta resolver pack/order IDs desde el recurso de mensaje que manda ML."""
    resource = str(resource or "").strip()
    if not resource:
        return set()

    ids = ml_extraer_ids_mensaje_ml({"resource": resource})
    if ids:
        return ids

    if not resource.startswith("/"):
        return set()

    intentos = [(resource, {})]
    # En algunas cuentas, el detalle del mensaje postventa necesita tag=post_sale.
    if "/messages" in resource:
        intentos.append((resource, {"tag": "post_sale"}))
        intentos.append((resource, {"role": "seller", "tag": "post_sale"}))

    for path, params in intentos:
        try:
            detalle = ml_api_get(path, params=params)
            ids = ml_extraer_ids_mensaje_ml(detalle)
            print("[ML-MENSAJE-DETALLE] resource=", path, params, "ids=", sorted(ids))
            if ids:
                return ids
        except Exception as e:
            print("[ML-MENSAJE-DETALLE] No se pudo resolver", path, params, e)

    return set()


def ml_obtener_ids_mensajes_pendientes():
    """
    Obtiene IDs con mensajes pendientes sin abrir el chat del pedido.
    Usa varios endpoints/formas porque ML cambia la estructura según flujo/cuenta.
    """
    pendientes_por_id = {}

    endpoints = [
        ("/messages/unread", {"role": "seller"}),
        ("/messages/unread", {"role": "seller", "tag": "post_sale"}),
        ("/messages/search", {"role": "seller", "limit": 50}),
    ]

    for path, params in endpoints:
        try:
            data = ml_api_get(path, params=params)
            print(f"[ML-MENSAJES] OK {path} {params}")
        except Exception as e:
            print(f"[ML-MENSAJES] No se pudo consultar {path} {params}: {e}")
            continue

        resultados = (data or {}).get("results") if isinstance(data, dict) else data
        if isinstance(resultados, dict):
            resultados = resultados.get("results") or resultados.get("items") or []
        if not isinstance(resultados, list):
            resultados = []

        for item in resultados:
            # En search puede venir status/read distinto. Si hay status y NO es unread, salteamos.
            estado_msg = str((item or {}).get("status") or (item or {}).get("message_status") or "").lower()
            if estado_msg and estado_msg not in {"unread", "new", "pending"}:
                continue

            try:
                count = int((item or {}).get("count") or (item or {}).get("unread") or 1)
            except Exception:
                count = 1
            if count <= 0:
                continue

            ids_item = ml_extraer_ids_mensaje_ml(item)

            # Si ML solo devuelve resource del mensaje, resolvemos el detalle puntual.
            if not ids_item:
                resource = (item or {}).get("resource") or (item or {}).get("message_id") or ""
                if resource and str(resource).startswith("/messages"):
                    ids_item = ml_resolver_ids_desde_recurso_mensaje(resource)

            for id_ref in ids_item:
                pendientes_por_id[id_ref] = max(int(pendientes_por_id.get(id_ref) or 0), count)

    return pendientes_por_id


def ml_extraer_lista_mensajes_ml(data):
    """Extrae mensajes desde varias estructuras posibles de la API de ML."""
    mensajes = []

    def caminar(valor):
        if isinstance(valor, dict):
            for clave in ("messages", "results", "items"):
                posible = valor.get(clave)
                if isinstance(posible, list):
                    for item in posible:
                        if isinstance(item, dict) and (
                            "from" in item or "sender" in item or "text" in item or "message" in item or "status" in item
                        ):
                            mensajes.append(item)
            for v in valor.values():
                caminar(v)
        elif isinstance(valor, list):
            for v in valor:
                caminar(v)

    caminar(data)

    unicos = []
    vistos = set()
    for m in mensajes:
        mid = str(m.get("id") or m.get("message_id") or "").strip()
        clave = mid or str(m)[:300]
        if clave in vistos:
            continue
        vistos.add(clave)
        unicos.append(m)
    return unicos


def ml_mensaje_es_del_comprador(m, seller_id=""):
    """Determina si un mensaje vino del comprador."""
    if not isinstance(m, dict):
        return False

    from_data = m.get("from") or m.get("sender") or m.get("user") or {}
    if not isinstance(from_data, dict):
        from_data = {}

    user_type = str(
        from_data.get("user_type")
        or from_data.get("role")
        or from_data.get("type")
        or m.get("from_user_type")
        or ""
    ).lower().strip()

    if user_type in {"buyer", "comprador"}:
        return True
    if user_type in {"seller", "vendedor", "operator", "admin"}:
        return False

    sender_id = str(
        from_data.get("id")
        or from_data.get("user_id")
        or m.get("from_id")
        or ""
    ).strip()

    return bool(sender_id and seller_id and sender_id != str(seller_id))


def ml_mensaje_es_del_vendedor(m, seller_id=""):
    """Determina si un mensaje vino del vendedor/cuenta Fierro."""
    if not isinstance(m, dict):
        return False
    seller_id = str(seller_id or "").strip()
    posibles_from = [m.get("from"), m.get("sender"), m.get("author")]
    for f in posibles_from:
        if isinstance(f, dict):
            user_type = str(f.get("user_type") or f.get("type") or f.get("role") or "").lower()
            if user_type in {"seller", "vendor"}:
                return True
            fid = str(f.get("id") or f.get("user_id") or "").strip()
            if seller_id and fid and fid == seller_id:
                return True
    for key in ["from_user_id", "sender_id", "user_id"]:
        val = str(m.get(key) or "").strip()
        if seller_id and val and val == seller_id:
            return True
    return False


def ml_mensaje_esta_pendiente(m):
    """Detecta si el mensaje requiere atención sin marcarlo como leído."""
    if not isinstance(m, dict):
        return False

    status = str(
        m.get("status")
        or m.get("message_status")
        or m.get("read_status")
        or ""
    ).lower().strip()

    if status in {"unread", "new", "pending", "not_read", "unanswered"}:
        return True
    if status in {"read", "answered", "closed"}:
        return False

    for clave in ("read", "is_read", "answered", "is_answered"):
        if clave in m:
            valor = m.get(clave)
            if clave in {"read", "is_read"} and valor is False:
                return True
            if clave in {"answered", "is_answered"} and valor is False:
                return True

    date_data = m.get("message_date") or m.get("date") or {}
    if isinstance(date_data, dict) and "read" in date_data and not date_data.get("read"):
        return True

    return False



def ml_fecha_mensaje_valor(m):
    """Devuelve una fecha comparable del mensaje ML si existe."""
    if not isinstance(m, dict):
        return ""
    candidatos = [m.get("date_created"), m.get("created_at"), m.get("date"), m.get("message_date")]
    for c in candidatos:
        if isinstance(c, dict):
            for k in ("created", "date", "sent", "received", "read"):
                if c.get(k):
                    return str(c.get(k))
        elif c:
            return str(c)
    return ""


def ml_texto_mensaje_ml(m):
    """Extrae texto visible de un mensaje ML sin marcarlo como leído."""
    if not isinstance(m, dict):
        return ""

    candidatos = [
        m.get("text"),
        m.get("message"),
        m.get("body"),
        m.get("plain"),
        m.get("content"),
    ]

    for valor in candidatos:
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
        if isinstance(valor, dict):
            for key in ["plain", "text", "message", "body", "content"]:
                sub = valor.get(key)
                if isinstance(sub, str) and sub.strip():
                    return sub.strip()

    attachments = m.get("attachments") or []
    if attachments:
        return "[El comprador envió un adjunto o imagen]"

    return ""


def ml_ultimo_mensaje_comprador(mensajes, seller_id=""):
    """Devuelve el último mensaje de comprador con texto útil."""
    if not mensajes:
        return None
    candidatos = [
        m for m in mensajes
        if ml_mensaje_es_del_comprador(m, seller_id=seller_id) and ml_texto_mensaje_ml(m)
    ]
    if not candidatos:
        return None
    try:
        candidatos.sort(key=ml_fecha_mensaje_valor)
    except Exception:
        pass
    return candidatos[-1]


def ia_hash_texto(texto):
    return hashlib.sha256(str(texto or "").encode("utf-8", errors="ignore")).hexdigest()

def ia_extraer_codigo_postal_simple(texto):
    """
    APB anti-loop:
    Detecta CP escrito de forma simple por el comprador.
    Ejemplos válidos:
    - 3500
    - CP 3500
    - Código postal 3500
    - codigo postal: 3500
    """
    texto = str(texto or "").strip()

    if not texto:
        return ""

    patrones = [
        r"\b(?:cp|c\.p\.|codigo postal|código postal|cod postal|cód postal)\s*[:\-]?\s*(\d{4})\b",
        r"^\s*(\d{4})\s*$",
        r"\bcp\s*(\d{4})\b",
    ]

    for patron in patrones:
        m = re.search(patron, texto, flags=re.IGNORECASE)

        if m:
            return m.group(1)

    return ""

ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
IA_HORA_INICIO_OPERATIVA = time(8, 0)
IA_HORA_FIN_OPERATIVA = time(22, 0)
IA_TIMEOUT_RESPUESTA_SEGUNDOS = 2 * 60 * 60


def _ia_datetime_utc(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _ia_datetime_arg(dt):
    dt_utc = _ia_datetime_utc(dt)
    return dt_utc.astimezone(ARG_TZ) if dt_utc else None


def ia_ahora_utc():
    return datetime.utcnow()


def ia_en_horario_operativo(dt=None):
    ahora_arg = _ia_datetime_arg(dt or ia_ahora_utc())
    if not ahora_arg:
        return False
    hora = ahora_arg.time()
    return IA_HORA_INICIO_OPERATIVA <= hora < IA_HORA_FIN_OPERATIVA


def ia_segundos_operativos_entre(inicio, fin=None):
    """Cuenta solo segundos entre 08:00 y 22:00 hora Argentina."""
    if not inicio:
        return 0
    fin = fin or ia_ahora_utc()
    ini_arg = _ia_datetime_arg(inicio)
    fin_arg = _ia_datetime_arg(fin)
    if not ini_arg or not fin_arg or fin_arg <= ini_arg:
        return 0

    total = 0
    cursor_fecha = ini_arg.date()
    fin_fecha = fin_arg.date()

    while cursor_fecha <= fin_fecha:
        tramo_ini = datetime.combine(cursor_fecha, IA_HORA_INICIO_OPERATIVA, tzinfo=ARG_TZ)
        tramo_fin = datetime.combine(cursor_fecha, IA_HORA_FIN_OPERATIVA, tzinfo=ARG_TZ)
        desde = max(ini_arg, tramo_ini)
        hasta = min(fin_arg, tramo_fin)
        if hasta > desde:
            total += int((hasta - desde).total_seconds())
        cursor_fecha += timedelta(days=1)

    return max(0, total)


def ia_marcar_mensaje_bot(pedido, canal, texto=None, commit=True):
    """Registra que el bot habló y debe esperar respuesta del comprador."""
    if not pedido:
        return False
    try:
        pedido.ia_esperando_respuesta = True
        pedido.ia_ultimo_mensaje_bot = ia_ahora_utc()
        pedido.ia_canal_activo = str(canal or "").strip()[:30] or None
        if texto:
            pedido.ia_respuesta_enviada_hash = ia_hash_texto(texto)
            pedido.ia_ultima_respuesta_enviada = pedido.ia_ultimo_mensaje_bot

        actualizar_estado_conversacional(
            pedido,
            owner_actual="bot",
            canal_activo=pedido.ia_canal_activo or canal,
            estado_conversacional="esperando_respuesta",
            takeover_activo=False,
            bot_pausado=False,
            ultimo_mensaje_bot=pedido.ia_ultimo_mensaje_bot,
        )

        registrar_evento_operativo(
            pedido=pedido,
            tipo_evento="bot_esperando_respuesta",
            origen="bot",
            canal=pedido.ia_canal_activo or canal or "sistema",
            owner="bot",
            estado_conversacional="esperando_respuesta",
            payload={
                "canal": pedido.ia_canal_activo,
                "ia_esperando_respuesta": pedido.ia_esperando_respuesta,
            },
            resultado="ok",
            detalle=(texto or "")[:500],
            procesado=True,
        )

        if commit:
            db.session.commit()
        return True
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print("[IA-APB] No se pudo marcar mensaje bot:", e)
        return False


def ia_marcar_respuesta_cliente(pedido, canal=None, commit=True):
    """Libera el candado porque el comprador respondió."""
    if not pedido:
        return False
    try:
        pedido.ia_esperando_respuesta = False
        pedido.ia_ultimo_mensaje_cliente = ia_ahora_utc()
        canal_respuesta = str(canal or "").strip()[:30] or None
        pedido.ia_canal_activo = None

        actualizar_estado_conversacional(
            pedido,
            canal_activo=canal_respuesta,
            estado_conversacional="recolectando_datos",
            ultimo_mensaje_cliente=pedido.ia_ultimo_mensaje_cliente,
        )

        registrar_evento_operativo(
            pedido=pedido,
            tipo_evento="cliente_respondio",
            origen="cliente",
            canal=canal_respuesta or "sistema",
            owner="bot",
            estado_conversacional="recolectando_datos",
            payload={
                "canal": canal_respuesta,
                "ia_esperando_respuesta": pedido.ia_esperando_respuesta,
            },
            resultado="ok",
            detalle="El cliente respondió y se liberó el candado de espera.",
            procesado=True,
        )

        # Si estaba escalado solo por timeout, el operador sigue viendo el caso;
        # no se borra ia_requiere_operador automaticamente para no tapar alertas reales.
        if commit:
            db.session.commit()
        return True
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print("[IA-APB] No se pudo marcar respuesta cliente:", e)
        return False


def ia_puede_enviar_automatico(pedido, canal, texto=None):
    """Candado global anti-acoso para ML y WhatsApp."""
    if not pedido:
        return True, "sin_pedido"

    canal = str(canal or "").strip().lower()
    canal_activo = str(getattr(pedido, "ia_canal_activo", "") or "").strip().lower()

    if getattr(pedido, "ia_requiere_operador", False):
        return False, "requiere_operador"

    if getattr(pedido, "ia_esperando_respuesta", False):
        if canal_activo and canal_activo != canal:
            return False, f"canal_activo_{canal_activo}"
        return False, "esperando_respuesta_cliente"

    if canal_activo and canal_activo != canal:
        return False, f"canal_activo_{canal_activo}"

    if texto:
        h = ia_hash_texto(texto)
        ultimo_hash = str(getattr(pedido, "ia_respuesta_enviada_hash", "") or "")
        ultimo_bot = getattr(pedido, "ia_ultimo_mensaje_bot", None)
        ultimo_cliente = getattr(pedido, "ia_ultimo_mensaje_cliente", None)
        if h == ultimo_hash and ultimo_bot and (not ultimo_cliente or ultimo_bot >= ultimo_cliente):
            return False, "mensaje_duplicado_sin_respuesta"

    return True, "ok"


def ia_escalar_si_timeout_operativo(pedido, canal="", motivo="Sin respuesta del comprador"):
    """Escala si pasaron 2 horas operativas desde el último mensaje del bot."""
    if not pedido or not getattr(pedido, "ia_esperando_respuesta", False):
        return False
    ultimo_bot = getattr(pedido, "ia_ultimo_mensaje_bot", None)
    if not ultimo_bot:
        return False
    if ia_segundos_operativos_entre(ultimo_bot, ia_ahora_utc()) < IA_TIMEOUT_RESPUESTA_SEGUNDOS:
        return False
    if getattr(pedido, "ia_requiere_operador", False):
        return False

    try:
        pedido.ia_requiere_operador = True
        pedido.ml_mensajes_pendientes = True
        pedido.ml_mensajes_pendientes_count = max(int(pedido.ml_mensajes_pendientes_count or 0), 1)
        pedido.ia_ultimo_timeout_operador = ia_ahora_utc()
        canal_txt = str(canal or getattr(pedido, "ia_canal_activo", "") or "bot")
        resumen = (pedido.ia_resumen or "").strip()
        marca = f"BOT: sin respuesta del comprador tras 2 hs operativas ({canal_txt})"
        if marca not in resumen:
            pedido.ia_resumen = f"{resumen} | {marca}".strip(" |")[:1000]
        try:
            pedido.wa_estado = "requiere_operador"
        except Exception:
            pass

        actualizar_estado_conversacional(
            pedido,
            owner_actual="operador",
            canal_activo=canal_txt,
            estado_conversacional="takeover_operador",
            takeover_activo=True,
            bot_pausado=True,
        )

        registrar_evento_operativo(
            pedido=pedido,
            tipo_evento="timeout_respuesta_cliente",
            origen="scheduler",
            canal=canal_txt,
            owner="operador",
            estado_conversacional="takeover_operador",
            payload={
                "motivo": motivo,
                "canal": canal_txt,
                "ia_esperando_respuesta": pedido.ia_esperando_respuesta,
                "ia_ultimo_mensaje_bot": str(ultimo_bot),
            },
            resultado="escalado_operador",
            detalle=marca,
            procesado=True,
        )

        db.session.commit()
        print(f"[IA-APB] Pedido #{pedido.id} escalado por timeout operativo canal={canal_txt}")
        return True
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print("[IA-APB] Error escalando por timeout:", e)
        return False


def ia_json_loads_seguro(texto):
    texto = str(texto or "").strip()
    if not texto:
        return {}
    try:
        return json.loads(texto)
    except Exception:
        pass
    ini = texto.find("{")
    fin = texto.rfind("}")
    if ini >= 0 and fin > ini:
        try:
            return json.loads(texto[ini:fin + 1])
        except Exception:
            return {}
    return {}


def ia_datos_previos_pedido(pedido):
    datos = {}
    if not pedido:
        return datos
    try:
        if pedido.ia_datos_detectados:
            datos.update(ia_json_loads_seguro(pedido.ia_datos_detectados))
    except Exception:
        pass

    if (pedido.cliente or "").strip() and not parece_nickname_ml(pedido.cliente, pedido.ml_buyer_nickname):
        partes = (pedido.cliente or "").strip().split()
        if len(partes) >= 1:
            datos.setdefault("nombre", partes[0])
        if len(partes) >= 2:
            datos.setdefault("apellido", " ".join(partes[1:]))
    if (pedido.dni or "").strip():
        datos.setdefault("dni", pedido.dni.strip())
    if (pedido.telefono or "").strip():
        datos.setdefault("telefono", pedido.telefono.strip())
    if (pedido.direccion or "").strip():
        datos.setdefault("direccion", pedido.direccion.strip())
    if (pedido.localidad or "").strip():
        datos.setdefault("localidad", pedido.localidad.strip())
    if (pedido.codigo_postal or "").strip():
        datos.setdefault("codigo_postal", pedido.codigo_postal.strip())
    return datos


def ia_analizar_datos_cliente_ml_acordas(texto_cliente, datos_previos=None):
    """Llama a OpenAI para extraer datos. Fase 2: NO responde al cliente."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {
            "ok": False,
            "error": "OPENAI_API_KEY no está configurada",
            "estado": "sin_configurar",
        }

    modelo = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    datos_previos = datos_previos or {}
    campos = ["nombre", "apellido", "dni", "telefono", "direccion", "localidad", "codigo_postal"]
    campos_autorizado = ["autorizado_nombre", "autorizado_dni", "autorizado_telefono"]

    prompt = '''
Sos el recolector de datos de Fierro 100% Argento para pedidos de Mercado Libre / Acordás la Entrega.

OBJETIVO PRINCIPAL:
Analizar la respuesta del comprador, extraer datos para coordinar el envío y clasificar la intención del mensaje.
No inventes datos. Si no estás seguro, dejá el campo vacío y ponelo como faltante.

DATOS OBLIGATORIOS DEL COMPRADOR / TITULAR:
- nombre
- apellido
- dni
- telefono
- direccion
- localidad
- codigo_postal

DATOS DE AUTORIZADO / QUIEN RECIBE O RETIRA:
Si el comprador dice que recibe, retira, está autorizado, se entrega a otra persona, o usa frases como "quien recibe", "quien retira", "autorizo a", "entregar a", NO pongas esos datos como titular. Cargalos en:
- autorizado_nombre
- autorizado_dni
- autorizado_telefono

Si no hay señal explícita de autorizado, dejá autorizado_* vacío.

REGLAS DE NEGOCIO ML / ACORDÁS:
1. En esta modalidad no vemos siempre todos los datos completos que el comprador cargó en Mercado Libre. Si el comprador dice "están en Mercado Libre", "son los mismos de la compra", "ya figuran", "están en mis datos" o similar, NO lo marques como conflicto: resumí que reclama que los datos ya están en ML y mantené los faltantes.
2. El envío es sin cargo. Si pregunta cuánto sale el envío, resumí que pregunta por costo de envío.
3. La demora habitual es de entre 3 y 5 días hábiles a partir del despacho. Si pregunta cuánto demora o cuándo llega, resumí que pregunta por demora.
4. Si pregunta por qué pedimos los datos, resumí que pide explicación sobre los datos.
5. Si dice "ya los pasé", verificá contra datos_previos + mensaje nuevo. Si siguen faltando datos, mantené solo los faltantes reales.
6. Si falta código postal pero hay localidad clara, mantené codigo_postal como faltante salvo que el comprador lo haya escrito explícitamente.
7. Si el comprador solo quiere que lo llamen o pasar WhatsApp, extraé el teléfono si está, pero seguí marcando los datos faltantes.
8. Si el mensaje mezcla datos del titular y de un autorizado, mantené separados: titular en nombre/apellido/dni/teléfono; autorizado en autorizado_nombre/autorizado_dni/autorizado_telefono.
9. No reemplaces el titular por el autorizado.

ESCALAR A OPERADOR:
Marcá requiere_operador=true SOLO si detectás intención de cancelar, reclamo/problema, enojo fuerte, insultos, cambio de modalidad de entrega/retiro, problema con el producto o una pregunta que no se pueda responder con estas reglas. En esos casos, el resumen debe incluir un llamado a la acción claro para el operador.

NO HACER:
- No prometas fechas exactas.
- No elijas transporte.
- No confirmes despacho.
- No resuelvas reclamos.
- No cambies estados.

Datos ya conocidos del pedido, si existen:
{datos_previos}

Mensaje nuevo del comprador:
"""{texto_cliente}"""

Respondé SOLO JSON válido con esta estructura exacta:
{{
  "datos": {{
    "nombre": "",
    "apellido": "",
    "dni": "",
    "telefono": "",
    "direccion": "",
    "localidad": "",
    "codigo_postal": "",
    "autorizado_nombre": "",
    "autorizado_dni": "",
    "autorizado_telefono": ""
  }},
  "faltantes": [],
  "datos_completos": false,
  "requiere_operador": false,
  "motivo_operador": "",
  "resumen": "",
  "confianza": "baja|media|alta"
}}

En resumen, indicá claramente si aplica alguno de estos casos: datos en Mercado Libre, ya los pasé, pregunta por demora, pregunta por costo de envío, pregunta por qué pedimos datos, quiere llamada/WhatsApp, requiere operador.
'''.format(
        datos_previos=json.dumps(datos_previos, ensure_ascii=False),
        texto_cliente=str(texto_cliente or "").strip(),
    )

    try:
        contenido = ia_chat_completion_json_service(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Respondés únicamente JSON válido. "
                        "Sos preciso, conservador y APB."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperatura=0,
            timeout=25,
        )
        resultado = ia_json_loads_seguro(contenido)
        if not resultado:
            raise ValueError("La IA no devolvió JSON válido")

        datos = resultado.get("datos") or {}

        # APB: refuerzo determinístico para DNI/CP.
        # Si el comprador respondió "1617", "Código postal 1617", "32339954" o "DNI 37331234",
        # lo tomamos aunque la IA no lo haya extraído.
        datos_clasicos = ia_extraer_datos_clasico_fierro(texto_cliente, datos_previos)
        for c, v in datos_clasicos.items():
            if v and not str(datos.get(c) or "").strip():
                datos[c] = v

        fusionados = dict(datos_previos)
        for c in campos:
            valor = str(datos.get(c) or "").strip()
            if valor:
                fusionados[c] = valor
            else:
                fusionados.setdefault(c, "")
        for c in campos_autorizado:
            valor = str(datos.get(c) or "").strip()
            if valor:
                fusionados[c] = valor
            else:
                fusionados.setdefault(c, "")

        faltantes = [c for c in campos if not str(fusionados.get(c) or "").strip()]
        resultado["datos"] = {c: str(fusionados.get(c) or "").strip() for c in campos + campos_autorizado}
        resultado["faltantes"] = faltantes
        resultado["datos_completos"] = len(faltantes) == 0
        resultado["ok"] = True
        return resultado
    except HTTPError as e:
        detalle = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
        return {"ok": False, "estado": "error", "error": f"OpenAI HTTP {e.code}: {detalle[:500]}"}
    except Exception as e:
        return {"ok": False, "estado": "error", "error": str(e)[:500]}



def capitalizar_texto_fierro(valor):
    """Capitaliza nombres/localidades/direcciones sin ponerse exquisito."""
    texto = str(valor or "").strip()
    if not texto:
        return ""

    texto = re.sub(r"\s+", " ", texto)
    minusculas = {"de", "del", "la", "las", "los", "y", "e"}
    siglas = {"dni", "cp"}

    partes = []
    for palabra in texto.split(" "):
        limpia = palabra.strip()
        if not limpia:
            continue
        base = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", "", limpia).lower()
        if base in siglas:
            partes.append(limpia.upper())
        elif base in minusculas:
            partes.append(limpia.lower())
        else:
            partes.append("-".join([x[:1].upper() + x[1:].lower() if x else x for x in limpia.split("-")]))
    return " ".join(partes).strip()


def normalizar_direccion_fierro(valor):
    texto = str(valor or "").strip()
    if not texto:
        return ""
    texto = re.sub(r"\s+", " ", texto)
    reemplazos = [
        (r"\bav\.?\b", "Av."),
        (r"\bavenida\b", "Av."),
        (r"\bcalle\b", "Calle"),
        (r"\bnro\.?\b", "N°"),
        (r"\bnº\b", "N°"),
        (r"\bnumero\b", "N°"),
        (r"\bpiso\b", "Piso"),
        (r"\bdpto\.?\b", "Dpto."),
        (r"\bdepartamento\b", "Dpto."),
    ]
    # Capitalización general primero, luego normalizamos abreviaturas comunes.
    texto = capitalizar_texto_fierro(texto)
    for patron, rep in reemplazos:
        texto = re.sub(patron, rep, texto, flags=re.IGNORECASE)
    return texto.strip()


def normalizar_datos_ia_fierro(datos):
    if not isinstance(datos, dict):
        return {}
    normalizados = dict(datos)
    for campo in ["nombre", "apellido", "localidad", "autorizado_nombre"]:
        if normalizados.get(campo):
            normalizados[campo] = capitalizar_texto_fierro(normalizados.get(campo))
    if normalizados.get("direccion"):
        normalizados["direccion"] = normalizar_direccion_fierro(normalizados.get("direccion"))
    if normalizados.get("dni"):
        normalizados["dni"] = ia_dni_valido(normalizados.get("dni")) or str(normalizados.get("dni") or "").strip()
    if normalizados.get("autorizado_dni"):
        normalizados["autorizado_dni"] = ia_dni_valido(normalizados.get("autorizado_dni")) or str(normalizados.get("autorizado_dni") or "").strip()
    if normalizados.get("autorizado_telefono"):
        normalizados["autorizado_telefono"] = normalizar_telefono(normalizados.get("autorizado_telefono"))
    if normalizados.get("codigo_postal"):
        normalizados["codigo_postal"] = str(normalizados.get("codigo_postal") or "").strip().upper()
    return normalizados

def ia_campo_vacio(valor):
    return not str(valor or "").strip()


def ia_dni_valido(valor):
    limpio = re.sub(r"\D+", "", str(valor or ""))
    return limpio if 7 <= len(limpio) <= 11 else ""


def ia_cp_valido(valor):
    limpio = str(valor or "").strip()
    # Acepta CP numérico argentino y también formatos alfanuméricos, sin ser demasiado agresivo.
    return limpio if 3 <= len(limpio) <= 12 else ""


def ia_extraer_datos_clasico_fierro(texto_cliente, datos_previos=None):
    """Parser APB determinístico para datos críticos.

    Motivo: en ML/WhatsApp muchos clientes contestan solo "1617",
    "CP 1617", "Código postal 1617", "32339954" o "DNI 37331234".
    No puede depender solo de la IA porque si falla se repregunta un dato ya pasado.
    Este parser solo completa datos con alta confianza y no pisa valores previos.
    """
    datos_previos = datos_previos or {}
    texto_original = str(texto_cliente or "").strip()
    texto = texto_original.lower()
    extraidos = {}

    def falta(campo):
        return not str((datos_previos or {}).get(campo) or "").strip()

    # DNI etiquetado: DNI: 37331234 / Documento 37.331.234 / doc 37331234
    m_dni = re.search(
        r"(?:\bd\.?n\.?i\.?\b|\bdni\b|\bdocumento\b|\bdoc\.?\b)\s*[:#-]?\s*([0-9][0-9\.\s-]{5,15}[0-9])",
        texto_original,
        flags=re.IGNORECASE,
    )
    if m_dni and falta("dni"):
        dni = ia_dni_valido(m_dni.group(1))
        if dni:
            extraidos["dni"] = dni

    # CP etiquetado: CP 1617 / C.P.: 1888 / Código postal 1617 / codigo postal: 1617
    m_cp = re.search(
        r"(?:\bc\.?p\.?\b|\bcod(?:igo)?\s*postal\b|\bcódigo\s*postal\b|\bpostal\b)\s*[:#-]?\s*([A-Za-z]?[0-9]{3,5}[A-Za-z]{0,3})",
        texto_original,
        flags=re.IGNORECASE,
    )
    if m_cp and falta("codigo_postal"):
        cp = ia_cp_valido(m_cp.group(1).strip().upper())
        if cp:
            extraidos["codigo_postal"] = cp

    # Respuesta suelta: "1617" cuando falta CP.
    # Para evitar confundir con DNI/teléfono, solo se usa si el mensaje es básicamente un único valor de 4 dígitos.
    solo_numero = re.fullmatch(r"\s*(\d{4})\s*", texto_original)
    if solo_numero and falta("codigo_postal"):
        extraidos.setdefault("codigo_postal", solo_numero.group(1))

    # Respuesta suelta: "32339954" cuando falta DNI.
    # Solo se usa si el mensaje es un único número/documento de 7 a 11 dígitos.
    solo_dni = re.fullmatch(r"\s*([0-9][0-9\.\s-]{5,15}[0-9])\s*", texto_original)
    if solo_dni and falta("dni"):
        dni = ia_dni_valido(solo_dni.group(1))
        if dni and len(dni) >= 7:
            extraidos.setdefault("dni", dni)

    return extraidos


def ia_calcular_faltantes_reales_pedido(pedido, datos=None):
    """Recalcula faltantes contra el pedido ya actualizado, no contra la respuesta vieja de IA."""
    datos = datos if isinstance(datos, dict) else {}

    def valor(campo):
        v = getattr(pedido, campo, "") if pedido else ""
        if str(v or "").strip():
            return str(v or "").strip()
        return str(datos.get(campo) or "").strip()

    faltantes = []
    if not valor("nombre") and not valor("cliente"):
        # Si el cliente ya está cargado como nombre completo, no forzar nombre/apellido por separado.
        if not str(getattr(pedido, "cliente", "") or "").strip():
            faltantes.append("nombre")
    if not valor("dni") and not str(getattr(pedido, "ml_billing_documento", "") or "").strip():
        faltantes.append("dni")
    if not normalizar_telefono(valor("telefono")):
        faltantes.append("telefono")
    if not valor("direccion"):
        faltantes.append("direccion")
    if not valor("localidad"):
        faltantes.append("localidad")
    if not ia_cp_valido(valor("codigo_postal")):
        faltantes.append("codigo_postal")
    return faltantes


def ia_texto_menciona_autorizado(texto):
    """Detecta si el comprador está pasando datos de otra persona.

    Regla APB:
    - Si aparecen frases como "quien recibe", "retira", "autorizado" o
      "entregar a", esos datos NO deben pisar al comprador/titular.
    - Se cargan en autorizado_nombre / autorizado_dni / autorizado_telefono.
    """
    t = str(texto or "").lower()
    patrones = [
        r"\bquien\s+recibe\b",
        r"\bquien\s+retira\b",
        r"\bquien\s+va\s+a\s+recibir\b",
        r"\bquien\s+va\s+a\s+retirar\b",
        r"\bel\s+que\s+recibe\b",
        r"\bla\s+que\s+recibe\b",
        r"\bel\s+que\s+retira\b",
        r"\bla\s+que\s+retira\b",
        r"\brecibe\s+[^,.]{2,80}",
        r"\bretira\s+[^,.]{2,80}",
        r"\bretirar\s+[^,.]{2,80}",
        r"\bautorizad[oa]\b",
        r"\bautorizo\s+a\b",
        r"\bentregar\s+a\b",
        r"\bentrega\s+a\b",
        r"\bse\s+lo\s+entregan\s+a\b",
        r"\ba\s+nombre\s+de\b",
    ]
    return any(re.search(p, t) for p in patrones)


def ia_autocompletar_pedido_con_datos(pedido, datos, texto_cliente=""):
    """
    Fase 4 segura: usa datos detectados por IA para completar la carga.
    Regla APB: solo completa campos vacíos. No pisa datos ya cargados manualmente,
    salvo cliente cuando todavía parece nick de Mercado Libre. No cambia estados.
    """
    if not pedido or not isinstance(datos, dict):
        return []

    completados = []

    datos = normalizar_datos_ia_fierro(datos)

    nombre = str(datos.get("nombre") or "").strip()
    apellido = str(datos.get("apellido") or "").strip()
    nombre_completo = " ".join([x for x in [nombre, apellido] if x]).strip()

    autorizado_nombre = str(datos.get("autorizado_nombre") or "").strip()
    autorizado_dni = ia_dni_valido(datos.get("autorizado_dni"))
    autorizado_telefono = normalizar_telefono(datos.get("autorizado_telefono")) if datos.get("autorizado_telefono") else ""
    texto_indica_autorizado = ia_texto_menciona_autorizado(texto_cliente)

    if texto_indica_autorizado:
        # APB: si el texto habla de quien recibe/retira/autorizado, NO pisar titular.
        # Si la IA no separó los campos, usamos los datos comunes como autorizado.
        autorizado_nombre = autorizado_nombre or nombre_completo
        autorizado_dni = autorizado_dni or ia_dni_valido(datos.get("dni"))
        autorizado_telefono = autorizado_telefono or (normalizar_telefono(datos.get("telefono")) if datos.get("telefono") else "")

        if autorizado_nombre and ia_campo_vacio(getattr(pedido, "autorizado_nombre", "")):
            pedido.autorizado_nombre = autorizado_nombre
            completados.append("autorizado_nombre")
        if autorizado_dni and ia_campo_vacio(getattr(pedido, "autorizado_dni", "")):
            pedido.autorizado_dni = autorizado_dni
            completados.append("autorizado_dni")
        if autorizado_telefono and ia_campo_vacio(getattr(pedido, "autorizado_telefono", "")):
            pedido.autorizado_telefono = autorizado_telefono
            completados.append("autorizado_telefono")
    else:
        cliente_actual = str(getattr(pedido, "cliente", "") or "").strip()
        puede_reemplazar_cliente = ia_campo_vacio(cliente_actual) or parece_nickname_ml(cliente_actual, getattr(pedido, "ml_buyer_nickname", ""))
        if nombre_completo and puede_reemplazar_cliente:
            pedido.cliente = nombre_completo
            completados.append("cliente")

        dni = ia_dni_valido(datos.get("dni"))
        if dni and ia_campo_vacio(getattr(pedido, "dni", "")):
            pedido.dni = dni
            completados.append("dni")

        telefono = normalizar_telefono(datos.get("telefono"))
        if telefono and ia_campo_vacio(getattr(pedido, "telefono", "")):
            pedido.telefono = telefono
            completados.append("telefono")

    direccion = str(datos.get("direccion") or "").strip()
    if direccion and ia_campo_vacio(getattr(pedido, "direccion", "")):
        pedido.direccion = direccion
        completados.append("direccion")

    localidad = str(datos.get("localidad") or "").strip()
    if localidad and ia_campo_vacio(getattr(pedido, "localidad", "")):
        pedido.localidad = localidad
        completados.append("localidad")

    codigo_postal = ia_cp_valido(datos.get("codigo_postal"))
    if codigo_postal and ia_campo_vacio(getattr(pedido, "codigo_postal", "")):
        pedido.codigo_postal = codigo_postal
        completados.append("codigo_postal")

    return completados


def ia_guardar_resultado_recolector(pedido, texto_cliente, resultado):
    if not pedido:
        return
    pedido.ia_ultimo_mensaje_hash = ia_hash_texto(texto_cliente)
    pedido.ia_ultimo_analisis = datetime.utcnow()
    pedido.ia_error = ""

    if not resultado or not resultado.get("ok"):
        pedido.ia_recolector_estado = resultado.get("estado") if isinstance(resultado, dict) else "error"
        pedido.ia_error = (resultado.get("error") if isinstance(resultado, dict) else "Error IA") or "Error IA"
        return

    datos = normalizar_datos_ia_fierro(resultado.get("datos") or {})

    # Segundo cinturón APB: si por algún motivo el resultado no trajo DNI/CP,
    # volvemos a mirar el texto antes de guardar y responder.
    datos_clasicos = ia_extraer_datos_clasico_fierro(texto_cliente, ia_datos_previos_pedido(pedido))
    for c, v in datos_clasicos.items():
        if v and not str(datos.get(c) or "").strip():
            datos[c] = v

    completados = ia_autocompletar_pedido_con_datos(pedido, datos, texto_cliente=texto_cliente)

    # Importante: no usar a ciegas los faltantes que devolvió la IA antes de autocompletar.
    # Se recalculan contra el pedido actualizado para no pedir DNI/CP dos veces.
    faltantes = ia_calcular_faltantes_reales_pedido(pedido, datos)
    requiere_operador = bool(resultado.get("requiere_operador"))

    if requiere_operador:
        estado = "requiere_operador"
    elif not faltantes:
        estado = "datos_completos"
    else:
        estado = "juntando_datos"

    pedido.ia_recolector_estado = estado
    pedido.ia_datos_detectados = json.dumps(datos, ensure_ascii=False)
    pedido.ia_faltantes = json.dumps(faltantes, ensure_ascii=False)
    resumen = str(resultado.get("resumen") or "").strip()
    if completados:
        extra = "IA autocompletó: " + ", ".join(completados)
        resumen = (resumen + " | " + extra).strip(" |") if resumen else extra
    pedido.ia_resumen = resumen
    pedido.ia_requiere_operador = requiere_operador

    # APB:
    # Mercado Libre inicia el contacto y sigue recolectando mientras el canal esté activo.
    # WhatsApp puede tomar la posta:
    # - con datos completos,
    # - o con faltantes si ML quedó cortado / timeout / escalado.
    if not requiere_operador:
        wa_auto_iniciar_desde_ml_si_corresponde(
            pedido,
            faltantes=faltantes,
            motivo="ia_guardar_resultado_recolector",
        )


def ia_analizar_ultimo_mensaje_pedido(pedido, mensajes, seller_id="", forzar=False):
    """Analiza último mensaje del comprador si corresponde. Autocompleta campos vacíos. No envía nada al cliente."""
    if not pedido or not es_ml_acordas_entrega(pedido):
        return None
    if not getattr(pedido, "contacto_iniciado", False):
        return None

    ultimo = ml_ultimo_mensaje_comprador(mensajes, seller_id=seller_id)
    if not ultimo:
        return None

    texto = ml_texto_mensaje_ml(ultimo)

    if texto:
        ia_marcar_respuesta_cliente(
        pedido,
        canal="mercadolibre",
        commit=False,
    )

    # APB:
    # Si el comprador respondió solo el CP
    # o escribió "CP 3500", lo tomamos
    # antes de llamar a IA.
    cp_detectado = ia_extraer_codigo_postal_simple(texto)

    faltantes_actuales = ia_faltantes_pedido(pedido) or []
    texto_limpio_cp = re.sub(r"\D", "", texto or "")

    esperando_cp = (
        "codigo_postal" in faltantes_actuales
        or "cp" in faltantes_actuales
        or "codigo postal" in str(pedido.ia_faltantes or "").lower()
    )

    posible_cp_contextual = (
        texto_limpio_cp.isdigit()
        and len(texto_limpio_cp) == 4
    )

    if esperando_cp and posible_cp_contextual:
        cp_detectado = texto_limpio_cp

    if (
        posible_cp_contextual
        and (pedido.codigo_postal or "").strip()
        and (pedido.codigo_postal or "").strip() != texto_limpio_cp
    ):
        cp_detectado = texto_limpio_cp

    if cp_detectado:
        pedido.codigo_postal = cp_detectado

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        resumen = (pedido.ia_resumen or "").strip()

        marca = (
            f"IA autocompletó CP simple: {cp_detectado}"
        )

        if marca not in resumen:
            pedido.ia_resumen = (
                f"{resumen} | {marca}"
            ).strip(" |")[:1000]

        # APB:
        # El CP puede ser el último dato faltante.
        # Después de guardarlo hay que limpiar bloqueo viejo,
        # recalcular faltantes y reenganchar el flujo automático.
        nuevos_faltantes = ia_faltantes_pedido(pedido) or []

        pedido.ia_faltantes = json.dumps(
            nuevos_faltantes,
            ensure_ascii=False,
        )

        if not nuevos_faltantes:
            pedido.ia_requiere_operador = False
            pedido.ia_recolector_estado = "datos_completos"
            pedido.ia_ultimo_timeout_operador = None

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        try:
            ia_auto_responder_post_analisis(pedido)
        except Exception as e:
            print(
                f"[IA-CP-APB] No se pudo reenganchar flujo "
                f"pedido #{pedido.id}: {e}"
            )                

        # DETECTAR SUCURSAL
        # PP6040 va por Andreani/Correo a domicilio → nunca detectar sucursal Via Cargo
        # Solo detectar elección si el sistema YA ofreció opciones al cliente (ia_sucursales_ofrecidas)
        # Evita que el texto con los datos del cliente (localidad, dirección) se confunda con una elección
        _sucursales_ya_ofrecidas = bool(getattr(pedido, "ia_sucursales_ofrecidas", None))
        if not pedido_es_plegable_pp6040(pedido) and _sucursales_ya_ofrecidas:
            # Si el sistema ya ofreció sucursales y el cliente hace una consulta
            # en lugar de elegir → escalar al operador para que lo resuelva
            candidatas_ids_check = []
            try:
                candidatas_ids_check = json.loads(getattr(pedido, "ia_sucursales_ofrecidas", "") or "[]")
            except Exception:
                pass

            if candidatas_ids_check and texto and _es_consulta_no_eleccion(texto.lower()):
                try:
                    pedido.ml_mensajes_pendientes = True
                    pedido.ia_requiere_operador = True
                    resumen = (pedido.ia_resumen or "").strip()
                    pedido.ia_resumen = f"{resumen} | Cliente consultó sobre sucursal: {texto[:100]}".strip(" |")
                    db.session.commit()
                    print(f"[VIA CARGO] Pedido #{pedido.id} escalado: consulta de sucursal no resuelta")
                except Exception as e:
                    print(f"[VIA CARGO] Error escalando consulta sucursal:", e)
                return None

            suc = detectar_sucursal(pedido, texto)
            if suc and not getattr(pedido, "sucursal_nombre", None):
                pedido.sucursal_nombre = suc.get("nombre")
                pedido.direccion = suc.get("direccion")
                pedido.localidad = suc.get("localidad")
                pedido.provincia = suc.get("provincia")
                # Autocompletar transporte y tipo de entrega según regla de negocio
                if not (pedido.empresa_envio or "").strip():
                    pedido.empresa_envio = "Vía Cargo"
                pedido.tipo_entrega = "Sucursal"
                try:
                    db.session.commit()
                except:
                    pass
                # Confirmar al cliente que la sucursal fue registrada y el despacho está en proceso
                try:
                    nombre_cliente = (getattr(pedido, "cliente", "") or "Cliente").split()[0] or "Cliente"

                    msg_confirmacion = (
                        f"Muchas gracias {nombre_cliente}! 🙌\n\n"
                        f"Tu pedido ya está en proceso de despacho a:\n"
                        f"📍 {suc.get('nombre')}\n"
                        f"📌 {suc.get('direccion')}\n\n"
                        f"En breve te pasamos el número de seguimiento para que puedas rastrear tu envío 😊"
                    )

                    # ---------------------------------------------------
                    # APB CANAL MANAGER
                    # ---------------------------------------------------

                    permitido, motivo = puede_enviar_mensaje(
                        pedido=pedido,
                        canal="ml",
                        texto=msg_confirmacion,
                    )

                    if not permitido:
                        print(
                            f"[CANAL-MANAGER] ML bloqueado pedido #{pedido.id}: {motivo}"
                        )
                        return False, motivo

                    ml_enviar_mensaje_acordas(
                        pedido,
                        msg_confirmacion,
                    )

                    registrar_envio_automatico(
                        pedido=pedido,
                        canal="ml",
                        texto=msg_confirmacion,
                    )

                except Exception as e:
                    print(
                        f"[VIA CARGO] No se pudo enviar confirmación de sucursal pedido #{pedido.id}:",
                        e
                    )


    if not texto:
        return None

    h = ia_hash_texto(texto)
    if not forzar and h == str(getattr(pedido, "ia_ultimo_mensaje_hash", "") or ""):
        return None

    resultado = ia_analizar_datos_cliente_ml_acordas(texto, ia_datos_previos_pedido(pedido))
    ia_guardar_resultado_recolector(pedido, texto, resultado)
    if resultado and resultado.get("ok"):
        ia_auto_responder_post_analisis(pedido)
    return resultado

def ia_auto_responder_post_analisis(pedido):
    """
    Fase 5: respuesta automática controlada.
    - Si faltan datos: pide SOLO faltantes.
    - Si requiere operador: envía CTA claro y frena la automatización.
    - Si datos completos: no responde.
    No cambia estados del pedido.
    Se puede apagar con IA_AUTO_RESPUESTA=0.
    """
    if os.getenv("IA_AUTO_RESPUESTA", "1").strip().lower() in ["0", "false", "no", "off"]:
        return False, "apagada"
    if not pedido or not es_ml_acordas_entrega(pedido):
        return False, "no_aplica"
    if not getattr(pedido, "contacto_iniciado", False):
        return False, "sin_contacto"
    if str(getattr(pedido, "ia_recolector_estado", "") or "") == "error":
        return False, "error_ia"

    # APB CANAL: si WhatsApp ya tomó la posta, Mercado Libre queda pasivo.
    # Evita pedir los mismos faltantes por ML después de haberlos pedido por WA.
    wa_estado_actual = str(getattr(pedido, "wa_estado", "") or "").strip()
    if wa_estado_actual:
        print(
            f"[IA-AUTO-RESPUESTA] ML no responde pedido #{getattr(pedido, 'id', '?')}: "
            f"WhatsApp activo ({wa_estado_actual})"
        )
        return False, f"wa_activo_{wa_estado_actual}"

    texto = ""
    if getattr(pedido, "ia_requiere_operador", False) or pedido.ia_recolector_estado == "requiere_operador":
        texto = ia_generar_cta_operador_pedido(pedido)
    else:
        faltantes = ia_faltantes_pedido(pedido)

        if not faltantes:
            # Datos del cliente completos.
            # ML Acordás la Entrega que NO es plegable PP6040 → siempre Via Cargo sucursal.
            # Si falta elegir sucursal, mandar opciones al cliente.
            es_via_cargo_acordas = es_ml_acordas_entrega(pedido) and not pedido_es_plegable_pp6040(pedido)
            if not es_via_cargo_acordas:
                # PP6040 (plegable) → cotizar y asignar transporte automáticamente
                if pedido_es_plegable_pp6040(pedido):
                    try:
                        from modules.transportes import asignar_transporte_pedido
                        ok, msg_transporte = asignar_transporte_pedido(pedido)
                        if ok:
                            print(f"[TRANSPORTES] Pedido #{pedido.id}: {msg_transporte}")
                            # Avisar al operador que el transporte fue asignado
                            pedido.ml_mensajes_pendientes = True
                            resumen = (pedido.ia_resumen or "").strip()
                            pedido.ia_resumen = f"{resumen} | {msg_transporte}".strip(" |")
                            db.session.commit()
                        else:
                            # Sin cobertura → escalar al operador
                            pedido.ml_mensajes_pendientes = True
                            pedido.ia_requiere_operador = True
                            resumen = (pedido.ia_resumen or "").strip()
                            pedido.ia_resumen = f"{resumen} | Sin cobertura transportes CP {pedido.codigo_postal}".strip(" |")
                            db.session.commit()
                    except Exception as e:
                        print(f"[TRANSPORTES] Error asignando transporte pedido #{pedido.id}:", e)
                return False, "datos_completos"
            msg_sucursales = sugerir_sucursales(pedido)
            if msg_sucursales:
                try:

                    # ---------------------------------------------------
                    # APB CANAL MANAGER
                    # ---------------------------------------------------

                    permitido, motivo = puede_enviar_mensaje(
                        pedido=pedido,
                        canal="ml",
                        texto=msg_sucursales,
                    )

                    if not permitido:
                        print(
                            f"[CANAL-MANAGER] ML bloqueado pedido #{pedido.id}: {motivo}"
                        )
                        return False, motivo

                    ml_enviar_mensaje_acordas(pedido, msg_sucursales)

                    registrar_envio_automatico(
                        pedido=pedido,
                        canal="ml",
                        texto=msg_sucursales,
                    )

                    pedido.ia_respuesta_sugerida = msg_sucursales
                    pedido.ia_respuesta_enviada_hash = ia_hash_texto(msg_sucursales)
                    pedido.ia_ultima_respuesta_enviada = datetime.utcnow()
                    pedido.ml_mensajes_pendientes = False
                    pedido.ml_mensajes_pendientes_count = 0
                    db.session.commit()
                except Exception as e:
                    print("[VIA CARGO] No se pudo enviar sugerencia de sucursales:", e)
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                    return False, "error_sucursales"
                return True, "sucursales_enviadas"
            # No es Via Cargo o ya tiene sucursal: no hay nada más que hacer
            return False, "datos_completos"

        texto = ia_generar_respuesta_faltantes_pedido(pedido)

    texto = str(texto or "").strip()
    if not texto:
        return False, "sin_texto"

    if ia_respuesta_faltantes_ya_enviada(pedido, texto):
        return False, "duplicada"

    try:

        # ---------------------------------------------------
        # APB CANAL MANAGER
        # ---------------------------------------------------

        permitido, motivo = puede_enviar_mensaje(
            pedido=pedido,
            canal="ml",
            texto=texto,
        )

        if not permitido:
            print(
                f"[CANAL-MANAGER] ML bloqueado pedido #{pedido.id}: {motivo}"
            )
            return False, motivo

        ml_enviar_mensaje_acordas(pedido, texto)

        registrar_envio_automatico(
            pedido=pedido,
            canal="ml",
            texto=texto,
        )

        pedido.ia_respuesta_sugerida = texto
        pedido.ia_respuesta_enviada_hash = ia_hash_texto(texto)
        pedido.ia_ultima_respuesta_enviada = datetime.utcnow()
        pedido.ml_mensajes_pendientes = False
        pedido.ml_mensajes_pendientes_count = 0
        pedido.ia_resumen = ((pedido.ia_resumen or "") + " | IA respondió automáticamente").strip(" |")

        print(
            f"[IA-AUTO-RESPUESTA] OK pedido #{pedido.id}: {texto[:120]}"
        )

        return True, "enviada"
    
    except Exception as e:
        pedido.ia_error = f"No se pudo enviar respuesta automática IA: {str(e)[:400]}"
        print(f"[IA-AUTO-RESPUESTA] Error pedido #{getattr(pedido, 'id', '?')}: {e}")
        return False, "error_envio"

def ml_hay_mensaje_pendiente_en_thread(mensajes, seller_id=""):
    """
    Regla APB para postventa:
    1) Si ML informa unread/pending del comprador, hay pendiente.
    2) Si ML no informa estado, pero el ultimo mensaje del thread es del comprador,
       tambien lo tratamos como pendiente.
    """
    if not mensajes:
        return False, 0

    pendientes_explicitos = [
        m for m in mensajes
        if ml_mensaje_es_del_comprador(m, seller_id=seller_id) and ml_mensaje_esta_pendiente(m)
    ]
    if pendientes_explicitos:
        return True, len(pendientes_explicitos)

    ordenados = list(mensajes)
    try:
        ordenados.sort(key=ml_fecha_mensaje_valor)
    except Exception:
        pass

    ultimo = ordenados[-1] if ordenados else None
    if ultimo and ml_mensaje_es_del_comprador(ultimo, seller_id=seller_id):
        return True, 1

    return False, 0


def ml_obtener_ids_chat_pedido(pedido):
    """
    Devuelve IDs candidatos para consultar el chat ML. Prioriza pack_id real.
    Si falta ml_pack_id, intenta refrescar /orders/{id_venta} y guardarlo.
    """
    ids = []
    if not pedido:
        return ids

    def agregar(v):
        v = str(v or "").strip()
        if v and v not in ids:
            ids.append(v)

    agregar(getattr(pedido, "ml_pack_id", ""))
    order_id = str(getattr(pedido, "id_venta", "") or "").strip()
    agregar(order_id)

    pack_actual = str(getattr(pedido, "ml_pack_id", "") or "").strip()
    if order_id and (not pack_actual or pack_actual == order_id):
        try:
            order = ml_api_get(f"/orders/{order_id}")
            pack_api = str((order or {}).get("pack_id") or "").strip()
            if pack_api:
                agregar(pack_api)
                if pack_api != pack_actual:
                    pedido.ml_pack_id = pack_api
        except Exception as e:
            print(f"[ML-MSGS-PACKID] No se pudo resolver pack_id para pedido #{getattr(pedido, 'id', '?')} order={order_id}: {e}")

    return ids


def ml_sync_mensajes_pedido(pedido):
    """Sincroniza mensajes de UN pedido probando pack_id real + order_id como fallback."""
    if not pedido:
        return False, 0

    ids_chat = ml_obtener_ids_chat_pedido(pedido)
    if not ids_chat:
        pedido.ml_mensajes_pendientes = False
        pedido.ml_mensajes_pendientes_count = 0
        pedido.ultima_sync_mensajes_ml = datetime.utcnow()
        return False, 0

    for id_chat in ids_chat:
        tiene, count = ml_sync_mensajes_pack(id_chat, pedido=pedido)
        if tiene or count > 0:
            pedido.ml_mensajes_pendientes = True
            pedido.ml_mensajes_pendientes_count = count or 1
            pedido.ultima_sync_mensajes_ml = datetime.utcnow()
            print(f"[ML-MSGS-PEDIDO] pedido #{pedido.id} id_chat={id_chat} pendientes={count}")
            return True, count or 1

    pedido.ml_mensajes_pendientes = False
    pedido.ml_mensajes_pendientes_count = 0
    pedido.ultima_sync_mensajes_ml = datetime.utcnow()
    print(f"[ML-MSGS-PEDIDO] pedido #{pedido.id} sin pendientes. ids_chat={ids_chat}")
    return False, 0


def ml_obtener_mensajes_pack_para_ia(pack_id, seller_id=""):
    """Obtiene mensajes del thread ML para análisis IA sin marcar como leídos."""
    pack_id = str(pack_id or "").strip()
    if not pack_id:
        return []

    seller_id = str(seller_id or "").strip()
    intentos = []
    if seller_id:
        intentos.append((f"/messages/packs/{pack_id}/sellers/{seller_id}", {"tag": "post_sale", "limit": 50}))
        intentos.append((f"/messages/packs/{pack_id}/sellers/{seller_id}", {"limit": 50}))
    intentos.append((f"/messages/packs/{pack_id}", {"role": "seller", "tag": "post_sale", "limit": 50}))
    intentos.append((f"/messages/packs/{pack_id}", {"role": "seller", "limit": 50}))

    for path, params in intentos:
        try:
            data = ml_api_get(path, params=params)
            mensajes = ml_extraer_lista_mensajes_ml(data)
            if mensajes:
                return mensajes
        except Exception as e:
            print(f"[IA-RECOLECTOR] Fallo leyendo mensajes {path} {params}: {e}")
            continue
    return []


def ml_sync_mensajes_pack(pack_id, pedido=None):
    """
    Consulta el thread de mensajes postventa de un pack/order ML y detecta
    mensajes sin leer del comprador. No marca mensajes como leidos.
    Devuelve (tiene_pendientes: bool, count: int).
    """
    pack_id = str(pack_id or "").strip()
    if not pack_id:
        return False, 0

    cuenta = MercadoLibreCuenta.query.first()
    seller_id = str((cuenta.user_id_ml if cuenta else "") or "").strip()

    intentos = []
    if seller_id:
        intentos.append((f"/messages/packs/{pack_id}/sellers/{seller_id}", {"tag": "post_sale", "limit": 50}))
        intentos.append((f"/messages/packs/{pack_id}/sellers/{seller_id}", {"limit": 50}))
    intentos.append((f"/messages/packs/{pack_id}", {"role": "seller", "tag": "post_sale", "limit": 50}))
    intentos.append((f"/messages/packs/{pack_id}", {"role": "seller", "limit": 50}))

    ultimo_error = None
    mensajes = []
    endpoint_ok = ""

    for path, params in intentos:
        try:
            data = ml_api_get(path, params=params)
            mensajes = ml_extraer_lista_mensajes_ml(data)
            endpoint_ok = f"{path} {params}"
            print(f"[ML-MSGS-PACK] OK {endpoint_ok} mensajes={len(mensajes)}")
            if mensajes:
                break
        except Exception as e:
            ultimo_error = e
            print(f"[ML-MSGS-PACK] Fallo {path} {params}: {e}")
            continue

    tiene_pendiente, count = ml_hay_mensaje_pendiente_en_thread(mensajes, seller_id=seller_id)

    if pedido is not None:
        pedido.ml_mensajes_pendientes = tiene_pendiente
        pedido.ml_mensajes_pendientes_count = count
        pedido.ultima_sync_mensajes_ml = datetime.utcnow()
        # APB: NO marcar contacto iniciado por leer mensajes de ML.
        # El contacto inicial solo se marca por accion explicita del operador:
        # Enviar mensaje ML / Copiar mensaje.

        # IA Fase 2: si ya se mandó el contacto inicial y llegó respuesta del comprador,
        # analizar datos detectados. NO responde al cliente ni cambia estados.
        try:
            ia_analizar_ultimo_mensaje_pedido(pedido, mensajes, seller_id=seller_id, forzar=False)
        except Exception as e:
            pedido.ia_recolector_estado = "error"
            pedido.ia_error = str(e)[:500]
            print(f"[IA-RECOLECTOR] Error analizando pedido {pedido.id}: {e}")


    if not endpoint_ok and ultimo_error:
        print(f"[ML-MSGS-PACK] Error consultando pack/order {pack_id}: {ultimo_error}")
    else:
        print(f"[ML-MSGS-PACK] pack/order={pack_id} endpoint={endpoint_ok} pendientes={count}")

    return tiene_pendiente, count


def ml_sync_mensajes_pendientes_pedidos():
    """
    Sync mejorada para mensajes postventa:
    en vez de depender de /messages/unread, consulta por pack_id/order_id
    en pedidos ML operativos. Es respaldo del webhook.
    """
    cuenta = cuenta_ml_actual()
    if not cuenta:
        return 0

    estados_operativos = [
        "Cargando Pedido",
        Estado.ETIQUETA_LISTA,
        Estado.ETIQUETA_IMPRESA,
        "Embalado",
        "Despachado",
        Estado.VERIFICAR_DESTINO,
        Estado.LISTO_RETIRAR,
        "Con demora de entrega",
        "Con reclamo en transporte",
        "Con reclamo por demora",
        "No Entregado",
        "No entregado",
    ]

    pedidos_ml = Pedido.query.filter(
        Pedido.canal == "Mercado Libre",
        Pedido.estado.in_(estados_operativos)
    ).all()

    total_pendientes = 0

    for pedido in pedidos_ml:
        tiene, count = ml_sync_mensajes_pedido(pedido)
        total_pendientes += int(count or 0)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[ML-MSGS-SYNC] Error guardando mensajes pendientes: {e}")

    return total_pendientes


def ml_pedido_tiene_mensajes_pendientes(pedido):
    if not pedido:
        return False
    try:
        return bool(pedido.ml_mensajes_pendientes) or int(pedido.ml_mensajes_pendientes_count or 0) > 0
    except Exception:
        return bool(pedido.ml_mensajes_pendientes)


def ml_pedido_tiene_chat_iniciado(pedido):
    """Señal visual APB de contacto inicial realizado.
    Solo depende del flag explícito del operador: no inferir por fecha_contacto
    para evitar globos falsos por datos viejos o correcciones parciales.
    """
    if not pedido:
        return False
    return bool(getattr(pedido, "contacto_iniciado", False))


def fecha_argentina(fecha):
    """Muestra timestamps internos UTC en horario Argentina para la UI."""
    if not fecha:
        return None
    try:
        return fecha - timedelta(hours=3)
    except Exception:
        return fecha


def ml_mensaje_thread_habilitado(pedido):
    """
    Verifica si ML permite enviar mensajes por API para este pedido.
    Si no esta habilitado, el flujo debe hacer fallback a ML web.
    """
    if not pedido:
        return False

    estados_bloqueados = {"payment_in_process", "payment_required", "cancelled"}
    estado_ml = str(getattr(pedido, "ml_order_status", "") or "").strip().lower()

    # Atajo local: si ML todavia no acredito pago o esta cancelado, no intentar API.
    if estado_ml in estados_bloqueados:
        return False

    pack_id = str(getattr(pedido, "ml_pack_id", "") or getattr(pedido, "id_venta", "") or "").strip()
    if not pack_id:
        return False

    cuenta = MercadoLibreCuenta.query.first()
    seller_id = str((cuenta.user_id_ml if cuenta else "") or "").strip()
    if not seller_id:
        raise ValueError("No hay cuenta de Mercado Libre conectada.")

    try:
        ml_api_get(
            f"/messages/packs/{pack_id}/sellers/{seller_id}",
            params={"tag": "post_sale"},
        )
        return True
    except HTTPError as e:
        detalle = e.read().decode("utf-8", errors="ignore")
        print(f"[ML-MENSAJES-SONDA] Pedido {pedido.id} | status={estado_ml} | HTTP {e.code} | {detalle}")
        if e.code in (403, 404):
            return estado_ml == "confirmed" and e.code == 404
        raise

def generar_mensaje_contacto_ml_api(pedido):
    """Primer contacto seguro para API ML: no pide datos personales ni de entrega."""
    if not pedido or not es_ml_acordas_entrega(pedido):
        return ""

    texto = (
        "Hola! Desde Fierro 100% Argento agradecemos tu compra.\n\n"
        "Te escribimos para coordinar el envio de tu pedido y avanzar con el despacho.\n\n"
        "Quedamos atentos a tu respuesta por este medio. Muchas gracias!"
    )

    if len(texto) > 348:
        texto = texto[:345] + "..."

    return texto
def ml_enviar_mensaje_acordas(pedido, texto):
    if not pedido or pedido.canal != "Mercado Libre" or not es_ml_acordas_entrega(pedido):
        raise ValueError("El pedido no corresponde a Mercado Libre / Acordás la Entrega.")

    texto = str(texto or "").strip()
    if not texto:
        raise ValueError("No hay mensaje para enviar.")

    puede_enviar, motivo_apb = ia_puede_enviar_automatico(pedido, "mercadolibre", texto)
    if not puede_enviar:
        raise ValueError(f"APB: no se envía mensaje automático ML ({motivo_apb}).")

    if not ml_mensaje_thread_habilitado(pedido):
        raise ValueError("__FALLBACK_A_WEB__")

    cuenta = MercadoLibreCuenta.query.first()
    seller_id = str((cuenta.user_id_ml if cuenta else "") or "").strip()
    buyer_id = str(pedido.ml_buyer_id or "").strip()

    if not seller_id:
        raise ValueError("No hay cuenta de Mercado Libre conectada.")
    if not buyer_id:
        raise ValueError("No se encontró el ID del comprador de Mercado Libre.")

    payload = {
        "from": {"user_id": int(seller_id)},
        "to": {"user_id": int(buyer_id)},
        "text": texto,
    }

    intentos = []
    pack_id = str(pedido.ml_pack_id or "").strip()
    order_id = str(pedido.id_venta or "").strip()

    if pack_id:
        intentos.append(f"/messages/packs/{pack_id}/sellers/{seller_id}?tag=post_sale")
    if order_id and order_id != pack_id:
        intentos.append(f"/messages/packs/{order_id}/sellers/{seller_id}?tag=post_sale")

    if not intentos:
        raise ValueError("El pedido no tiene ID de venta ni pack ID de Mercado Libre.")

    ultimo_error = None
    for path in intentos:
        try:
            resultado_ml = ml_api_post_json(path, payload)
            ia_marcar_mensaje_bot(pedido, "mercadolibre", texto, commit=False)
            return resultado_ml
        except Exception as e:
            ultimo_error = e
            print("No se pudo enviar mensaje ML por", path, e)

    raise ValueError(str(ultimo_error or "No se pudo enviar el mensaje a Mercado Libre."))


def ml_auto_enviar_contacto_inicial_acordas(pedido):
    """
    Fase 1 IA/APB: primer contacto automatico para ML / Acordas.
    Usa la plantilla existente del sistema, incluida la diferenciacion por producto.
    No cambia estados y no marca contacto iniciado si Mercado Libre rechaza el envio.
    """
    if not pedido or not es_ml_acordas_entrega(pedido):
        return False, "no_aplica"

    if bool(getattr(pedido, "contacto_iniciado", False)):
        return False, "ya_iniciado"

    texto = generar_mensaje_contacto_ml(pedido)
    if not texto:
        return False, "sin_mensaje"

    try:
        ml_enviar_mensaje_acordas(pedido, texto)
        pedido.ml_mensaje_contacto = texto
        marcar_contacto_iniciado_pedido(pedido)
        print(f"[ML-AUTO-CONTACTO] OK pedido #{pedido.id} order={pedido.id_venta} pack={pedido.ml_pack_id}")
        try:
            registrar_auditoria(
                accion="Envió contacto inicial ML automático",
                entidad="pedido",
                entidad_id=str(pedido.id),
                detalle=f"Mercado Libre / Acordás. Mensaje: {texto[:500]}",
            )
        except Exception as audit_error:
            print(f"[ML-AUTO-CONTACTO] No se pudo auditar pedido #{pedido.id}: {audit_error}")
        return True, "enviado"
    except Exception as e:
        # APB: si ML rechaza o no habilita el thread, no rompemos la importacion ni marcamos contacto iniciado.
        print(f"[ML-AUTO-CONTACTO] NO ENVIADO pedido #{getattr(pedido, 'id', '')} order={getattr(pedido, 'id_venta', '')}: {e}")
        return False, str(e)


def ml_obtener_etiqueta_url(shipping_id):
    # Compatibilidad: mantiene el nombre viejo, pero ahora descarga y devuelve el archivo local.
    return ml_guardar_etiqueta_pdf(shipping_id)



def etiqueta_archivo_local_disponible(etiqueta_archivo):
    archivo = os.path.basename(str(etiqueta_archivo or ""))
    if not archivo:
        return False
    return os.path.exists(os.path.join(app.config["UPLOAD_FOLDER"], archivo))


def ml_asegurar_etiqueta_disponible(pedido):
    """
    Garantiza que la etiqueta ML esté disponible en el servidor actual.
    Render puede perder archivos locales al redeploy, por eso re-descargamos por shipping_id.
    """
    if not pedido or not es_mercado_envios(pedido):
        return True

    if pedido.etiqueta_archivo and str(pedido.etiqueta_archivo).startswith("http"):
        return True

    if etiqueta_archivo_local_disponible(pedido.etiqueta_archivo):
        return True

    if not pedido.ml_shipping_id and pedido.id_venta:
        order = ml_obtener_order(pedido.id_venta)
        shipment_id = (order.get("shipping") or {}).get("id") if order else ""
        if shipment_id:
            pedido.ml_shipping_id = str(shipment_id).strip()

    if pedido.ml_shipping_id:
        nombre_pdf = ml_guardar_etiqueta_pdf(pedido.ml_shipping_id)
        if nombre_pdf:
            pedido.etiqueta_archivo = os.path.basename(str(nombre_pdf))
            return etiqueta_archivo_local_disponible(pedido.etiqueta_archivo)

    return False


def ml_nombre_cliente(order, shipment=None):
    shipment = shipment or {}
    buyer = order.get("buyer") or {}
    receiver_address = shipment.get("receiver_address") or {}

    candidatos = [
        receiver_address.get("receiver_name"),
        receiver_address.get("recipient_name"),
        shipment.get("receiver_name"),
        order.get("receiver_name"),
        order.get("recipient_name"),
    ]

    nombre_buyer = " ".join([
        str(buyer.get("first_name") or "").strip(),
        str(buyer.get("last_name") or "").strip(),
    ]).strip()
    candidatos.append(nombre_buyer)

    for candidato in candidatos:
        valor = str(candidato or "").strip()
        if valor:
            return valor

    return str(buyer.get("nickname") or "Cliente Mercado Libre").strip()


def ml_mapear_tipo(order, shipment):
    shipping = order.get("shipping") or {}
    mode = str((shipping.get("mode") or shipment.get("mode") or "")).lower().strip()
    logistic_type = str((shipment.get("logistic_type") or shipping.get("logistic_type") or "")).lower().strip()

    if mode == "custom":
        return "Acordás la Entrega"

    if mode in ["me1", "me2", "fulfillment", "cross_docking", "drop_off"]:
        return "Mercado Envíos"

    if logistic_type in ["fulfillment", "cross_docking", "drop_off", "xd_drop_off", "self_service"]:
        return "Mercado Envíos"

    return "Mercado Envíos" if shipping.get("id") else "Acordás la Entrega"


def ml_mapear_tipo_entrega(order, shipment):
    shipping_option = shipment.get("shipping_option") or {}
    delivery_type = str((shipping_option.get("delivery_type") or "")).lower().strip()
    receiver_address = shipment.get("receiver_address") or {}

    if delivery_type == "pickup":
        return "Sucursal"

    if receiver_address.get("address_line"):
        return "Domicilio"

    return ""


def ml_aplicar_datos_envio(pedido, order, shipment):
    shipping = order.get("shipping") or {}
    receiver_address = shipment.get("receiver_address") or {}
    city = receiver_address.get("city") or {}
    state = receiver_address.get("state") or {}

    pedido.ml_shipping_id = str(shipping.get("id") or shipment.get("id") or pedido.ml_shipping_id or "").strip()
    pedido.ml_logistic_type = str(shipment.get("logistic_type") or shipping.get("logistic_type") or pedido.ml_logistic_type or "").strip()
    pedido.ml_shipping_mode = str(shipment.get("mode") or shipping.get("mode") or pedido.ml_shipping_mode or "").strip()

    pedido.ml_tipo = ml_mapear_tipo(order, shipment)
    pedido.tipo_entrega = ml_mapear_tipo_entrega(order, shipment)

    pedido.seguimiento = (
        shipment.get("tracking_number")
        or shipment.get("tracking_method")
        or pedido.seguimiento
    )

    if pedido.ml_tipo == "Mercado Envíos":
        pedido.empresa_envio = "Mercado Envíos"

    pedido.direccion = receiver_address.get("address_line") or pedido.direccion
    pedido.codigo_postal = receiver_address.get("zip_code") or pedido.codigo_postal
    pedido.localidad = city.get("name") or pedido.localidad
    pedido.provincia = state.get("name") or pedido.provincia
    pedido.sucursal_nombre = receiver_address.get("agency_name") or pedido.sucursal_nombre
    aplicar_default_tipo_entrega(pedido)
    if pedido.sucursal_nombre and es_ml_acordas_via_cargo(pedido):
        pedido.tipo_entrega = "Sucursal"
    pedido.ml_shipping_status = shipment.get("status") or shipping.get("status") or pedido.ml_shipping_status

    if pedido.ml_tipo == "Mercado Envíos" and pedido.ml_shipping_id:
        if not pedido.etiqueta_archivo or not etiqueta_archivo_local_disponible(pedido.etiqueta_archivo):
            nombre_pdf = ml_guardar_etiqueta_pdf(pedido.ml_shipping_id)
            if nombre_pdf:
                pedido.etiqueta_archivo = os.path.basename(str(nombre_pdf))


def ml_pedido_existente_por_order_id(order_id):
    if not order_id:
        return None

    pedido = (
        Pedido.query
        .filter_by(canal="Mercado Libre", id_venta=order_id)
        .order_by(Pedido.id.asc())
        .first()
    )

    if pedido:
        return pedido

    return (
        Pedido.query
        .filter_by(id_venta=order_id)
        .order_by(Pedido.id.asc())
        .first()
    )

def ml_pedido_existente_operativo(order, shipment=None):
    """
    APB Mercado Libre:
    - Mercado Envíos se opera por paquete/envío.
      Un pack/shipment puede contener varias órdenes/items.
    - Acordás la Entrega sigue operando por order_id.
    """

    order = order or {}
    shipment = shipment or {}

    order_id = str(order.get("id") or "").strip()
    pack_id = str(order.get("pack_id") or "").strip()

    shipping = order.get("shipping") or {}
    shipping_id = str(
        shipping.get("id")
        or shipment.get("id")
        or ""
    ).strip()

    if ml_es_mercado_envios_order(order, shipment):

        if pack_id:
            pedido = (
                Pedido.query
                .filter_by(
                    canal="Mercado Libre",
                    ml_pack_id=pack_id,
                )
                .order_by(Pedido.id.asc())
                .first()
            )

            if pedido:
                return pedido

        if shipping_id:
            pedido = (
                Pedido.query
                .filter_by(
                    canal="Mercado Libre",
                    ml_shipping_id=shipping_id,
                )
                .order_by(Pedido.id.asc())
                .first()
            )

            if pedido:
                return pedido

    return ml_pedido_existente_por_order_id(order_id)


def ml_logistica_no_operable(order, shipment):
    return ml_logistica_no_operable_service(
        order,
        shipment,
    )


def ml_es_envio_full(order, shipment):
    return ml_es_envio_full_service(
        order,
        shipment,
        ml_logistica_no_operable,
    )


def ml_es_mercado_envios_order(order, shipment=None):
    return ml_es_mercado_envios_order_service(
        order,
        shipment,
        ml_mapear_tipo,
    )


def ml_envio_ya_despachado(order, shipment=None):
    return ml_envio_ya_despachado_service(
        order,
        shipment,
    )


CLAIM_ESTADOS_BLOQUEANTES = {"opened", "under_review", "mediating", "claim_opened"}
# Estados de reclamo cerrado con reembolso — también bloquean operación
CLAIM_ESTADOS_REEMBOLSO = {"closed", "resolved", "refunded", "buyer_won"}


def ml_obtener_claim_de_order(order_id, pack_id=None):
    return ml_obtener_claim_de_order_service(
        order_id,
        pack_id=pack_id,
        ml_api_get=ml_api_get,
    )


def ml_marcar_claim_en_pedido(
    pedido,
    claim,
):
    return ml_marcar_claim_en_pedido_service(
        pedido,
        claim,
    )


def ml_sync_claims_pedidos_operativos():
    estados_operativos = [
        Estado.CARGANDO,
        Estado.ETIQUETA_LISTA,
        Estado.ETIQUETA_IMPRESA,
        Estado.EMBALADO,
        Estado.DESPACHADO,
        Estado.VERIFICAR_DESTINO,
        Estado.LISTO_RETIRAR,
        Estado.DEMORA,
        Estado.RECLAMO,
        "Con reclamo por demora",
    ]

    return ml_sync_claims_pedidos_operativos_service(
        Pedido,
        db,
        cuenta_ml_actual,
        ml_obtener_claim_de_order,
        ml_marcar_claim_en_pedido,
        estados_operativos,
    )


def ml_pedido_tiene_claim(pedido):
    return ml_pedido_tiene_claim_service(
        pedido
    )


def ml_validar_orden_operable_antes_de_despacho(pedido):
    return ml_validar_orden_operable_antes_de_despacho_service(
        pedido,
        db,
        ml_obtener_order,
        ml_obtener_shipment,
        ml_obtener_claim_de_order,
        ml_marcar_claim_en_pedido,
    )


def ml_preparar_etiqueta_mercado_envios(
    order,
    shipment=None,
):
    return ml_preparar_etiqueta_mercado_envios_service(
        order,
        shipment,
        ml_guardar_etiqueta_pdf,
    )


def ml_estado_order(order):
    return ml_estado_order_service(order)


def ml_estado_shipment(
    order=None,
    shipment=None,
):
    return ml_estado_shipment_service(
        order,
        shipment,
    )


def ml_order_esta_entregado(
    order,
    shipment=None,
):
    return ml_order_esta_entregado_service(
        order,
        shipment,
        ml_estado_order,
        ml_estado_shipment,
    )


def ml_pedido_esta_ignorado(order_id):
    return ml_pedido_esta_ignorado_service(
        order_id,
        PedidoIgnoradoML,
    )


def ml_registrar_pedido_ignorado(
    pedido,
    motivo="eliminado_manual",
):
    return ml_registrar_pedido_ignorado_service(
        pedido,
        motivo,
        PedidoIgnoradoML,
        db,
        usuario=session.get("username") or "sistema",
    )


def ml_registrar_order_ignorado(
    order_id,
    motivo="omitido_por_sync_ml",
):
    return ml_registrar_order_ignorado_service(
        order_id,
        motivo,
        PedidoIgnoradoML,
        db,
        usuario=session.get("username") or "sistema",
    )


def ml_marcar_pedido_finalizado_por_entrega(
    pedido,
    order,
    shipment=None,
):
    return ml_marcar_pedido_finalizado_por_entrega_service(
        pedido,
        order,
        shipment,
        ml_estado_order,
        ml_estado_shipment,
    )


def ml_order_debe_omitirse(order, shipment=None):
    return ml_order_debe_omitirse_service(
        order,
        shipment,
        ml_pedido_esta_ignorado,
        ml_order_esta_entregado,
        ml_estado_order,
        ml_logistica_no_operable,
    )


def ml_borrar_pedido_importado_si_corresponde(
    pedido,
):
    return ml_borrar_pedido_importado_si_corresponde_service(
        pedido,
        Estado,
    )


def ml_upsert_pedido_desde_order(order):
    order_id = str(order.get("id") or "").strip()

    shipment = ml_obtener_shipment(
        (order.get("shipping") or {}).get("id")
    )

    prevalidacion = ml_prevalidar_importacion_order_service(
        order,
        shipment,
        ml_pedido_esta_ignorado,
        ml_order_esta_entregado,
        ml_pedido_existente_operativo,
        ml_registrar_order_ignorado,
        ml_marcar_pedido_finalizado_por_entrega,
        ml_order_debe_omitirse,
        ml_borrar_pedido_importado_si_corresponde,
        ml_es_mercado_envios_order,
        ml_envio_ya_despachado,
        ml_preparar_etiqueta_mercado_envios,
    )

    if not prevalidacion.get("continuar"):
        return (
            prevalidacion.get("pedido"),
            prevalidacion.get("creado", False),
            prevalidacion.get("motivo", ""),
        )

    etiqueta_ml_preparada = (
        prevalidacion.get("etiqueta_ml_preparada")
        or ""
    )

    # APB ML:
    # Mercado Envíos se opera por pack_id.
    # Acordás sigue usando order_id.
    id_operativo_ml = order_id

    if ml_es_mercado_envios_order(order, shipment):
        pack_operativo = str(order.get("pack_id") or "").strip()

        if pack_operativo:
            id_operativo_ml = pack_operativo

    billing_info = ml_obtener_billing_info(order_id)

    pedido, creado = ml_preparar_pedido_base_importacion_service(
        order,
        shipment,
        id_operativo_ml,
        etiqueta_ml_preparada,
        Pedido,
        db,
        ml_nombre_cliente,
        ml_es_mercado_envios_order,
        ml_pedido_existente_operativo,
        ml_aplicar_datos_envio,
        ml_aplicar_apb_en_pedido,
        billing_info=billing_info,
    )   

    ml_sincronizar_items_pedido_service(
        pedido,
        order,
        shipment,
        PedidoItem,
        db,
        ml_es_mercado_envios_order,
    )

    estado_anterior = pedido.estado
    actualizar_estado_automatico(pedido)

    if not creado and estado_anterior != pedido.estado and estado_anterior != "Cargando Pedido":
        pedido.estado = estado_anterior

    ml_intentar_contacto_inicial_acordas_service(
        pedido,
        creado,
        es_ml_acordas_entrega,
        ml_auto_enviar_contacto_inicial_acordas,
    )

    return pedido, creado, ""

def ml_borrar_pedidos_ml_cargando_importados():
    pedidos = (
        Pedido.query
        .filter(
            Pedido.estado == "Cargando Pedido",
            or_(
                Pedido.origen == "mercadolibre",
                Pedido.canal == "Mercado Libre"
            )
        )
        .order_by(Pedido.id.asc())
        .all()
    )

    total = len(pedidos)

    for pedido in pedidos:
        db.session.delete(pedido)

    db.session.commit()
    return total


def ml_limpiar_pedidos_ml_no_operables_existentes():
    return ml_limpiar_pedidos_ml_no_operables_existentes_service(
        Pedido,
        ml_obtener_order,
        ml_obtener_shipment,
        ml_order_esta_entregado,
        ml_estado_order,
        ml_estado_shipment,
        ml_order_debe_omitirse,
        ml_borrar_pedido_importado_si_corresponde,
    )


def ml_sync_manual(limit=20, incluir_auxiliares=False):
    cuenta = cuenta_ml_actual()
    if not cuenta:
        raise ValueError("No hay cuenta de Mercado Libre conectada.")

    eliminados_existentes, detalles_eliminados = ml_limpiar_pedidos_ml_no_operables_existentes()

    orders = ml_obtener_orders_recientes(cuenta, limit=limit)
    resultado_sync = (
        ml_procesar_orders_sync_service(
            orders,
            ml_upsert_pedido_desde_order,
        )
    )

    creados = resultado_sync["creados"]
    actualizados = resultado_sync["actualizados"]
    omitidos = resultado_sync["omitidos"]

    errores = list(detalles_eliminados)
    errores.extend(
        resultado_sync["errores"]
    )

    mercado_envios_sin_etiqueta = (
        resultado_sync["me_sin_etiqueta"]
    )

    mercado_envios_sin_etiqueta_ids = (
        resultado_sync["me_sin_etiqueta_ids"]
    )

    mensajes_pendientes = 0
    claims_marcados = 0

    if incluir_auxiliares:
        mensajes_pendientes = ml_sync_mensajes_pendientes_pedidos()
        claims_marcados = ml_sync_claims_pedidos_operativos()

    resultado = (
        ml_actualizar_resumen_sync_service(
            cuenta,
            orders,
            creados,
            actualizados,
            omitidos,
            eliminados_existentes,
            mensajes_pendientes,
            claims_marcados,
            errores,
            mercado_envios_sin_etiqueta,
            mercado_envios_sin_etiqueta_ids,
            session,
        )
    )

    db.session.commit()

    return resultado


def ia_datos_detectados_pedido(pedido):
    if not pedido or not getattr(pedido, "ia_datos_detectados", None):
        return {}
    data = ia_json_loads_seguro(pedido.ia_datos_detectados)
    return data if isinstance(data, dict) else {}


def ia_faltantes_pedido(pedido):
    if not pedido or not getattr(pedido, "ia_faltantes", None):
        return []
    data = ia_json_loads_seguro(pedido.ia_faltantes)
    return data if isinstance(data, list) else []



def ml_conversacion_cortada_para_handoff_wa(pedido, motivo_handoff=""):
    """Check APB para permitir ML -> WhatsApp con datos faltantes.

    WhatsApp puede continuar la recolección con faltantes solo si Mercado Libre
    dejó de ser un canal útil o seguro. Si ML está activo y el cliente viene
    respondiendo, la recolección debe seguir por ML.
    """
    if not pedido:
        return False, "sin_pedido"

    if getattr(pedido, "ia_ultimo_timeout_operador", None):
        return True, "timeout_ml_registrado"

    if getattr(pedido, "ia_requiere_operador", False):
        return True, "requiere_operador"

    canal_ia = str(getattr(pedido, "ia_canal_activo", "") or "").strip().lower()
    if canal_ia and canal_ia not in ["ml", "mercadolibre", "mercado_libre"]:
        return True, f"canal_ia_no_ml:{canal_ia}"

    try:
        estado_conv = obtener_estado_conversacional(
            pedido,
            crear_si_no_existe=False,
        )
    except Exception:
        estado_conv = None

    if estado_conv:
        canal_conv = str(getattr(estado_conv, "canal_activo", "") or "").strip().lower()
        if canal_conv and canal_conv not in ["ml", "mercadolibre", "mercado_libre"]:
            return True, f"canal_conversacional_no_ml:{canal_conv}"

        if getattr(estado_conv, "bot_pausado", False):
            return True, "bot_pausado"

        if getattr(estado_conv, "takeover_activo", False):
            return True, "takeover_operador"

    motivo_txt = str(motivo_handoff or "").strip().lower()
    motivos_corte = [
        "timeout",
        "bloqueado",
        "blocked",
        "rechazado",
        "fallo_ml",
        "error_ml",
        "ml_no_disponible",
        "canal_no_disponible",
    ]

    if motivo_txt and any(m in motivo_txt for m in motivos_corte):
        return True, f"motivo_handoff:{motivo_handoff}"

    return False, "ml_activo_sigue_recolectando"



def wa_auto_iniciar_desde_ml_si_corresponde(pedido, faltantes=None, motivo=""):
    """Disparador APB: ML inicia, WhatsApp continúa cuando corresponde.

    Reglas:
    - Solo Mercado Libre / Acordás la Entrega.
    - Solo si ya hubo contacto inicial por ML (`contacto_iniciado=True`).
    - Solo si hay teléfono normalizado.
    - Si hay faltantes, WA solo toma la posta cuando ML está cortado.
    - Si no hay faltantes, WA puede continuar con datos completos.
    - No pisa conversaciones WA ya iniciadas ni operador_manual.
    - No actúa sobre pedidos cerrados/finalizados/cancelados.
    """
    if not pedido or not es_ml_acordas_entrega(pedido):
        return False, "no_aplica"

    if os.getenv("WA_AUTO_DESDE_ML", "1").strip().lower() in ["0", "false", "no", "off"]:
        return False, "apagado"

    if not getattr(pedido, "contacto_iniciado", False):
        return False, "ml_no_iniciado"

    from services.canal_manager import (
        puede_hacer_handoff_ml_a_whatsapp,
    )

    permitido_handoff, motivo_handoff = (
        puede_hacer_handoff_ml_a_whatsapp(
            pedido
        )
    )

    if not permitido_handoff:
        return False, motivo_handoff

    tel = normalizar_telefono(getattr(pedido, "telefono", ""))
    if not tel or len(tel) < 12:
        return False, "sin_telefono_valido"

    faltantes_limpios = []
    for campo in (faltantes or ia_faltantes_pedido(pedido) or []):
        campo = str(campo or "").strip()
        if not campo:
            continue
        if campo == "telefono" and tel:
            continue
        if campo in ["localidad", "provincia"] and getattr(pedido, campo, None):
            continue
        if campo not in faltantes_limpios:
            faltantes_limpios.append(campo)

    if faltantes_limpios:
        ml_cortado, motivo_corte_ml = ml_conversacion_cortada_para_handoff_wa(
            pedido,
            motivo_handoff=motivo_handoff,
        )

        if not ml_cortado:
            try:
                resumen = (pedido.ia_resumen or "").strip()
                marca = (
                    "ML sigue recolectando datos; WA no iniciado por faltantes: "
                    + ", ".join(faltantes_limpios)
                )
                if marca not in resumen:
                    pedido.ia_resumen = f"{resumen} | {marca}".strip(" |")[:1000]
                db.session.commit()
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass

            print(
                f"[WA-AUTO-ML] NO inicia WA pedido #{getattr(pedido, 'id', '')}: "
                f"ML activo sigue recolectando ({', '.join(faltantes_limpios)})"
            )
            return False, motivo_corte_ml

    try:
        if faltantes_limpios:
            from modules.whatsapp.flows import wa_iniciar_desde_ml

            ok = wa_iniciar_desde_ml(pedido)

            accion = "Inició WhatsApp desde ML"
            detalle_extra = (
                "handoff ML→WA con ML cortado | "
                + ", ".join(faltantes_limpios)
            )
        else:
            from modules.whatsapp.flows import wa_cerrar_datos_completos, wa_iniciar_cross_sell
            ok = wa_cerrar_datos_completos(pedido)
            accion = "Inició WhatsApp con datos completos"
            detalle_extra = "datos completos"
            try:
                wa_iniciar_cross_sell(pedido)
            except Exception as cross_error:
                print(f"[WA-AUTO-ML] Cross-sell no iniciado pedido #{getattr(pedido, 'id', '')}: {cross_error}")

        if ok:
            pedido.wa_ultimo_contacto = datetime.utcnow()
            resumen = (pedido.ia_resumen or "").strip()
            marca = "WA iniciado automáticamente desde ML"

            # APB UX: avisar una sola vez por ML que el canal operativo pasa a WhatsApp.
            # No bloquea el flujo si Mercado Libre rechaza/falla el mensaje.
            marca_transicion_ml = "ML avisó migración a WhatsApp"
            if marca_transicion_ml not in resumen:
                try:
                    texto_transicion_ml = "Te escribimos por WhatsApp para coordinar el envío."

                    # ---------------------------------------------------
                    # APB CANAL MANAGER
                    # ---------------------------------------------------

                    permitido, motivo = puede_enviar_mensaje(
                        pedido=pedido,
                        canal="ml",
                        texto=texto_transicion_ml,
                    )

                    if not permitido:
                        print(
                            f"[CANAL-MANAGER] ML bloqueado pedido #{pedido.id}: {motivo}"
                        )
                    else:
                        ml_enviar_mensaje_acordas(
                            pedido,
                            texto_transicion_ml,
                        )

                        registrar_envio_automatico(
                            pedido=pedido,
                            canal="ml",
                            texto=texto_transicion_ml,
                        )

                        resumen = f"{resumen} | {marca_transicion_ml}".strip(" |")

                except Exception as e:
                    print(
                        f"[WA-AUTO-ML] No se pudo avisar migración por ML "
                        f"pedido #{getattr(pedido, 'id', '')}: {e}"
                    )

            pedido.ia_resumen = f"{resumen} | {marca}".strip(" |") if marca not in resumen else resumen
            try:
                pedido.ml_mensajes_pendientes = False
                pedido.ml_mensajes_pendientes_count = 0
            except Exception:
                pass
            db.session.commit()
            try:
                registrar_auditoria(
                    accion=accion,
                    entidad="pedido",
                    entidad_id=str(pedido.id),
                    detalle=f"Origen ML/Acordás. Teléfono: {tel}. {detalle_extra}. Motivo: {motivo}",
                )
            except Exception as audit_error:
                print(f"[WA-AUTO-ML] No se pudo auditar pedido #{getattr(pedido, 'id', '')}: {audit_error}")
            print(f"[WA-AUTO-ML] OK pedido #{getattr(pedido, 'id', '')}: {accion} ({detalle_extra})")
            return True, "enviado"

        return False, "wa_no_enviado"
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"[WA-AUTO-ML] Error pedido #{getattr(pedido, 'id', '')}: {e}")
        return False, str(e)


def ia_etiqueta_faltante(campo):
    mapa = {
        "nombre": "Nombre",
        "apellido": "Apellido",
        "dni": "DNI",
        "telefono": "Teléfono",
        "direccion": "Dirección completa",
        "localidad": "Localidad",
        "codigo_postal": "Código postal",
    }
    return mapa.get(str(campo or "").strip(), str(campo or "").replace("_", " ").capitalize())


def ia_generar_respuesta_faltantes_pedido(pedido):
    """Fase 4.5 segura: genera texto humano para pedir faltantes. No envía nada por sí sola."""
    if not pedido or not es_ml_acordas_entrega(pedido):
        return ""
    if getattr(pedido, "ia_requiere_operador", False) or pedido.ia_recolector_estado == "requiere_operador":
        return ""

    faltantes = ia_faltantes_pedido(pedido)
    if not faltantes:
        return ""

    datos = ia_datos_detectados_pedido(pedido)
    nombre_raw = str(datos.get("nombre") or "").strip()
    nombre_corto = nombre_raw.split()[0] if nombre_raw else ""
    saludo = f"Gracias, {nombre_corto} 😊" if nombre_corto else "Gracias 😊"
    lineas = [f"- {ia_etiqueta_faltante(c)}" for c in faltantes]
    bloque_faltantes = "\n".join(lineas)

    resumen = str(getattr(pedido, "ia_resumen", "") or "").lower()

    # Detectores de intención. Importante: usamos frases específicas para no disparar textos largos
    # cuando el comprador simplemente manda datos incompletos.
    resumen_ml_explicito = any(k in resumen for k in [
        "datos en mercado libre",
        "datos están en mercado libre",
        "datos estan en mercado libre",
        "datos ya están en mercado libre",
        "datos ya estan en mercado libre",
        "son los mismos de la compra",
        "datos de mi cuenta",
    ])

    pregunta_por_que = any(k in resumen for k in [
        "por qué", "por que", "pide explicación", "pide explicacion",
        "por qué pedimos", "por que pedimos", "por qué piden", "por que piden"
    ])

    pregunta_costo_envio = any(k in resumen for k in [
        "costo de envío", "costo de envio", "cuánto sale", "cuanto sale",
        "sale el envío", "sale el envio", "valor del envío", "valor del envio"
    ])

    # Diferenciar intención:
    # - "cuándo lo envían / despachan" => falta acción de Fierro; empujar a completar datos.
    # - "cuánto tarda / demora" => informar plazo habitual desde el despacho.
    pregunta_cuando_sale = any(k in resumen for k in [
        "cuándo lo envían", "cuando lo envian",
        "cuándo envían", "cuando envian",
        "cuándo lo mandan", "cuando lo mandan",
        "cuándo despachan", "cuando despachan",
        "cuando la despachan", "cuándo la despachan",
        "cuando la envias", "cuándo la envias",
        "cuando la envían", "cuándo la envían",
        "cuando lo envias", "cuándo lo envias",
        "fecha de envío", "fecha de envio",
        "cuando sale", "cuándo sale",
    ])

    pregunta_cuanto_tarda = any(k in resumen for k in [
        "cuánto tarda", "cuanto tarda",
        "cuánto demora", "cuanto demora",
        "demora", "tiempo de entrega",
        "cuándo llega", "cuando llega",
        "cuando me llega", "cuándo me llega",
    ])

    cliente_dice_ya_los_pase = any(k in resumen for k in [
        "ya los pasé", "ya los pase", "ya pasó", "ya paso", "ya envié", "ya envie"
    ])

    # Solo si el cliente pide explícitamente llamada/WhatsApp. No usar "telefono" solo,
    # porque muchas veces aparece en el resumen simplemente porque el comprador pasó su teléfono.
    pide_llamada_o_whatsapp = any(k in resumen for k in [
        "llamada", "llamar", "llamame", "llámame", "hablar por whatsapp",
        "te paso mi whatsapp", "por whatsapp", "mandame whatsapp", "mandame un whatsapp"
    ])

    hay_contexto_especial = any([
        resumen_ml_explicito,
        pregunta_por_que,
        pregunta_costo_envio,
        pregunta_cuando_sale,
        pregunta_cuanto_tarda,
        cliente_dice_ya_los_pase,
        pide_llamada_o_whatsapp,
    ])

    # Caso muy común: el comprador colaboró y solo quedó 1 dato pendiente.
    # Respuesta ultra corta y humana, sin explicación extra.
    if len(faltantes) == 1 and not hay_contexto_especial:
        etiqueta = ia_etiqueta_faltante(faltantes[0]).strip().lower()
        articulo = "el"
        if etiqueta in ["localidad", "dirección", "direccion"]:
            articulo = "la"
        elif etiqueta.startswith("código") or etiqueta.startswith("codigo"):
            articulo = "el"
        elif etiqueta.startswith("teléfono") or etiqueta.startswith("telefono"):
            articulo = "el"
        elif etiqueta.startswith("dni") or etiqueta.startswith("documento"):
            articulo = "el"

        if nombre_corto:
            return f"Excelente, gracias {nombre_corto} 😊\n\nSolo me falta {articulo} {etiqueta} para completar los datos."
        return f"Excelente, gracias 😊\n\nSolo me falta {articulo} {etiqueta} para completar los datos."

    partes = []

    if resumen_ml_explicito:
        partes.append(
            "En esta modalidad de Mercado Libre (Acordás la entrega), los datos cargados en la compra no nos aparecen completos para coordinar el envío."
        )

    if pregunta_por_que:
        partes.append("Te pedimos estos datos para coordinar bien el envío y evitar errores en la entrega.")

    if pregunta_costo_envio:
        partes.append("El envío es sin cargo.")

    if pregunta_cuando_sale:
        partes.append("Lo despachamos apenas nos confirmes estos datos.")

    if pregunta_cuanto_tarda:
        partes.append("Una vez despachado, suele tardar entre 3 y 5 días hábiles.")

    if cliente_dice_ya_los_pase:
        partes.append("Puede ser que haya llegado parte de la información, pero todavía falta completar estos datos.")

    if pide_llamada_o_whatsapp:
        partes.append("Por este medio podemos coordinar más rápido y dejar la información asentada en la compra.")

    if partes:
        texto = (
            saludo
            + "\n\n"
            + "\n\n".join(partes)
            + "\n\nPara avanzar con el envío nos falta:\n\n"
            + bloque_faltantes
            + "\n\nCon eso ya lo despachamos."
        )
    else:
        texto = (
            saludo
            + "\n\nPara avanzar con el envío nos falta:\n\n"
            + bloque_faltantes
            + "\n\nCon eso ya lo despachamos."
        )

    # ML postventa suele ser sensible a mensajes largos. Lo mantenemos compacto y APB.
    if len(texto) > 650:
        texto = texto[:647] + "..."
    return texto

def ia_generar_cta_operador_pedido(pedido):
    """Genera una sugerencia con CTA cuando la IA decide que requiere operador. No envía nada automáticamente."""
    if not pedido or not es_ml_acordas_entrega(pedido):
        return ""
    if not (getattr(pedido, "ia_requiere_operador", False) or pedido.ia_recolector_estado == "requiere_operador"):
        return ""

    resumen = str(getattr(pedido, "ia_resumen", "") or "").lower()

    if "cancel" in resumen:
        return "Entendemos. Para poder gestionarlo correctamente, confirmá por este medio si querés cancelar la compra y lo revisa un operador a la brevedad."

    if any(k in resumen for k in ["retiro", "retirar", "cambio de modalidad", "cambiar modalidad"]):
        return "Perfecto. Para coordinar ese cambio necesitamos revisarlo manualmente. Confirmá si querés retirar personalmente o indicá cómo preferís recibirlo, y un operador lo revisa."

    if any(k in resumen for k in ["enojo", "insulto", "conflicto", "reclamo", "problema"]):
        return "Entendemos tu situación y queremos ayudarte. Un operador va a revisar el caso. Si podés, dejanos más detalle de lo ocurrido para resolverlo más rápido."

    return "Para darte una respuesta correcta necesitamos revisarlo manualmente. Un operador va a tomar el caso. Si podés, dejanos más detalles así avanzamos más rápido."


def ia_respuesta_faltantes_ya_enviada(pedido, texto):

    if not pedido or not texto:
        return False

    ultima_enviada = getattr(
        pedido,
        "ia_ultima_respuesta_enviada",
        None,
    )

    if not ultima_enviada:
        return False

    mismo_texto = (
        str(
            getattr(
                pedido,
                "ia_respuesta_enviada_hash",
                "",
            ) or ""
        )
        == ia_hash_texto(texto)
    )

    if not mismo_texto:
        return False

    # APB anti-acoso:
    # aunque el scheduler relea el mensaje,
    # no volver a mandar exactamente
    # la misma respuesta automática.

    segundos = ia_segundos_operativos_entre(
        ultima_enviada,
        datetime.utcnow(),
    )

    if segundos < IA_TIMEOUT_RESPUESTA_SEGUNDOS:
        return True

    # Si ya pasaron 2 hs operativas:
    # no insistir.
    # Escalar a operador.

    pedido.ia_requiere_operador = True
    pedido.ml_mensajes_pendientes = True

    resumen = (pedido.ia_resumen or "").strip()

    marca = (
        "BOT frenado: respuesta automática repetida, "
        "requiere operador"
    )

    if marca not in resumen:
        pedido.ia_resumen = (
            f"{resumen} | {marca}"
        ).strip(" |")[:1000]

    return True


@app.context_processor
def inyectar_contexto_global():
    return {
        "usuario_logueado": usuario_actual(),
        "rol_actual": rol_actual(),
        "titulo_inicio_por_rol": titulo_inicio_por_rol,
        "subtitulo_inicio_por_rol": subtitulo_inicio_por_rol,
        "puede_crear_pedido": puede_crear_pedido,
        "puede_ver_historico": puede_ver_historico,
        "puede_administrar_integraciones": puede_administrar_integraciones,
        "cuenta_ml_actual": cuenta_ml_actual,
        "puede_editar_pedido": puede_editar_pedido,
        "puede_eliminar_pedido": puede_eliminar_pedido,
        "puede_ver_pedido": puede_ver_pedido,
        "puede_imprimir_pedido": puede_imprimir_pedido,
        "normalizar_telefono": normalizar_telefono,
        "requiere_contacto_cliente": requiere_contacto_cliente,
        "requiere_cargar_seguimiento": requiere_cargar_seguimiento,
        "tiempo_transcurrido": tiempo_transcurrido,
        "fecha_referencia_estado": fecha_referencia_estado,
        "alertas_operativas": alertas_operativas,
        "semaforo_pedido": semaforo_pedido,
        "accion_principal_pedido": accion_principal_pedido,
        "primer_paso_pendiente_carga": primer_paso_pendiente_carga,
        "ml_datos_apb_pedido": ml_datos_apb_pedido,
        "ml_link_detalle_venta": ml_link_detalle_venta,
        "ml_link_chat_venta": ml_link_chat_venta,
        "ml_pedido_tiene_mensajes_pendientes": ml_pedido_tiene_mensajes_pendientes,
        "ml_pedido_tiene_chat_iniciado": ml_pedido_tiene_chat_iniciado,
        "ml_pedido_tiene_claim": ml_pedido_tiene_claim,
        "fecha_argentina": fecha_argentina,
        "tracking_info_pedido": tracking_info_pedido,
        "link_detalle_venta": link_detalle_venta,
        "tn_tipo_envio_visual": tn_tipo_envio_visual,
        "tn_admin_base_url": tn_admin_base_url,
        "tn_pedido_bloqueado_cancelado": tn_pedido_bloqueado_cancelado,
        "es_andreani_pedido": es_andreani_pedido,
        "es_via_cargo_pedido": es_via_cargo_pedido,
        "es_correo_argentino_pedido": es_correo_argentino_pedido,
        "puede_actualizar_tracking_externo": puede_actualizar_tracking_externo,
        "andreani_configurada": andreani_configurada,
        "andreani_texto_ultimo_evento": andreani_texto_ultimo_evento,
        "andreani_alerta_pedido": andreani_alerta_pedido,
        "generar_mensaje_contacto_ml": generar_mensaje_contacto_ml,
        "ia_datos_detectados_pedido": ia_datos_detectados_pedido,
        "ia_faltantes_pedido": ia_faltantes_pedido,
        "ia_generar_respuesta_faltantes_pedido": ia_generar_respuesta_faltantes_pedido,
        "ia_generar_cta_operador_pedido": ia_generar_cta_operador_pedido,
        "ia_respuesta_faltantes_ya_enviada": ia_respuesta_faltantes_ya_enviada,
    }

@app.route("/health")
def health():
    return {
        "status": "ok",
        "service": "sistema-fierro",
        "timestamp": datetime.utcnow().isoformat()
    }, 200

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500

@app.route("/login", methods=["GET", "POST"])
def login():
    if usuario_actual():
        return redirect(url_for("inicio"))

    error = ""

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        usuario = UsuarioSistema.query.filter_by(username=username).first()

        if not usuario or not usuario.activo or not check_password_hash(usuario.password_hash, password):
            error = "Usuario o contraseña incorrectos."
            try:
                aud = Auditoria(
                    username=username or "sin_usuario",
                    accion="Login fallido",
                    entidad="usuario",
                    entidad_id=username or "",
                    detalle="Intento de ingreso rechazado",
                    ip=(request.headers.get("X-Forwarded-For") or request.remote_addr or "")[:80],
                    metodo=request.method,
                    path=request.path,
                )
                db.session.add(aud)
                db.session.commit()
            except Exception:
                db.session.rollback()
        else:
            session["user_id"] = usuario.id
            session["username"] = usuario.username
            registrar_auditoria("Login correcto", entidad="usuario", entidad_id=usuario.id, detalle=f"Ingreso de {usuario.username}", usuario=usuario)
            return redirect(url_for("inicio"))

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def inicio():
    if rol_actual() == "despacho" and (es_dispositivo_movil() or request.args.get("mobile")):
        return redirect(url_for("despacho_mobile"))

    pedidos = Pedido.query.all()

    cambios = False
    for pedido in pedidos:
        telefono_original = pedido.telefono or ""
        telefono_normalizado = normalizar_telefono(telefono_original)
        if telefono_original and telefono_normalizado and telefono_original != telefono_normalizado:
            pedido.telefono = telefono_normalizado
            cambios = True

        estado_anterior = pedido.estado
        actualizar_estado_automatico(pedido)
        if pedido.estado != estado_anterior:
            cambios = True

    if cambios:
        db.session.commit()

    estados = estados_visibles_inicio()
    if estados is not None:
        pedidos = [p for p in pedidos if p.estado in estados]

    pedidos.sort(key=orden_inicio_pedido)

    ok_feedback = (request.args.get("ok") or "").strip()
    error = (request.args.get("error") or "").strip()

    return render_template(
        "index.html",
        pedidos=pedidos,
        resumen_operativo=resumen_operativo(pedidos),
        accion_sugerida_pedido=accion_sugerida_pedido,
        texto_boton_estado=texto_boton_estado,
        puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,
        ok_feedback=ok_feedback
    )


@app.route("/pedidos-preparacion")
@login_required
def pedidos_preparacion():
    if not puede_ver_pedidos_preparacion():
        return redirect(url_for("inicio"))

    pedidos = Pedido.query.all()

    cambios = False
    for pedido in pedidos:
        telefono_original = pedido.telefono or ""
        telefono_normalizado = normalizar_telefono(telefono_original)
        if telefono_original and telefono_normalizado and telefono_original != telefono_normalizado:
            pedido.telefono = telefono_normalizado
            cambios = True

        estado_anterior = pedido.estado
        actualizar_estado_automatico(pedido)
        if pedido.estado != estado_anterior:
            cambios = True

    if cambios:
        db.session.commit()

    estados = estados_visibles_preparacion()
    pedidos = [p for p in pedidos if p.estado in estados]
    pedidos.sort(key=orden_inicio_pedido)

    ok_feedback = (request.args.get("ok") or "").strip()
    error = (request.args.get("error") or "").strip()

    return render_template(
        "index.html",
        pedidos=pedidos,
        resumen_operativo=resumen_operativo(pedidos),
        accion_sugerida_pedido=accion_sugerida_pedido,
        texto_boton_estado=texto_boton_estado,
        puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,
        ok_feedback=ok_feedback,
        error=error,
        titulo_override="Pedidos en preparación",
        subtitulo_override="Pedidos en instancia de impresión, embalaje y despacho",
    )


@app.route("/despacho-mobile")
@login_required
def despacho_mobile():
    if rol_actual() != "despacho":
        return redirect(url_for("inicio"))

    pedidos = Pedido.query.filter(Pedido.estado.in_(ESTADOS_DESPACHO_OPERATIVO)).all()
    pedidos.sort(key=orden_inicio_pedido)

    return render_template(
        "despacho_mobile.html",
        pedidos=pedidos,
        accion_principal_pedido=accion_principal_pedido,
        accion_sugerida_pedido=accion_sugerida_pedido,
        ok_feedback=(request.args.get("ok") or "").strip(),
    )


def ml_sync_pedido_por_order_id_webhook(order_id):
    """Sincroniza una orden puntual recibida por webhook ML sin esperar la sync general."""
    order_id = str(order_id or "").strip()
    if not order_id:
        return False
    try:
        order = ml_obtener_order(order_id)
        if not order:
            print(f"[WEBHOOK ML] Order vacia o no encontrada: {order_id}")
            return False
        pedido, creado, motivo = ml_upsert_pedido_desde_order(order)

        # Si ML informa que la orden está cancelada y el pedido ya existe en el sistema,
        # actualizarlo a Cancelado automáticamente
        if not pedido and motivo:
            estados_cancelados_ml = {"cancelled", "invalid", "closed"}
            order_status = str((order or {}).get("status") or "").lower().strip()
            if order_status in estados_cancelados_ml:
                pedido_existente = ml_pedido_existente_por_order_id(order_id)
                if pedido_existente and pedido_existente.estado not in ["Cancelado", "Finalizado", "Entregado"]:
                    pedido_existente.estado = "Cancelado"
                    print(f"[WEBHOOK ML] Pedido #{pedido_existente.id} cancelado automáticamente — ML status={order_status}")

        if pedido and ml_order_esta_entregado(order):

            if not pedido.fecha_entregado:
                pedido.fecha_entregado = datetime.utcnow()

            pedido.estado = "Finalizado"

            print(
                f"[WEBHOOK ML] Pedido #{pedido.id} "
                f"finalizado automáticamente por order webhook"
            )

        db.session.commit()

        if pedido:
            print(f"[WEBHOOK ML] Order sincronizada {order_id}. pedido_id={pedido.id} creado={creado} motivo={motivo}")
        else:
            print(f"[WEBHOOK ML] Order omitida {order_id}. motivo={motivo}")

        return True
    except Exception as e:
        db.session.rollback()
        print(f"[WEBHOOK ML] No se pudo sincronizar order {order_id}: {e}")
        return False


def ml_sync_shipment_por_id_webhook(shipment_id):
    """Actualiza datos ML básicos del pedido asociado a un shipment recibido por webhook."""
    shipment_id = str(shipment_id or "").strip()
    if not shipment_id:
        return False
    try:
        shipment = ml_obtener_shipment(shipment_id)
        if not shipment:
            print(f"[WEBHOOK ML] Shipment vacio o no encontrado: {shipment_id}")
            return False
        pedido = (
            Pedido.query
            .filter(
                Pedido.canal == "Mercado Libre",
                or_(
                    Pedido.ml_shipping_id == shipment_id,
                    Pedido.ml_shipping_id == str(shipment_id)
                )
            )
            .order_by(Pedido.id.asc())
            .first()
        )
        if pedido:
            estado_shipping = str(
                shipment.get("status")
                or pedido.ml_shipping_status
                or ""
            ).lower().strip()

            pedido.ml_shipping_status = estado_shipping
            pedido.ml_logistic_type = str(
                shipment.get("logistic_type")
                or pedido.ml_logistic_type
                or ""
            ).strip()
            pedido.ml_shipping_mode = str(
                shipment.get("mode")
                or pedido.ml_shipping_mode
                or ""
            ).strip()
            pedido.ultima_sync_ml = datetime.utcnow()

            # APB Mercado Envíos:
            # Si Mercado Libre informa delivered/fulfilled,
            # el pedido no debe seguir operativo.
            # En Mercado Envíos no hay aviso manual a ML:
            # el estado válido es el del carrier/ML.
            if (
                pedido.ml_tipo == "Mercado Envíos"
                and estado_shipping in ["delivered", "fulfilled"]
                and pedido.estado not in ["Finalizado", "Cancelado"]
            ):
                pedido.estado = "Finalizado"
                pedido.fecha_entregado = (
                    pedido.fecha_entregado
                    or datetime.utcnow()
                )

                aviso = (
                    "ML Mercado Envíos informa entregado. "
                    "Pedido finalizado automáticamente."
                )
                obs = str(pedido.observaciones or "").strip()
                if aviso not in obs:
                    pedido.observaciones = (
                        f"{aviso} {obs}".strip()
                    )[:300]

                print(
                    f"[WEBHOOK ML] Pedido #{pedido.id} finalizado automáticamente "
                    f"por shipment delivered={shipment_id}"
                )

            db.session.commit()
            print(f"[WEBHOOK ML] Shipment actualizado {shipment_id}. pedido_id={pedido.id}")
            return True
        print(
            f"[WEBHOOK ML] Shipment {shipment_id} sin pedido vinculado en Fierro"
        )

        pedido_por_order = (
            Pedido.query
            .filter_by(
                id_venta=str(
                    shipment.get("order_id") or ""
                )
            )
            .first()
        )

        if pedido_por_order:

            print(
                f"[WEBHOOK ML] Shipment {shipment_id} "
                f"re-vinculado por order_id "
                f"pedido=#{pedido_por_order.id}"
            )

            if not pedido_por_order.fecha_entregado:
                pedido_por_order.fecha_entregado = datetime.utcnow()

            pedido_por_order.estado = "Finalizado"

            db.session.commit()

            return True

        return False
    except Exception as e:
        db.session.rollback()
        print(f"[WEBHOOK ML] No se pudo sincronizar shipment {shipment_id}: {e}")
        return False


def ml_marcar_reclamo_webhook(resource):
    """Procesa claims recibidos por webhook ML y los vincula a pedidos Fierro."""
    resource = str(resource or "").strip()
    claim_id = ""

    match = re.search(r"/claims/([^/?#]+)", resource)
    if match:
        claim_id = match.group(1)

    if not claim_id:
        print(f"[WEBHOOK ML] Claim recibido sin claim_id claro. resource={resource}")
        return False

    try:
        claim = ml_api_get(f"/post-purchase/v1/claims/{claim_id}")
        if not claim:
            print(f"[WEBHOOK ML] Claim {claim_id} no encontrado en API")
            return False

        status = str(claim.get("status") or "").lower().strip()
        resource_id = str(
            claim.get("resource_id")
            or claim.get("resource")
            or claim.get("pack_id")
            or ""
        ).strip()
        order_id = str(claim.get("order_id") or "").strip()

        # Algunas respuestas pueden traer order dentro de resource/order.
        resource_obj = claim.get("resource") if isinstance(claim.get("resource"), dict) else {}
        if not order_id and resource_obj:
            order_id = str(resource_obj.get("id") or resource_obj.get("order_id") or "").strip()
        if not resource_id and resource_obj:
            resource_id = str(resource_obj.get("id") or "").strip()

        pedido = None
        for buscar_id in [resource_id, order_id]:
            buscar_id = str(buscar_id or "").strip()
            if not buscar_id:
                continue

            pedido = (
                Pedido.query.filter(Pedido.canal == "Mercado Libre")
                .filter(or_(
                    Pedido.ml_pack_id == buscar_id,
                    Pedido.id_venta == buscar_id,
                ))
                .first()
            )
            if pedido:
                break

        # Último respaldo: si el claim no trajo order claro, consultar búsqueda por claim no sirve;
        # dejamos log exacto para poder mapear el shape real que devuelva ML.
        if not pedido:
            print(
                f"[WEBHOOK ML] Claim {claim_id} sin pedido vinculado. "
                f"status={status} resource_id={resource_id} order_id={order_id} claim={claim}"
            )
            return False

        if status in CLAIM_ESTADOS_BLOQUEANTES:
            ml_marcar_claim_en_pedido(pedido, claim)
        else:
            ml_marcar_claim_en_pedido(pedido, None)

        db.session.commit()
        print(
            f"[WEBHOOK ML] Claim {claim_id} -> pedido #{pedido.id} "
            f"status={status} abierto={pedido.ml_claim_abierto}"
        )
        return True

    except Exception as e:
        db.session.rollback()
        print(f"[WEBHOOK ML] Error procesando claim {claim_id}: {e}")
        return False


@app.route("/ayuda")
@login_required
def ayuda():
    return render_template("ayuda.html")


@app.route("/privacidad")
def privacidad():
    return """
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>Política de Privacidad - Fierro 100% Argento</title></head>
<body style="font-family:Arial,sans-serif;max-width:800px;margin:40px auto;padding:20px;">
<h1>Política de Privacidad</h1>
<p>Última actualización: Mayo 2026</p>
<p>Fierro 100% Argento utiliza WhatsApp Business API para comunicarse con sus clientes en el marco de ventas y logística. Los datos recopilados (nombre, teléfono, dirección de entrega) son utilizados exclusivamente para gestionar pedidos y coordinar envíos.</p>
<p>No compartimos información personal con terceros salvo con las empresas de transporte necesarias para completar la entrega.</p>
<p>Para consultas sobre privacidad contactar a: nauticadelplata@yahoo.com.ar</p>
</body>
</html>
"""


def ml_crear_log_webhook(topic, resource, data):
    try:
        log = WebhookML(
            topic=str(topic or "")[:80],
            resource=str(resource or "")[:300],
            payload=json.dumps(data or {}, ensure_ascii=False)[:5000],
            ok=False,
        )
        db.session.add(log)
        db.session.commit()
        return log.id
    except Exception as e:
        db.session.rollback()
        print(f"[WEBHOOK ML LOG] No se pudo crear log: {e}")
        return None


def ml_cerrar_log_webhook(log_id, ok=True, detalle=""):
    if not log_id:
        return
    try:
        log = WebhookML.query.get(log_id)
        if log:
            log.ok = bool(ok)
            log.detalle = str(detalle or "")[:1000]
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[WEBHOOK ML LOG] No se pudo cerrar log #{log_id}: {e}")


@app.route("/webhook/mercadolibre", methods=["GET", "POST"])
@app.route("/admin/integraciones/mercadolibre/webhook", methods=["GET", "POST"])
def webhook_mercadolibre():
    """
    Webhook ML. No requiere login porque lo llama Mercado Libre.
    Regla APB: siempre responde 200, pero deja log del evento y del resultado.
    """
    if request.method == "GET":
        return "OK", 200

    log_id = None
    try:
        data = request.get_json(silent=True) or {}
        print("[WEBHOOK ML]", data)

        topic = str(data.get("topic") or data.get("type") or "").lower()
        resource = str(data.get("resource") or "").strip()
        log_id = ml_crear_log_webhook(topic, resource, data)
        detalle_log = "sin accion"

        if "message" in topic or "/messages" in resource:
            pack_id = ""
            match_pack = re.search(r"/packs/([^/?#]+)", resource)
            if match_pack:
                pack_id = match_pack.group(1)

            if pack_id:
                pedido = (
                    Pedido.query.filter(Pedido.canal == "Mercado Libre")
                    .filter(or_(
                        Pedido.ml_pack_id == pack_id,
                        Pedido.id_venta == pack_id,
                    ))
                    .first()
                )
                if pedido:
                    tiene, count = ml_sync_mensajes_pedido(pedido)
                    db.session.commit()
                    detalle_log = f"mensaje pack={pack_id} pedido={pedido.id} pendientes={count}"
                    print(f"[WEBHOOK ML] Mensaje pack={pack_id} -> pedido #{pedido.id} pendientes={count}")
                else:
                    detalle_log = f"mensaje pack={pack_id} sin pedido vinculado"
                    print(f"[WEBHOOK ML] Mensaje pack={pack_id} sin pedido vinculado")
            else:
                ids = ml_extraer_ids_mensaje_ml(data)
                if not ids and resource:
                    ids = ml_resolver_ids_desde_recurso_mensaje(resource)

                marcados = ml_marcar_mensajes_pendientes_por_ids(ids, count=1, commit=True)

                if marcados == 0:
                    total = ml_sync_mensajes_pendientes_pedidos()
                    db.session.commit()
                    detalle_log = f"mensaje sin match directo; sync total={total}"
                    print(f"[WEBHOOK ML] Mensaje sin match directo. Sync mensajes total={total}")
                else:
                    detalle_log = f"mensaje vinculado a {marcados} pedido(s): {sorted(ids)}"
                    print(f"[WEBHOOK ML] Mensaje vinculado a {marcados} pedido(s). IDs={sorted(ids)}")

        elif "order" in topic or "/orders/" in resource:
            order_id = ""
            match = re.search(r"/orders/([^/?#]+)", resource)
            if match:
                order_id = match.group(1)
            ok_order = ml_sync_pedido_por_order_id_webhook(order_id)
            detalle_log = f"order {order_id} ok={ok_order}"

        elif "shipment" in topic or "/shipments/" in resource:
            shipment_id = ""
            match = re.search(r"/shipments/([^/?#]+)", resource)
            if match:
                shipment_id = match.group(1)
            ok_ship = ml_sync_shipment_por_id_webhook(shipment_id)
            detalle_log = f"shipment {shipment_id} ok={ok_ship}"

        elif "claim" in topic or "/claims/" in resource:
            ok_claim = ml_marcar_reclamo_webhook(resource)
            detalle_log = f"claim resource={resource} ok={ok_claim}"

        ml_cerrar_log_webhook(log_id, ok=True, detalle=detalle_log)
        return "OK", 200

    except Exception as e:
        db.session.rollback()
        print("[WEBHOOK ML ERROR]", e)
        ml_cerrar_log_webhook(log_id, ok=False, detalle=str(e))
        return "OK", 200


@app.route("/admin/productos", methods=["GET", "POST"])
@login_required
def admin_productos():
    mensaje = ""
    error = ""

    if request.method == "POST":
        archivo = request.files.get("archivo_productos")
        if not archivo or not archivo.filename:
            error = "Tenés que seleccionar un Excel."
        else:
            try:
                cantidad = sincronizar_productos_desde_excel(archivo)
                mensaje = f"Productos actualizados: {cantidad}"
            except Exception as e:
                db.session.rollback()
                error = f"No se pudo importar el Excel: {e}"

    total_productos = Producto.query.count()
    ultimos = Producto.query.order_by(Producto.descripcion.asc()).limit(20).all()

    return render_template(
        "admin_productos.html",
        mensaje=mensaje,
        error=error,
        total_productos=total_productos,
        ultimos=ultimos
    )


@app.route("/admin/usuarios")
@login_required
def admin_usuarios():
    if rol_actual() != "admin":
        return redirect(url_for("inicio"))

    usuarios = UsuarioSistema.query.order_by(UsuarioSistema.activo.desc(), UsuarioSistema.rol.asc(), UsuarioSistema.username.asc()).all()
    return render_template(
        "admin_usuarios.html",
        usuarios=usuarios,
        roles=ROLES_SISTEMA,
        ok_feedback=(request.args.get("ok") or "").strip(),
        error=(request.args.get("error") or "").strip(),
    )


@app.route("/admin/usuarios/nuevo", methods=["POST"])
@login_required
def admin_usuario_nuevo():
    if rol_actual() != "admin":
        return redirect(url_for("inicio"))

    username = (request.form.get("username") or "").strip()
    nombre = (request.form.get("nombre") or "").strip()
    rol = (request.form.get("rol") or "carga").strip()
    password = request.form.get("password") or ""

    if not username or not nombre or not password:
        return redirect(url_for("admin_usuarios", error="Completá usuario, nombre y contraseña."))
    if rol not in ROLES_SISTEMA:
        return redirect(url_for("admin_usuarios", error="Rol inválido."))
    if UsuarioSistema.query.filter_by(username=username).first():
        return redirect(url_for("admin_usuarios", error="Ese usuario ya existe."))

    creador = usuario_actual()
    usuario = UsuarioSistema(
        username=username,
        nombre=nombre,
        rol=rol,
        password_hash=generate_password_hash(password),
        activo=True,
        creado_por=creador.username if creador else "admin",
    )
    db.session.add(usuario)
    db.session.commit()
    registrar_auditoria("Creó usuario", entidad="usuario", entidad_id=usuario.id, detalle=f"Usuario {username} / rol {rol}")
    return redirect(url_for("admin_usuarios", ok="Usuario creado correctamente."))


@app.route("/admin/usuarios/<int:id>/editar", methods=["POST"])
@login_required
def admin_usuario_editar(id):
    if rol_actual() != "admin":
        return redirect(url_for("inicio"))

    usuario = UsuarioSistema.query.get_or_404(id)
    nombre = (request.form.get("nombre") or "").strip()
    rol = (request.form.get("rol") or "").strip()
    password = request.form.get("password") or ""

    if not nombre:
        return redirect(url_for("admin_usuarios", error="El nombre no puede quedar vacío."))
    if rol not in ROLES_SISTEMA:
        return redirect(url_for("admin_usuarios", error="Rol inválido."))

    antes = f"nombre={usuario.nombre}, rol={usuario.rol}, activo={usuario.activo}"
    usuario.nombre = nombre
    usuario.rol = rol
    if password:
        usuario.password_hash = generate_password_hash(password)
        detalle_pass = " Contraseña actualizada."
    else:
        detalle_pass = ""
    db.session.commit()
    registrar_auditoria("Editó usuario", entidad="usuario", entidad_id=usuario.id, detalle=f"Antes: {antes}. Ahora: nombre={nombre}, rol={rol}.{detalle_pass}")
    return redirect(url_for("admin_usuarios", ok="Usuario actualizado correctamente."))


@app.route("/admin/usuarios/<int:id>/toggle", methods=["POST"])
@login_required
def admin_usuario_toggle(id):
    if rol_actual() != "admin":
        return redirect(url_for("inicio"))

    usuario = UsuarioSistema.query.get_or_404(id)
    actual = usuario_actual()
    if actual and usuario.id == actual.id and usuario.activo:
        return redirect(url_for("admin_usuarios", error="No podés desactivar tu propio usuario."))

    usuario.activo = not usuario.activo
    db.session.commit()
    estado = "activado" if usuario.activo else "desactivado"
    registrar_auditoria("Activó/desactivó usuario", entidad="usuario", entidad_id=usuario.id, detalle=f"Usuario {usuario.username} {estado}")
    return redirect(url_for("admin_usuarios", ok=f"Usuario {estado} correctamente."))


@app.route("/admin/auditoria")
@login_required
def admin_auditoria():
    if rol_actual() != "admin":
        return redirect(url_for("inicio"))

    auditorias = Auditoria.query.order_by(Auditoria.fecha.desc()).limit(300).all()
    return render_template("admin_auditoria.html", auditorias=auditorias, ok_feedback="", error="")


@app.route("/admin/integraciones")
@login_required
def admin_integraciones():
    if not puede_administrar_integraciones():
        return redirect(url_for("inicio"))

    cuenta_ml = cuenta_ml_actual()
    faltantes = ml_config_faltante()
    cuenta_tn = cuenta_tn_actual()
    faltantes_tn = tn_config_faltante()
    ultimos_logs_tn = TiendaNubeWebhookLog.query.order_by(TiendaNubeWebhookLog.fecha.desc()).limit(10).all()
    ok_feedback = (request.args.get("ok") or "").strip()
    error = (request.args.get("error") or "").strip()

    return render_template(
        "admin_integraciones.html",
        cuenta_ml=cuenta_ml,
        faltantes=faltantes,
        cuenta_tn=cuenta_tn,
        faltantes_tn=faltantes_tn,
        ultimos_logs_tn=ultimos_logs_tn,
        ok_feedback=ok_feedback,
        error=error,
    )


@app.route("/webhook/tiendanube", methods=["POST"])
def webhook_tiendanube():
    raw_body = request.get_data() or b""
    data = None
    log_id = None
    try:
        if not tn_webhook_firma_valida(raw_body):
            log = TiendaNubeWebhookLog(
                event=request.headers.get("X-Event", "firma_invalida"),
                tn_order_id=None,
                payload=raw_body.decode("utf-8", errors="ignore")[:5000],
                procesado=False,
                error="Firma HMAC inválida"
            )
            db.session.add(log)
            db.session.commit()
            return "Firma inválida", 401

        data = request.get_json(silent=True) or {}
        event = (
            request.headers.get("X-Event")
            or request.headers.get("X-TiendaNube-Topic")
            or data.get("event")
            or data.get("topic")
            or "unknown"
        )
        tn_order_id = tn_extraer_order_id(data)

        log = TiendaNubeWebhookLog(
            event=event,
            tn_order_id=tn_order_id,
            payload=json.dumps(data, ensure_ascii=False),
            procesado=False,
        )
        db.session.add(log)
        db.session.commit()
        log_id = log.id

        if tn_order_id and str(event).startswith("order/"):
            try:
                tn_importar_pedido_por_id(tn_order_id)
                log = TiendaNubeWebhookLog.query.get(log_id)
                if log:
                    log.procesado = True
                    log.error = None
                    db.session.commit()
            except Exception as e:
                db.session.rollback()
                log = TiendaNubeWebhookLog.query.get(log_id)
                if log:
                    log.procesado = False
                    log.error = str(e)
                    db.session.commit()

        return "OK", 200
    except Exception as e:
        db.session.rollback()
        try:
            log = TiendaNubeWebhookLog(
                event=request.headers.get("X-Event", "error"),
                tn_order_id=tn_extraer_order_id(data or {}) if isinstance(data, dict) else None,
                payload=raw_body.decode("utf-8", errors="ignore")[:5000],
                procesado=False,
                error=str(e),
            )
            db.session.add(log)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return f"Error: {str(e)}", 500


@app.route("/admin/integraciones/tiendanube/test", methods=["POST"])
@login_required
def test_tiendanube():
    if not puede_administrar_integraciones():
        return redirect(url_for("inicio"))
    faltantes = tn_config_faltante()
    if faltantes:
        return redirect(url_for("admin_integraciones", error=f"Faltan variables TN: {', '.join(faltantes)}"))
    try:
        orders = tn_http_json("GET", "/orders", params={"per_page": 1})
        cuenta = cuenta_tn_actual()
        if cuenta:
            cuenta.store_id = tn_store_id()
            cuenta.estado_conexion = "conectada"
            cuenta.last_sync_at = datetime.utcnow()
            cuenta.last_sync_status = "test_ok"
            cuenta.last_sync_detail = "Conexión TN OK"
            db.session.commit()
        cantidad = len(orders) if isinstance(orders, list) else 0
        return redirect(url_for("admin_integraciones", ok=f"Conexión Tienda Nube OK. Pedidos leídos de prueba: {cantidad}."))
    except Exception as e:
        cuenta = cuenta_tn_actual()
        if cuenta:
            cuenta.estado_conexion = "error"
            cuenta.last_sync_at = datetime.utcnow()
            cuenta.last_sync_status = "test_error"
            cuenta.last_sync_detail = str(e)
            db.session.commit()
        return redirect(url_for("admin_integraciones", error=f"Falló test Tienda Nube: {e}"))


@app.route("/admin/integraciones/tiendanube/sync", methods=["POST"])
@login_required
def sync_tiendanube():
    if not puede_administrar_integraciones():
        return redirect(url_for("inicio"))
    faltantes = tn_config_faltante()
    if faltantes:
        return redirect(url_for("admin_integraciones", error=f"Faltan variables TN: {', '.join(faltantes)}"))
    try:
        resultado = tn_sync_manual(limit=50)
        mensaje = (
            f"Sync TN OK. Leídos: {resultado['leidos']} | "
            f"Nuevos: {resultado['creados']} | "
            f"Actualizados: {resultado['actualizados']} | "
            f"Omitidos: {resultado['omitidos']}"
        )
        return redirect(url_for("admin_integraciones", ok=mensaje))
    except Exception as e:
        db.session.rollback()
        cuenta = cuenta_tn_actual()
        if cuenta:
            cuenta.last_sync_at = datetime.utcnow()
            cuenta.last_sync_status = "error"
            cuenta.last_sync_detail = str(e)
            db.session.commit()
        return redirect(url_for("admin_integraciones", error=f"Falló sincronización Tienda Nube: {e}"))


@app.route("/admin/integraciones/tiendanube/registrar-webhooks", methods=["POST"])
@login_required
def registrar_webhooks_tiendanube():
    if not puede_administrar_integraciones():
        return redirect(url_for("inicio"))
    faltantes = tn_config_faltante()
    if faltantes:
        return redirect(url_for("admin_integraciones", error=f"Faltan variables TN: {', '.join(faltantes)}"))
    try:
        resultados = tn_registrar_webhooks_sistema_fierro()
        ok_count = sum(1 for r in resultados if r.get("ok"))
        mensaje = f"Webhooks TN solicitados. Creados OK: {ok_count}/{len(resultados)}. Si alguno ya existía, TN puede devolver advertencia sin afectar."
        return redirect(url_for("admin_integraciones", ok=mensaje))
    except Exception as e:
        db.session.rollback()
        return redirect(url_for("admin_integraciones", error=f"No se pudieron registrar webhooks TN: {e}"))


@app.route("/admin/integraciones/tiendanube/reset-prueba", methods=["POST"])
@login_required
def reset_prueba_tiendanube():
    if not puede_administrar_integraciones():
        return redirect(url_for("inicio"))
    try:
        pedidos = Pedido.query.filter(
            Pedido.origen == "tiendanube",
            Pedido.estado == "Cargando Pedido"
        ).all()
        eliminados = len(pedidos)
        for pedido in pedidos:
            db.session.delete(pedido)
        db.session.commit()
        return redirect(url_for("admin_integraciones", ok=f"Pedidos TN de prueba eliminados: {eliminados}."))
    except Exception as e:
        db.session.rollback()
        return redirect(url_for("admin_integraciones", error=f"No se pudieron borrar pedidos TN de prueba: {e}"))


@app.route("/admin/integraciones/mercadolibre/conectar")
@login_required
def conectar_mercadolibre():
    if not puede_administrar_integraciones():
        return redirect(url_for("inicio"))

    faltantes = ml_config_faltante()
    if faltantes:
        return redirect(url_for("admin_integraciones", error=f"Faltan variables: {', '.join(faltantes)}"))

    params = urlencode({
        "response_type": "code",
        "client_id": ml_client_id(),
        "redirect_uri": ml_redirect_uri(),
    })
    return redirect(f"https://auth.mercadolibre.com.ar/authorization?{params}")


@app.route("/admin/integraciones/mercadolibre/callback")
@login_required
def callback_mercadolibre():
    if not puede_administrar_integraciones():
        return redirect(url_for("inicio"))

    error = (request.args.get("error") or "").strip()
    code = (request.args.get("code") or "").strip()

    if error:
        return redirect(url_for("admin_integraciones", error=f"Mercado Libre devolvió error: {error}"))

    if not code:
        return redirect(url_for("admin_integraciones", error="Mercado Libre no devolvió código de autorización."))

    try:
        token_data = ml_exchange_code_for_token(code)
        cuenta = cuenta_ml_actual() or MercadoLibreCuenta()
        ml_guardar_token_en_cuenta(cuenta, token_data)
        if cuenta.id is None:
            db.session.add(cuenta)
        db.session.flush()

        perfil = ml_obtener_usuario_actual()
        cuenta.user_id_ml = str(perfil.get("id") or cuenta.user_id_ml or "")
        cuenta.nickname = perfil.get("nickname") or cuenta.nickname
        cuenta.estado_conexion = "conectada"
        db.session.commit()
        return redirect(url_for("admin_integraciones", ok="Cuenta de Mercado Libre vinculada correctamente."))
    except Exception as e:
        db.session.rollback()
        return redirect(url_for("admin_integraciones", error=f"No se pudo vincular Mercado Libre: {e}"))


@app.route("/admin/integraciones/mercadolibre/desconectar", methods=["POST"])
@login_required
def desconectar_mercadolibre():
    if not puede_administrar_integraciones():
        return redirect(url_for("inicio"))

    cuenta = cuenta_ml_actual()
    if cuenta:
        db.session.delete(cuenta)
        db.session.commit()

    return redirect(url_for("admin_integraciones", ok="Cuenta de Mercado Libre desconectada."))


@app.route("/admin/integraciones/mercadolibre/sync", methods=["POST"])
@login_required
def sync_mercadolibre():
    if not puede_administrar_integraciones():
        return redirect(url_for("inicio"))

    cuenta = cuenta_ml_actual()
    if not cuenta:
        return redirect(url_for("admin_integraciones", error="Primero conectá una cuenta de Mercado Libre."))

    try:
        resultado = ml_sync_manual(
            limit=5,
            incluir_auxiliares=False,
        )
        mensaje = (
            f"Sync ML OK. Leídos: {resultado['leidos']} | "
            f"Nuevos: {resultado['creados']} | "
            f"Actualizados: {resultado['actualizados']} | "
            f"Omitidos: {resultado['omitidos']} | "
            f"Eliminados: {resultado['eliminados']} | "
            f"Mensajes: {resultado.get('mensajes_pendientes', 0)} | "
            f"Reclamos: {resultado.get('claims_marcados', 0)} | "
            f"ME sin etiqueta: {resultado.get('me_sin_etiqueta', 0)}"
        )
        return redirect(url_for("admin_integraciones", ok=mensaje))
    except Exception as e:
        if cuenta:
            cuenta.last_sync_at = datetime.utcnow()
            cuenta.last_sync_status = "error"
            cuenta.last_sync_detail = str(e)
            db.session.commit()
        return redirect(url_for("admin_integraciones", error=f"Falló la sincronización: {e}"))


@app.route("/admin/integraciones/mercadolibre/reset-prueba", methods=["POST"])
@login_required
def reset_prueba_mercadolibre():
    if not puede_administrar_integraciones():
        return redirect(url_for("inicio"))

    try:
        eliminados = ml_borrar_pedidos_ml_cargando_importados()
        return redirect(url_for("admin_integraciones", ok=f"Pedidos ML de prueba eliminados: {eliminados}. Ahora podés sincronizar de nuevo."))
    except Exception as e:
        return redirect(url_for("admin_integraciones", error=f"No se pudieron eliminar pedidos ML de prueba: {e}"))

@app.route("/admin/integraciones/mercadolibre/reset-total", methods=["POST"])
@login_required
def reset_total_mercadolibre():
    if not puede_administrar_integraciones():
        return redirect(url_for("inicio"))

    try:
        pedidos = (
            Pedido.query
            .filter(
                or_(
                    Pedido.origen == "mercadolibre",
                    Pedido.canal == "Mercado Libre"
                )
            )
            .all()
        )
        eliminados = len(pedidos)

        for pedido in pedidos:
            db.session.delete(pedido)

        db.session.commit()
        return redirect(url_for(
            "admin_integraciones",
            ok=f"Reset total ML realizado. Pedidos importados de Mercado Libre eliminados en Fierro: {eliminados}. Ahora podés sincronizar de nuevo."
        ))
    except Exception as e:
        db.session.rollback()
        return redirect(url_for("admin_integraciones", error=f"No se pudo hacer reset total ML: {e}"))


@app.route("/admin/reset_ml")
@login_required
def reset_ml_directo():
    if not puede_administrar_integraciones():
        return redirect(url_for("inicio"))

    try:
        pedidos = (
            Pedido.query
            .filter(
                or_(
                    Pedido.origen == "mercadolibre",
                    Pedido.canal == "Mercado Libre"
                )
            )
            .all()
        )
        eliminados = len(pedidos)

        for pedido in pedidos:
            db.session.delete(pedido)

        db.session.commit()
        return f"OK - pedidos ML importados borrados de Fierro: {eliminados}. No se tocó Mercado Libre."
    except Exception as e:
        db.session.rollback()
        return f"ERROR - no se pudo borrar: {e}", 500



@app.route("/historico")
@login_required
def historico():
    if not puede_ver_historico():
        return redirect(url_for("inicio"))

    pedidos = Pedido.query.filter_by(estado="Finalizado").order_by(Pedido.id.desc()).all()

    return render_template(
        "historico.html",
        pedidos=pedidos
    )


@app.route("/productos")
@login_required
def productos():
    productos_db = Producto.query.order_by(Producto.descripcion.asc()).all()

    if productos_db:
        return jsonify([
            {"sku": p.sku or "", "descripcion": p.descripcion or ""}
            for p in productos_db
        ])

    ruta_excel = os.path.join(app.root_path, "productos.xlsx")
    if os.path.exists(ruta_excel):
        productos = productos_desde_excel(ruta_excel)
        if productos:
            try:
                sincronizar_productos_desde_excel(ruta_excel)
            except Exception as e:
                print("No se pudo sincronizar productos desde Excel:", e)
        return jsonify(productos)

    return jsonify([])


@app.route("/uploads/<path:nombre_archivo>")
@login_required
def ver_etiqueta(nombre_archivo):
    return send_from_directory(app.config["UPLOAD_FOLDER"], nombre_archivo)


@app.route("/pedido/<path:nombre_archivo>")
@login_required
def ver_archivo_pedido_sin_id_compat(nombre_archivo):
    # APB: si por precedencia de rutas entra un ID numérico acá, redirigimos al detalle real.
    # Evita que /pedido/243 sea tratado como archivo.
    if str(nombre_archivo or "").strip().isdigit():
        return redirect(url_for("detalle_pedido", id=int(str(nombre_archivo).strip())))

    # Compatibilidad con links relativos viejos tipo /pedido/ml_xxx.pdf.
    # Busca el pedido que tenga ese nombre de etiqueta y redirige al link seguro con ID.
    archivo = os.path.basename(str(nombre_archivo or ""))
    if not archivo:
        return "Etiqueta no disponible", 404

    pedido = (
        Pedido.query
        .filter(Pedido.etiqueta_archivo.ilike(f"%{archivo}%"))
        .order_by(Pedido.id.desc())
        .first()
    )

    if not pedido:
        return "Etiqueta no encontrada", 404

    return redirect(url_for("ver_archivo_pedido_compat", pedido_id=pedido.id, nombre_archivo=archivo))





@app.route("/pedido/<int:pedido_id>/<path:nombre_archivo>")
@login_required
def ver_archivo_pedido_compat(pedido_id, nombre_archivo):
    # Compatibilidad con links antiguos tipo /pedido/106/ml_xxx.pdf
    pedido = Pedido.query.get_or_404(pedido_id)

    if not pedido.etiqueta_archivo:
        return "Etiqueta no disponible", 404

    archivo_guardado = os.path.basename(str(pedido.etiqueta_archivo))

    # Si el link pidió otro nombre, igual entregamos la etiqueta real del pedido.
    # Esto evita Not Found por URLs viejas o rutas relativas.
    ruta = os.path.join(app.config["UPLOAD_FOLDER"], archivo_guardado)
    if not os.path.exists(ruta):
        if es_mercado_envios(pedido):
            try:
                ml_asegurar_etiqueta_disponible(pedido)
                db.session.commit()
                archivo_guardado = os.path.basename(str(pedido.etiqueta_archivo))
                ruta = os.path.join(app.config["UPLOAD_FOLDER"], archivo_guardado)
            except Exception as e:
                print("No se pudo re-descargar etiqueta ML desde link compatible:", e)

        if not os.path.exists(ruta):
            # Último intento: si por alguna razón está en etiqueta_archivo con ruta completa.
            if os.path.exists(str(pedido.etiqueta_archivo)):
                return send_from_directory(
                    os.path.dirname(str(pedido.etiqueta_archivo)),
                    os.path.basename(str(pedido.etiqueta_archivo))
                )
            return "Etiqueta no encontrada en el servidor", 404

    return send_from_directory(app.config["UPLOAD_FOLDER"], archivo_guardado)

@app.route("/pedido/<int:id>/lanzar-impresion")
@login_required
def lanzar_impresion(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_imprimir_pedido(pedido):
        if rol_actual() == "despacho" and es_dispositivo_movil():
            return redirect(url_for("despacho_mobile", ok="Este pedido no tiene etiqueta disponible para imprimir."))
        return redirect(url_for("inicio"))

    actualizar_estado_automatico(pedido)
    db.session.commit()

    origen = (request.args.get("origen") or "").strip()

    if origen == "mobile":
        return redirect(url_for("imprimir_etiqueta", id=pedido.id, origen="mobile"))

    if origen == "detalle":
        volver_url = url_for("detalle_pedido", id=pedido.id)
    else:
        volver_url = url_for("inicio")

    return render_template(
        "lanzar_impresion.html",
        print_url=url_for("imprimir_etiqueta", id=pedido.id, origen=origen),
        volver_url=volver_url
    )


@app.route("/pedido/<int:id>/imprimir-etiqueta")
@login_required
def imprimir_etiqueta(id):
    pedido = Pedido.query.get_or_404(id)
    origen = (request.args.get("origen") or "").strip()

    if not puede_imprimir_pedido(pedido):
        if rol_actual() == "despacho" and es_dispositivo_movil():
            return redirect(url_for("despacho_mobile", ok="Este pedido no tiene etiqueta disponible para imprimir."))
        return redirect(url_for("inicio"))

    actualizar_estado_automatico(pedido)

    if es_via_cargo(pedido.empresa_envio) and not es_mercado_envios(pedido):
        aplicar_estado_y_fechas(pedido, "Etiqueta Impresa")
        db.session.commit()
        es_mobile = origen == "mobile" and rol_actual() == "despacho"

        return render_template(
            "etiqueta_via_cargo_print.html",
            pedido=pedido,
            hay_autorizado=hay_autorizado,
            es_mobile=es_mobile,
            volver_url=(
                url_for("despacho_mobile", ok="Etiqueta impresa correctamente.") if es_mobile
                else url_for("detalle_pedido", id=pedido.id) if origen == "detalle"
                else url_for("inicio")
            )
        )

    if es_mercado_envios(pedido):
        try:
            etiqueta_ok = ml_asegurar_etiqueta_disponible(pedido)
        except Exception as e:
            print("No se pudo asegurar etiqueta ML:", e)
            etiqueta_ok = False

        if not etiqueta_ok:
            db.session.commit()
            if origen == "mobile" and rol_actual() == "despacho":
                return redirect(url_for("despacho_mobile", ok="La etiqueta de Mercado Envíos todavía no está disponible. Probá de nuevo en unos minutos."))
            return render_template(
                "detalle_pedido.html",
                pedido=pedido,
                error="La etiqueta de Mercado Envíos todavía no está disponible. Resincronizá ML o probá de nuevo en unos minutos.",
                ok_feedback="",
                accion_sugerida=accion_sugerida_pedido(pedido),
                texto_boton=texto_boton_estado(pedido),
                hay_autorizado=hay_autorizado,
                puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,
                
                notas_pedido=[]
            )

    if not pedido.etiqueta_archivo:
        if origen == "mobile" and rol_actual() == "despacho":
            return redirect(url_for("despacho_mobile", ok="No hay etiqueta adjunta para imprimir."))
        return render_template(
            "detalle_pedido.html",
            pedido=pedido,
            error="No hay etiqueta adjunta para imprimir.",
            ok_feedback="",
            accion_sugerida=accion_sugerida_pedido(pedido),
            texto_boton=texto_boton_estado(pedido),
            hay_autorizado=hay_autorizado,
            puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,
            
            notas_pedido=[]
        )

    etiqueta = str(pedido.etiqueta_archivo or "").strip()
    extension = etiqueta.rsplit(".", 1)[-1].lower() if "." in etiqueta else ""
    url_original = etiqueta
    preset_etiqueta = "default"

    if etiqueta.startswith("http"):
        if extension == "pdf":
            if pedido.empresa_envio and "andreani" in pedido.empresa_envio.lower():
                preset_etiqueta = "andreani"
                nombre_pdf_local = asegurar_pdf_local_desde_url(etiqueta, prefijo=f"pedido_{pedido.id}_andreani")
                nombre_preview = generar_preview_etiqueta_pdf(nombre_pdf_local, proveedor="andreani") if nombre_pdf_local else None
                url_archivo = url_for("ver_etiqueta", nombre_archivo=nombre_preview) if nombre_preview else etiqueta.replace("/upload/", "/upload/pg_1,f_png/")
            elif pedido.empresa_envio and "correo" in pedido.empresa_envio.lower():
                preset_etiqueta = "correo"
                nombre_pdf_local = asegurar_pdf_local_desde_url(etiqueta, prefijo=f"pedido_{pedido.id}_correo")
                nombre_preview = generar_preview_etiqueta_pdf(nombre_pdf_local, proveedor="correo") if nombre_pdf_local else None
                url_archivo = url_for("ver_etiqueta", nombre_archivo=nombre_preview) if nombre_preview else etiqueta.replace("/upload/", "/upload/pg_1,f_png/")
            elif (pedido.empresa_envio and "mercado" in pedido.empresa_envio.lower()) or es_mercado_envios(pedido):
                preset_etiqueta = "mercado"
                nombre_pdf_local = asegurar_pdf_local_desde_url(etiqueta, prefijo=f"pedido_{pedido.id}_mercado")
                nombre_preview = generar_preview_etiqueta_pdf(nombre_pdf_local, proveedor="mercado") if nombre_pdf_local else None
                url_archivo = url_for("ver_etiqueta", nombre_archivo=nombre_preview) if nombre_preview else etiqueta.replace("/upload/", "/upload/pg_1,f_png/")
            else:
                url_archivo = etiqueta.replace("/upload/", "/upload/pg_1,f_png/")
        else:
            url_archivo = etiqueta
    else:
        archivo_local = os.path.basename(etiqueta)
        ruta_local = os.path.join(app.config["UPLOAD_FOLDER"], archivo_local)

        if not os.path.exists(ruta_local):
            if origen == "mobile" and rol_actual() == "despacho":
                return redirect(url_for("despacho_mobile", ok="La etiqueta no está disponible. Probá de nuevo en unos minutos."))
            return render_template(
                "detalle_pedido.html",
                pedido=pedido,
                error="La etiqueta no está disponible en el servidor. Probá resincronizar ML.",
                ok_feedback="",
                accion_sugerida=accion_sugerida_pedido(pedido),
                texto_boton=texto_boton_estado(pedido),
                hay_autorizado=hay_autorizado,
                puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,                
            )

        if extension == "pdf":
            proveedor = "mercado" if es_mercado_envios(pedido) else "default"
            preset_etiqueta = proveedor
            nombre_preview = generar_preview_etiqueta_pdf(archivo_local, proveedor=proveedor)
            url_archivo = url_for("ver_etiqueta", nombre_archivo=nombre_preview or archivo_local)
        else:
            url_archivo = url_for("ver_etiqueta", nombre_archivo=archivo_local)

    aplicar_estado_y_fechas(pedido, "Etiqueta Impresa")
    db.session.commit()

    if origen == "mobile" and rol_actual() == "despacho":
        return render_template(
            "imprimir_etiqueta_mobile.html",
            pedido=pedido,
            url_archivo=url_archivo,
            url_original=None,
            extension=extension,
            preset_etiqueta=preset_etiqueta,
            volver_url=url_for("despacho_mobile", ok="Etiqueta impresa correctamente.")
        )

    return render_template(
        "imprimir_etiqueta.html",
        pedido=pedido,
        url_archivo=url_archivo,
        url_original=url_original,
        extension=extension,
        preset_etiqueta=preset_etiqueta
    )


@app.route("/nuevo", methods=["GET", "POST"])
@login_required
def nuevo_pedido():
    if not puede_crear_pedido():
        return redirect(url_for("inicio"))

    if request.method == "POST":
        accion_paso2 = (request.form.get("accion_paso2") or "").strip()

        etiqueta_existente = request.form.get("etiqueta_existente", "").strip()
        comprobante_dux_existente = request.form.get("comprobante_dux_existente", "").strip()
        comprobante_pago_existente = request.form.get("comprobante_pago_existente", "").strip()

        archivo_etiqueta = request.files.get("etiqueta")
        archivo_comprobante_dux = request.files.get("comprobante_dux")
        archivo_comprobante_pago = request.files.get("comprobante_pago")

        if archivo_etiqueta and archivo_etiqueta.filename:
            subida = guardar_etiqueta_subida(archivo_etiqueta)
            etiqueta_existente = subida.get("url", "")

        canal = request.form.get("canal")
        ml_tipo = request.form.get("ml_tipo")

        # APB:
        # Mercado Libre y Tienda Nube NO se crean manualmente.
        # Solo pueden ingresar por importación/sync.
        if canal in ["Mercado Libre", "Tienda Nube"]:
            return render_template(
                "nuevo_pedido.html",
                error="APB: Mercado Libre y Tienda Nube solo ingresan por sincronización.",
                paso=1
            )

        # APB Presencial / Mayorista:
        # Importar DUX desde el primer paso permite autocompletar cliente/dirección
        # y dejar los productos ya cargados para confirmar al final.
        if accion_paso2 == "importar_dux_cliente":
            form_data = request.form.to_dict()
            form_data["current_step"] = "1"

            archivo_importar_dux = request.files.get("comprobante_dux_importar")
            if not archivo_importar_dux or not archivo_importar_dux.filename:
                return render_template(
                    "nuevo_pedido.html",
                    error="Subí el PDF de DUX para importar los datos.",
                    form_data=form_data,
                    etiqueta_guardada=etiqueta_existente,
                    comprobante_dux_guardado=comprobante_dux_existente,
                    comprobante_pago_guardado=comprobante_pago_existente,
                )

            nombre_dux = (archivo_importar_dux.filename or "").lower()
            if not nombre_dux.endswith(".pdf"):
                return render_template(
                    "nuevo_pedido.html",
                    error="La importación automática solo funciona con PDF de DUX.",
                    form_data=form_data,
                    etiqueta_guardada=etiqueta_existente,
                    comprobante_dux_guardado=comprobante_dux_existente,
                    comprobante_pago_guardado=comprobante_pago_existente,
                )

            resultado_datos = extraer_datos_cliente_comprobante_dux_desde_pdf(archivo_importar_dux)
            archivo_importar_dux.stream.seek(0)
            resultado_items = extraer_items_comprobante_dux_desde_pdf(archivo_importar_dux)
            items_detectados = resultado_items.get("items", []) or []

            if not resultado_datos.get("ok") and not items_detectados:
                return render_template(
                    "nuevo_pedido.html",
                    error=resultado_items.get("error") or resultado_datos.get("error") or "No se pudieron leer datos ni productos del PDF de DUX.",
                    form_data=form_data,
                    etiqueta_guardada=etiqueta_existente,
                    comprobante_dux_guardado=comprobante_dux_existente,
                    comprobante_pago_guardado=comprobante_pago_existente,
                )

            archivo_importar_dux.stream.seek(0)
            subida_dux = guardar_comprobante_dux_subido(archivo_importar_dux)
            comprobante_dux_existente = subida_dux.get("url", "")

            if not comprobante_dux_existente:
                return render_template(
                    "nuevo_pedido.html",
                    error="Se leyó el DUX, pero no se pudo guardar el comprobante. Volvé a intentar.",
                    form_data=form_data,
                    etiqueta_guardada=etiqueta_existente,
                    comprobante_dux_guardado="",
                    comprobante_pago_guardado=comprobante_pago_existente,
                )

            datos_dux = resultado_datos.get("datos", {}) or {}
            for campo in ["cliente", "dni", "id_venta", "direccion", "localidad", "provincia"]:
                valor_actual = (form_data.get(campo) or "").strip()
                valor_dux = (datos_dux.get(campo) or "").strip()
                if valor_dux and not valor_actual:
                    form_data[campo] = valor_dux

            if items_detectados:
                form_data["items_texto"] = items_detectados_a_texto(items_detectados)

            form_data["comprobante_dux_existente"] = comprobante_dux_existente
            form_data["dux_importado_desde_cliente"] = "1"

            partes_ok = []
            if datos_dux:
                partes_ok.append("datos del cliente")
            if items_detectados:
                partes_ok.append(f"{len(items_detectados)} producto(s)")
            mensaje_ok = "DUX importado correctamente: " + " y ".join(partes_ok) + "."

            return render_template(
                "nuevo_pedido.html",
                error="",
                form_data=form_data,
                etiqueta_guardada=etiqueta_existente,
                comprobante_dux_guardado=comprobante_dux_existente,
                comprobante_pago_guardado=comprobante_pago_existente,
                ok_feedback=mensaje_ok,
            )

        # APB Presencial / Mayorista:
        # DUX es obligatorio y además permite leer automáticamente los productos.
        # Comprobante de pago es opcional: si se adjunta, se guarda; si no, no bloquea.
        if accion_paso2 == "leer_dux_nuevo":
            form_data = request.form.to_dict()
            form_data["current_step"] = "4"

            if not archivo_comprobante_dux or not archivo_comprobante_dux.filename:
                return render_template(
                    "nuevo_pedido.html",
                    error="Subí el PDF de DUX para leer los productos.",
                    form_data=form_data,
                    etiqueta_guardada=etiqueta_existente,
                    comprobante_dux_guardado=comprobante_dux_existente,
                    comprobante_pago_guardado=comprobante_pago_existente,
                )

            nombre_dux = (archivo_comprobante_dux.filename or "").lower()
            if not nombre_dux.endswith(".pdf"):
                return render_template(
                    "nuevo_pedido.html",
                    error="La lectura automática solo funciona con PDF de DUX.",
                    form_data=form_data,
                    etiqueta_guardada=etiqueta_existente,
                    comprobante_dux_guardado=comprobante_dux_existente,
                    comprobante_pago_guardado=comprobante_pago_existente,
                )

            resultado_pdf = extraer_items_comprobante_dux_desde_pdf(archivo_comprobante_dux)
            items_detectados = resultado_pdf.get("items", []) or []
            if not items_detectados:
                return render_template(
                    "nuevo_pedido.html",
                    error=resultado_pdf.get("error") or "No se detectaron productos en el PDF de DUX.",
                    form_data=form_data,
                    etiqueta_guardada=etiqueta_existente,
                    comprobante_dux_guardado=comprobante_dux_existente,
                    comprobante_pago_guardado=comprobante_pago_existente,
                )

            archivo_comprobante_dux.stream.seek(0)
            subida_dux = guardar_comprobante_dux_subido(archivo_comprobante_dux)
            comprobante_dux_existente = subida_dux.get("url", "")
            if not comprobante_dux_existente:
                return render_template(
                    "nuevo_pedido.html",
                    error="Se leyeron los productos, pero no se pudo guardar el comprobante DUX. Volvé a intentar.",
                    form_data=form_data,
                    etiqueta_guardada=etiqueta_existente,
                    comprobante_dux_guardado="",
                    comprobante_pago_guardado=comprobante_pago_existente,
                )

            if archivo_comprobante_pago and archivo_comprobante_pago.filename:
                subida_pago = guardar_comprobante_pago_agregado_subido(archivo_comprobante_pago)
                comprobante_pago_existente = subida_pago.get("url", "")

            form_data["items_texto"] = items_detectados_a_texto(items_detectados)
            form_data["comprobante_dux_existente"] = comprobante_dux_existente
            form_data["comprobante_pago_existente"] = comprobante_pago_existente

            return render_template(
                "nuevo_pedido.html",
                error="",
                form_data=form_data,
                etiqueta_guardada=etiqueta_existente,
                comprobante_dux_guardado=comprobante_dux_existente,
                comprobante_pago_guardado=comprobante_pago_existente,
                ok_feedback=f"DUX leído correctamente: {len(items_detectados)} producto(s) cargado(s).",
            )

        if archivo_comprobante_dux and archivo_comprobante_dux.filename:
            subida_dux = guardar_comprobante_dux_subido(archivo_comprobante_dux)
            comprobante_dux_existente = subida_dux.get("url", "")

        if archivo_comprobante_pago and archivo_comprobante_pago.filename:
            subida_pago = guardar_comprobante_pago_agregado_subido(archivo_comprobante_pago)
            comprobante_pago_existente = subida_pago.get("url", "")

        empresa_envio = request.form.get("empresa_envio")
        tipo_entrega = request.form.get("tipo_entrega")
        direccion = request.form.get("direccion")
        codigo_postal = request.form.get("codigo_postal")
        localidad = request.form.get("localidad")
        provincia = request.form.get("provincia")
        observaciones = request.form.get("observaciones")
        sucursal_nombre = request.form.get("sucursal_nombre")
        autorizado_nombre = request.form.get("autorizado_nombre")
        autorizado_dni = request.form.get("autorizado_dni")
        autorizado_telefono = request.form.get("autorizado_telefono")

        if canal == "Mercado Libre" and ml_tipo == "Mercado Envíos":
            empresa_envio = ""
            tipo_entrega = ""
            direccion = ""
            codigo_postal = ""
            localidad = ""
            provincia = ""
            observaciones = ""
            sucursal_nombre = ""
            autorizado_nombre = ""
            autorizado_dni = ""
            autorizado_telefono = ""

        if canal_requiere_dux_obligatorio(canal) and not comprobante_dux_existente:
            return render_template(
                "nuevo_pedido.html",
                error="Para pedidos Presencial o Mayorista tenés que importar o leer el PDF de DUX antes de guardar.",
                form_data=request.form,
                etiqueta_guardada=etiqueta_existente,
                comprobante_dux_guardado=comprobante_dux_existente,
                comprobante_pago_guardado=comprobante_pago_existente,
            )

        pedido = Pedido(
            cliente=request.form.get("cliente"),
            dni=request.form.get("dni"),
            telefono=normalizar_telefono(request.form.get("telefono")),
            mail=request.form.get("mail"),
            canal=canal,
            id_venta=request.form.get("id_venta"),
            ml_tipo=ml_tipo,
            empresa_envio=empresa_envio,
            tipo_entrega=tipo_entrega,
            direccion=direccion,
            codigo_postal=codigo_postal,
            localidad=localidad,
            provincia=provincia,
            observaciones=observaciones,
            sucursal_nombre=sucursal_nombre,
            autorizado_nombre=autorizado_nombre,
            autorizado_dni=autorizado_dni,
            autorizado_telefono=autorizado_telefono,
            seguimiento=request.form.get("seguimiento"),
            etiqueta_archivo=etiqueta_existente,
            comprobante_dux_archivo=comprobante_dux_existente,
            comprobante_pago_archivo=comprobante_pago_existente,
        )

        db.session.add(pedido)
        db.session.flush()

        if es_guardado_parcial_acordas():
            db.session.commit()



            return redirect(url_for("inicio"))

        cargar_items_desde_texto(pedido, request.form.get("items_texto", ""))
        actualizar_estado_automatico(pedido)

        errores = motor_bloqueo(pedido)

        if errores:
            db.session.rollback()
            return render_template(
                "nuevo_pedido.html",
                error="<br>".join(errores),
                form_data=request.form,
                etiqueta_guardada=etiqueta_existente,
                comprobante_dux_guardado=comprobante_dux_existente,
                comprobante_pago_guardado=comprobante_pago_existente,
            )

        db.session.commit()

        if canal == "Mercado Libre" and ml_tipo == "Acordás la Entrega" and not despacho_completo(pedido):
            return redirect(url_for("inicio"))

        return redirect(url_for("inicio"))

    return render_template(
        "nuevo_pedido.html",
        error="",
        form_data={},
        etiqueta_guardada="",
        comprobante_dux_guardado="",
        comprobante_pago_guardado="",
    )

@app.route("/pedido/<int:id>")
@login_required
def detalle_pedido(id):
    
    pedido = Pedido.query.get_or_404(id)

    permitir_detalle_mobile = (
        request.args.get("mobile_detalle") == "1"
    )

    if (
        rol_actual() == "despacho"
        and es_dispositivo_movil()
        and not permitir_detalle_mobile
    ):
        return redirect(url_for("despacho_mobile"))


    if not puede_ver_pedido(pedido):
        return redirect(url_for("inicio"))

    estado_anterior = pedido.estado
    actualizar_estado_automatico(pedido)
    if pedido.estado != estado_anterior:
        db.session.commit()

    ok_feedback = (request.args.get("ok") or "").strip()
    error = (request.args.get("error") or "").strip()

    if es_ml_acordas_entrega(pedido):
        mensaje_actualizado = generar_mensaje_contacto_ml(pedido)
        if pedido.ml_mensaje_contacto != mensaje_actualizado:
            pedido.ml_mensaje_contacto = mensaje_actualizado
            db.session.commit()

    # Refuerzo APB con throttle: al abrir detalle NO castigamos la API de ML en cada carga.
    # Mensajes: refresca cada 5 min. Reclamos: refresca cada 10 min.
    if pedido.canal == "Mercado Libre":
        hubo_cambios_ml = False
        ahora_ml_detalle = datetime.utcnow()

        try:
            ultima_msgs = getattr(pedido, "ultima_sync_mensajes_ml", None)
            debe_sync_msgs = (not ultima_msgs) or ((ahora_ml_detalle - ultima_msgs).total_seconds() > 5 * 60)
            if debe_sync_msgs:
                ml_sync_mensajes_pedido(pedido)
                hubo_cambios_ml = True
            else:
                print(f"[ML-DETALLE] Mensajes pedido #{pedido.id}: se usa cache reciente")
        except Exception as e:
            print(f"[ML-DETALLE] No se pudo sincronizar mensajes pedido #{pedido.id}: {e}")

        try:
            ultima_claim = getattr(pedido, "ultima_sync_claim_ml", None)
            debe_sync_claim = (not ultima_claim) or ((ahora_ml_detalle - ultima_claim).total_seconds() > 10 * 60)
            if debe_sync_claim:
                order_id_detalle = str(getattr(pedido, "id_venta", "") or "").strip()
                pack_id_detalle = str(getattr(pedido, "ml_pack_id", "") or "").strip()
                if order_id_detalle or pack_id_detalle:
                    claim_live = ml_obtener_claim_de_order(order_id_detalle, pack_id_detalle)
                    ml_marcar_claim_en_pedido(pedido, claim_live)
                    hubo_cambios_ml = True
            else:
                print(f"[ML-DETALLE] Claim pedido #{pedido.id}: se usa cache reciente")
        except Exception as e:
            print(f"[ML-DETALLE] No se pudo sincronizar claim pedido #{pedido.id}: {e}")

        if hubo_cambios_ml:
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"[ML-DETALLE] Error guardando sync ML pedido #{pedido.id}: {e}")

    auditorias_pedido = []
    if rol_actual() == "admin":
        auditorias_pedido = Auditoria.query.filter_by(entidad="pedido", entidad_id=str(pedido.id)).order_by(Auditoria.fecha.desc()).limit(50).all()

    # Notas internas (solo admin y carga)
    notas_pedido = []
    if rol_actual() in ["admin", "carga"]:
        notas_pedido = NotaPedido.query.filter_by(pedido_id=pedido.id).order_by(NotaPedido.fecha.desc()).all()

    whatsapp_mensajes = []
    if rol_actual() in ["admin", "carga"]:
        whatsapp_mensajes = (
            WhatsAppMensaje.query
            .filter_by(pedido_id=pedido.id)
            .order_by(WhatsAppMensaje.fecha.asc())
            .limit(80)
            .all()
        )

    agregados_apb = []
    if rol_actual() in ["admin", "carga", "despacho"]:
        registros_agregados_apb = (
            PedidoAgregadoAPB.query
            .filter_by(pedido_id=pedido.id)
            .order_by(PedidoAgregadoAPB.fecha.desc())
            .all()
        )
        for agregado in registros_agregados_apb:
            try:
                items_agregado = json.loads(agregado.items_json or "[]")
            except Exception:
                items_agregado = []
            agregados_apb.append({
                "id": agregado.id,
                "usuario": agregado.usuario,
                "rol": agregado.rol,
                "fecha": agregado.fecha,
                "comprobante_dux_url": agregado.comprobante_dux_url,
                "comprobante_pago_url": agregado.comprobante_pago_url,
                "items": items_agregado,
            })

    return render_template(
        "detalle_pedido.html",
        pedido=pedido,
        error=error,
        ok_feedback=ok_feedback,
        accion_sugerida=accion_sugerida_pedido(pedido),
        texto_boton=texto_boton_estado(pedido),
        hay_autorizado=hay_autorizado,
        puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,
        
        auditorias_pedido=auditorias_pedido,
        notas_pedido=notas_pedido,
        whatsapp_mensajes=whatsapp_mensajes,
        agregados_apb=agregados_apb,
    )

@app.route("/despacho-mobile/pedido/<int:id>/revisar-agregado")
@login_required
def revisar_agregado_mobile(id):

    if rol_actual() != "despacho":
        flash("Acceso inválido.", "danger")
        return redirect(url_for("inicio"))

    pedido = Pedido.query.get_or_404(id)

    if not es_dispositivo_movil():
        return redirect(url_for("detalle_pedido", id=pedido.id))

    return render_template(
        "revisar_agregado_mobile.html",
        pedido=pedido
    )

def marcar_contacto_iniciado_pedido(pedido):
    if not pedido:
        return
    pedido.contacto_iniciado = True
    if not pedido.fecha_contacto:
        pedido.fecha_contacto = datetime.utcnow()


@app.route("/pedido/<int:id>/resync-ml", methods=["POST"])
@login_required
def resync_ml_pedido(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_operar_whatsapp(pedido):
        return redirect(url_for(
            "detalle_pedido",
            id=pedido.id,
            error="No autorizado para operar WhatsApp."
        ))

    if pedido.canal != "Mercado Libre":
        return redirect(url_for("detalle_pedido", id=pedido.id, error="No es un pedido de Mercado Libre."))

    try:
        detalles = []
        order_id = str(getattr(pedido, "id_venta", "") or "").strip()
        if order_id:
            order = ml_obtener_order(order_id)
            if order:
                print(
                    f"[ML-RESYNC-DEBUG] Pedido #{pedido.id} order_id={order_id} "
                    f"status={order.get('status')} "
                    f"tags={order.get('tags')} "
                    f"shipping_status={((order.get('shipping') or {}).get('status'))} "
                    f"shipping_mode={((order.get('shipping') or {}).get('mode'))} "
                    f"pack_id={order.get('pack_id')} "
                    f"date_closed={order.get('date_closed')}"
                )

                pedido_actualizado, creado, motivo = ml_upsert_pedido_desde_order(order)
                if pedido_actualizado:
                    pedido = pedido_actualizado
                    detalles.append("orden")
                elif motivo:
                    detalles.append(f"orden omitida: {motivo}")
                    # Si ML informa que la orden está cancelada/cerrada,
                    # actualizar el estado del pedido existente en el sistema
                    estados_cancelados_ml = {"cancelled", "invalid"}
                    order_status = str((order or {}).get("status") or "").lower().strip()
                    if order_status in estados_cancelados_ml and pedido.estado not in ["Cancelado", "Finalizado", "Entregado"]:
                        pedido.estado = "Cancelado"
                        detalles.append("estado=Cancelado (ML informa orden cancelada)")
                        print(f"[ML-RESYNC] Pedido #{pedido.id} cancelado — ML status={order_status}")

                    shipment = ml_obtener_shipment((order.get("shipping") or {}).get("id"))

                    print(
                        f"[ML-RESYNC-DEBUG] Pedido #{pedido.id} "
                        f"order_id={order_id} "
                        f"order_status={ml_estado_order(order)} "
                        f"shipping_status={ml_estado_shipment(order, shipment)} "
                        f"tags={order.get('tags') or []} "
                        f"shipping={order.get('shipping') or {}} "
                        f"shipment={shipment}"
                    )

                    if ml_order_esta_entregado(order, shipment):

                        if not pedido.fecha_entregado:
                            pedido.fecha_entregado = datetime.utcnow()

                        pedido.estado = "Finalizado"

                        detalles.append(
                            "estado=Finalizado (ML informa entrega/finalización)"
                        )

                        print(
                            f"[ML-RESYNC] Pedido #{pedido.id} finalizado automáticamente — "
                            f"order={order_status} "
                            f"shipment={ml_estado_shipment(order, shipment)}"
                        )


        tiene_msgs, count_msgs = ml_sync_mensajes_pedido(pedido)
        detalles.append(f"mensajes={count_msgs}")

        claim = ml_obtener_claim_de_order(pedido.id_venta, pedido.ml_pack_id)
        ml_marcar_claim_en_pedido(pedido, claim)
        detalles.append("reclamo=activo" if claim else "reclamo=sin activo")

        db.session.commit()
        return redirect(url_for("detalle_pedido", id=pedido.id, ok="ML re-sincronizado: " + " | ".join(detalles)))

    except Exception as e:
        db.session.rollback()
        print(f"[ML-RESYNC] Error pedido #{pedido.id}: {e}")
        return redirect(url_for("detalle_pedido", id=pedido.id, error=f"No se pudo re-sincronizar ML: {e}"))


@app.route("/pedido/<int:id>/sync-mensajes-ml", methods=["POST"])
@login_required
def sync_mensajes_ml_pedido_admin(id):
    pedido = Pedido.query.get_or_404(id)
    if not puede_ver_pedido(pedido):
        return redirect(url_for("inicio"))
    if pedido.canal != "Mercado Libre":
        return redirect(url_for("detalle_pedido", id=pedido.id, error="No es un pedido de Mercado Libre."))

    try:
        tiene, count = ml_sync_mensajes_pedido(pedido)
        db.session.commit()
        ok = f"Mensajes ML sincronizados: {count} pendiente(s)." if tiene else "Mensajes ML sincronizados: sin pendientes detectados."
        return redirect(url_for("detalle_pedido", id=pedido.id, ok=ok))
    except Exception as e:
        db.session.rollback()
        print(f"[ML-MSGS-MANUAL] Error pedido #{pedido.id}: {e}")
        return redirect(url_for("detalle_pedido", id=pedido.id, error=f"No se pudo sincronizar mensajes ML: {e}"))


@app.route("/pedido/<int:id>/resync-tn", methods=["POST"])
@login_required
def resync_tn_pedido(id):
    pedido = Pedido.query.get_or_404(id)
    if not puede_editar_pedido(pedido):
        return redirect(url_for("detalle_pedido", id=pedido.id, error="No autorizado."))
    if pedido.canal != "Tienda Nube" or not pedido.tn_order_id:
        return redirect(url_for("detalle_pedido", id=pedido.id, error="No es un pedido de Tienda Nube."))

    try:
        _, accion = tn_importar_pedido_por_id(pedido.tn_order_id)
        registrar_auditoria(
            accion="Re-sincronizó pedido Tienda Nube",
            entidad="pedido",
            entidad_id=str(pedido.id),
            detalle=f"Pedido TN {pedido.tn_order_id}. Resultado: {accion}",
        )
        db.session.commit()
        return redirect(url_for("detalle_pedido", id=pedido.id, ok=f"Pedido TN re-sincronizado ({accion})."))
    except Exception as e:
        db.session.rollback()
        return redirect(url_for("detalle_pedido", id=pedido.id, error=f"No se pudo re-sincronizar TN: {e}"))



@app.route("/pedido/<int:id>/sync-tracking", methods=["GET", "POST"])
@app.route("/pedido/<int:id>/actualizar-tracking-externo", methods=["GET", "POST"])
@login_required
def actualizar_tracking_externo_pedido(id):
    pedido = Pedido.query.get_or_404(id)

    if rol_actual() not in ["admin", "carga"]:
        return redirect(url_for("detalle_pedido", id=pedido.id, error="No autorizado."))

    if not puede_actualizar_tracking_externo(pedido):
        return redirect(url_for("detalle_pedido", id=pedido.id, ok="Este pedido no tiene tracking externo actualizable."))

    tracking_info = tracking_info_pedido(pedido)
    if not tracking_info:
        return redirect(url_for("detalle_pedido", id=pedido.id, ok="No hay link de seguimiento disponible."))

    transporte = pedido.empresa_envio or ("Correo Argentino" if es_correo_argentino_pedido(pedido) else "")
    seguimiento = str(tracking_info.get("seguimiento") or pedido.seguimiento or pedido.tn_tracking_number or "").strip()

    # APB: para consultar automáticamente NO confiamos en links genéricos ni en datos viejos.
    # Armamos la URL real del transportista desde empresa_envio + seguimiento.
    transporte_norm = str(transporte or "").strip().lower()
    if "andreani" in transporte_norm:
        url = f"https://www.andreani.com/envio/{seguimiento}"
    elif "via cargo" in transporte_norm or "vía cargo" in transporte_norm:
        url = f"https://viacargo.com.ar/seguimiento-de-envio/{seguimiento}/"
    else:
        url = tracking_info.get("url") or ""

    try:
        if es_correo_argentino_pedido(pedido):
            resultado = consultar_correo_formulario(
                seguimiento,
                mercado_envios=(pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Mercado Envíos")
            )
            transporte = "Correo Argentino"
        else:
            resultado = consultar_tracking_url(url, transporte=transporte, seguimiento=seguimiento)

        estado = (resultado.get("estado") or "").strip() or "Sin estado detectado"
        clasificacion = interpretar_estado_logistico(estado, transporte=transporte)

        pedido.tracking_transportista = transporte[:80] if transporte else None
        pedido.tracking_url_consultada = url[:500] if url else None
        pedido.tracking_estado_externo = estado[:300]
        pedido.tracking_ultima_sync = datetime.utcnow()
        pedido.tracking_error = resultado.get("error")

        nuevo_estado = None
        if not resultado.get("error"):
            nuevo_estado = aplicar_estado_tracking_seguro(pedido, clasificacion)
            try:
                from modules.whatsapp.post_despacho import registrar_tracking_evento, procesar_evento_tracking_pedido
                registrar_tracking_evento(pedido, transporte, seguimiento, estado, clasificacion, raw_json=str(resultado)[:4000], origen="manual")
                procesar_evento_tracking_pedido(pedido, clasificacion, estado, origen="manual")
            except Exception as e:
                print("[TRACKING] Error post-despacho:", e)

        registrar_auditoria(
            accion="Actualizó tracking externo",
            entidad="pedido",
            entidad_id=str(pedido.id),
            detalle=f"{transporte} {seguimiento}. Estado externo: {estado}. Estado Fierro: {nuevo_estado or pedido.estado}",
        )
        db.session.commit()

        if resultado.get("error"):
            return redirect(url_for("detalle_pedido", id=pedido.id, ok="Tracking consultado. No se detectó un estado automático seguro."))

        extra = f" Pedido actualizado a {nuevo_estado}." if nuevo_estado else " No se cambió el estado interno."
        return redirect(url_for("detalle_pedido", id=pedido.id, ok=f"Tracking actualizado: {estado}.{extra}"))

    except Exception as e:
        db.session.rollback()
        try:
            pedido.tracking_error = str(e)
            pedido.tracking_ultima_sync = datetime.utcnow()
            db.session.commit()
        except Exception:
            db.session.rollback()
        return redirect(url_for("detalle_pedido", id=pedido.id, ok="No se pudo actualizar el tracking automáticamente."))


@app.route("/pedido/<int:id>/actualizar-andreani", methods=["POST"])
@login_required
def actualizar_andreani_pedido(id):
    pedido = Pedido.query.get_or_404(id)
    if rol_actual() not in ["admin", "carga"]:
        return redirect(url_for("detalle_pedido", id=pedido.id, error="No autorizado."))
    if not es_andreani_pedido(pedido):
        return redirect(url_for("detalle_pedido", id=pedido.id, error="El pedido no es de Andreani."))
    if not (pedido.seguimiento or "").strip():
        return redirect(url_for("detalle_pedido", id=pedido.id, error="El pedido no tiene seguimiento Andreani cargado."))
    if not andreani_configurada():
        # Andreani puede quedar instalado antes de cargar credenciales.
        # No lo tratamos como error operativo ni mostramos banner rojo.
        return redirect(url_for("detalle_pedido", id=pedido.id))

    try:
        resultado = andreani_trazas_envio(pedido.seguimiento)
        eventos = resultado.get("eventos") or []
        ultimo = resultado.get("ultimo_evento") or {}
        pedido.andreani_estado = resumen_evento_andreani(ultimo)[:200] if ultimo else "Sin eventos"
        pedido.andreani_eventos_json = json.dumps({"eventos": eventos}, ensure_ascii=False, default=str)
        pedido.andreani_ultima_sync = datetime.utcnow()
        registrar_auditoria(
            accion="Actualizó estado Andreani",
            entidad="pedido",
            entidad_id=str(pedido.id),
            detalle=f"Seguimiento {pedido.seguimiento}. Estado: {pedido.andreani_estado}",
        )
        db.session.commit()
        alerta = andreani_alerta_pedido(pedido)
        extra = f" {alerta['texto']}" if alerta else ""
        return redirect(url_for("detalle_pedido", id=pedido.id, ok=f"Andreani actualizado: {pedido.andreani_estado}.{extra}"))
    except Exception as e:
        db.session.rollback()
        return redirect(url_for("detalle_pedido", id=pedido.id, error=f"No se pudo actualizar Andreani: {e}"))


@app.route("/pedido/<int:id>/eliminar", methods=["POST"])
@login_required
def eliminar_pedido(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_eliminar_pedido(pedido):
        return redirect(url_for("detalle_pedido", id=pedido.id, error="Solo Admin puede eliminar pedidos."))

    pedido_numero = pedido.id
    try:
        if pedido.canal == "Mercado Libre" and pedido.id_venta:
            ml_registrar_pedido_ignorado(pedido, motivo="eliminado_manual_admin")

        db.session.delete(pedido)
        db.session.commit()
        return redirect(url_for("inicio", ok=f"Pedido #{pedido_numero} eliminado correctamente."))
    except Exception as e:
        db.session.rollback()
        return redirect(url_for("detalle_pedido", id=id, error=f"No se pudo eliminar el pedido: {e}"))




@app.route("/pedido/<int:id>/nota/agregar", methods=["POST"])
@login_required
def agregar_nota_pedido(id):
    pedido = Pedido.query.get_or_404(id)
    rol = rol_actual()
    if rol not in ["admin", "carga"]:
        return redirect(url_for("detalle_pedido", id=id, error="Sin permiso para agregar notas."))

    texto = (request.form.get("texto") or "").strip()
    if not texto:
        return redirect(url_for("detalle_pedido", id=id, error="La nota no puede estar vacía."))

    nota = NotaPedido(
        pedido_id=id,
        texto=texto,
        usuario=session.get("username", ""),
        rol=rol_actual(),
        fecha=datetime.utcnow(),
    )
    db.session.add(nota)
    db.session.commit()
    return redirect(url_for("detalle_pedido", id=id) + "#notas")


@app.route("/pedido/<int:id>/nota/<int:nota_id>/editar", methods=["POST"])
@login_required
def editar_nota_pedido(id, nota_id):
    if rol_actual() != "admin":
        return redirect(url_for("detalle_pedido", id=id, error="Solo Admin puede editar notas."))

    nota = NotaPedido.query.get_or_404(nota_id)
    texto = (request.form.get("texto") or "").strip()
    if not texto:
        return redirect(url_for("detalle_pedido", id=id, error="La nota no puede estar vacía."))

    nota.texto = texto
    db.session.commit()
    return redirect(url_for("detalle_pedido", id=id) + "#notas")


@app.route("/pedido/<int:id>/nota/<int:nota_id>/eliminar", methods=["POST"])
@login_required
def eliminar_nota_pedido(id, nota_id):
    if rol_actual() != "admin":
        return redirect(url_for("detalle_pedido", id=id, error="Solo Admin puede eliminar notas."))

    nota = NotaPedido.query.get_or_404(nota_id)
    db.session.delete(nota)
    db.session.commit()
    return redirect(url_for("detalle_pedido", id=id) + "#notas")

@app.route("/pedido/<int:id>/marcar-contacto-ml", methods=["POST"])
@login_required
def marcar_contacto_ml(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_ver_pedido(pedido):
        return jsonify({"ok": False}), 403

    marcar_contacto_iniciado_pedido(pedido)
    db.session.commit()
    return jsonify({"ok": True})




@app.route("/pedido/<int:id>/desmarcar-contacto-ml", methods=["POST"])
@login_required
def desmarcar_contacto_ml(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_operar_whatsapp(pedido):
        return redirect(url_for(
            "detalle_pedido",
            id=pedido.id,
            error="No autorizado para operar WhatsApp."
        ))

    pedido.contacto_iniciado = False
    pedido.fecha_contacto = None
    pedido.ml_mensaje_contacto = ""
    db.session.commit()
    return redirect(url_for("detalle_pedido", id=pedido.id, ok="Contacto inicial corregido. El pedido vuelve a quedar pendiente de contacto."))

@app.route("/pedido/<int:id>/enviar-mensaje-ml", methods=["POST"])
@login_required
def enviar_mensaje_ml_acordas(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_ver_pedido(pedido):
        return redirect(url_for("inicio"))

    try:
        # Usar la misma plantilla existente que ve el operador, incluida la diferenciacion por producto.
        texto_visible = generar_mensaje_contacto_ml(pedido)
        ml_enviar_mensaje_acordas(pedido, texto_visible)
        pedido.ml_mensaje_contacto = texto_visible
        marcar_contacto_iniciado_pedido(pedido)
        db.session.commit()
        return redirect(url_for("inicio"))
    except Exception as e:
        db.session.rollback()

        if "__FALLBACK_A_WEB__" in str(e):
            marcar_contacto_iniciado_pedido(pedido)
            db.session.commit()
            print(f"[ML-FALLBACK] Pedido {pedido.id} | order_status={pedido.ml_order_status} | ML no habilita envio por API")
            return redirect(url_for(
                "detalle_pedido",
                id=pedido.id,
                ok="ML no habilito el envio automatico. Copiamos el mensaje y abrimos el chat de la venta en Mercado Libre.",
                fallback_ml_chat="1"
            ))

        return redirect(url_for(
            "detalle_pedido",
            id=pedido.id,
            error=f"No se pudo enviar el mensaje a Mercado Libre: {e}"
        ))
@app.route("/pedido/<int:id>/ia-analizar-respuesta", methods=["POST"])
@login_required
def ia_analizar_respuesta_pedido(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_operar_whatsapp(pedido):
        return redirect(url_for(
            "detalle_pedido",
            id=pedido.id,
            error="No autorizado para operar WhatsApp."
        ))

    if not es_ml_acordas_entrega(pedido):
        return redirect(url_for("detalle_pedido", id=pedido.id, error="La IA recolector solo aplica a Mercado Libre / Acordás la Entrega."))

    if not getattr(pedido, "contacto_iniciado", False):
        return redirect(url_for("detalle_pedido", id=pedido.id, error="Primero debe existir contacto inicial enviado."))

    cuenta = MercadoLibreCuenta.query.first()
    seller_id = str((cuenta.user_id_ml if cuenta else "") or "").strip()
    ids_chat = []
    for posible in [getattr(pedido, "ml_pack_id", None), getattr(pedido, "id_venta", None)]:
        posible = str(posible or "").strip()
        if posible and posible not in ids_chat:
            ids_chat.append(posible)

    mensajes = []
    for id_chat in ids_chat:
        mensajes = ml_obtener_mensajes_pack_para_ia(id_chat, seller_id=seller_id)
        if mensajes:
            break

    if not mensajes:
        return redirect(url_for("detalle_pedido", id=pedido.id, error="No se pudieron leer mensajes del comprador para analizar."))

    resultado = ia_analizar_ultimo_mensaje_pedido(pedido, mensajes, seller_id=seller_id, forzar=True)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return redirect(url_for("detalle_pedido", id=pedido.id, error=f"No se pudo guardar el análisis IA: {e}"))

    if not resultado:
        return redirect(url_for("detalle_pedido", id=pedido.id, error="No hay mensaje nuevo del comprador para analizar."))
    if not resultado.get("ok"):
        return redirect(url_for("detalle_pedido", id=pedido.id, error=f"IA no disponible: {resultado.get('error', 'error desconocido')}"))

    return redirect(url_for("detalle_pedido", id=pedido.id, ok="IA analizó la última respuesta, autocompletó campos vacíos y aplicó respuesta automática si correspondía."))


@app.route("/pedido/<int:id>/ia-enviar-respuesta-faltantes", methods=["POST"])
@login_required
def ia_enviar_respuesta_faltantes_pedido(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_operar_whatsapp(pedido):
        return redirect(url_for(
            "detalle_pedido",
            id=pedido.id,
            error="No autorizado para operar WhatsApp."
        ))

    if not es_ml_acordas_entrega(pedido):
        return redirect(url_for("detalle_pedido", id=pedido.id, error="La IA recolector solo aplica a Mercado Libre / Acordás la Entrega."))

    if not getattr(pedido, "contacto_iniciado", False):
        return redirect(url_for("detalle_pedido", id=pedido.id, error="Primero debe existir contacto inicial enviado."))

    if getattr(pedido, "ia_requiere_operador", False) or pedido.ia_recolector_estado == "requiere_operador":
        return redirect(url_for("detalle_pedido", id=pedido.id, error="La IA marcó que requiere operador. No se envía respuesta automática."))

    faltantes = ia_faltantes_pedido(pedido)
    if not faltantes:
        return redirect(url_for("detalle_pedido", id=pedido.id, error="No hay datos faltantes para pedir."))

    texto = ia_generar_respuesta_faltantes_pedido(pedido)
    if not texto:
        return redirect(url_for("detalle_pedido", id=pedido.id, error="No se pudo generar respuesta IA."))

    if ia_respuesta_faltantes_ya_enviada(pedido, texto):
        return redirect(url_for("detalle_pedido", id=pedido.id, error="Esta respuesta IA ya fue enviada después del último análisis. Esperá una nueva respuesta del comprador."))

    try:
        ml_enviar_mensaje_acordas(pedido, texto)
        pedido.ia_respuesta_sugerida = texto
        pedido.ia_respuesta_enviada_hash = ia_hash_texto(texto)
        pedido.ia_ultima_respuesta_enviada = datetime.utcnow()
        pedido.ml_mensajes_pendientes = False
        pedido.ml_mensajes_pendientes_count = 0
        db.session.commit()
        return redirect(url_for("detalle_pedido", id=pedido.id, ok="Respuesta IA enviada a Mercado Libre pidiendo solo los datos faltantes."))
    except Exception as e:
        db.session.rollback()
        return redirect(url_for("detalle_pedido", id=pedido.id, error=f"No se pudo enviar respuesta IA a Mercado Libre: {e}"))




# =========================
# ADMIN - EDICIÓN COMPLETA DE PEDIDO
# =========================
ADMIN_PEDIDO_CAMPOS_GRUPOS = [
    ("Identificación / ML / TN", [
        "origen", "ml_pack_id", "ml_order_status", "ml_shipping_status", "ml_shipping_id",
        "ml_logistic_type", "ml_shipping_mode", "ultima_sync_ml", "tn_order_id", "tn_order_number",
        "tn_order_status", "tn_payment_status", "tn_paid_at", "tn_cancelled_at", "tn_fulfillment_id",
        "tn_fulfillment_status", "tn_shipping_type", "tn_shipping_carrier", "tn_shipping_option",
        "tn_tracking_number", "tn_tracking_url", "ultima_sync_tn",
    ]),
    ("Cliente / venta", [
        "cliente", "dni", "telefono", "mail", "canal", "id_venta", "ml_tipo",
        "ml_buyer_id", "ml_buyer_nickname", "ml_nombre_real", "ml_datos_fiscales_ok",
        "ml_billing_nombre", "ml_billing_documento", "ml_billing_direccion", "ml_campos_faltantes",
        "ml_mensaje_contacto", "contacto_iniciado", "fecha_contacto",
        "wa_estado", "wa_paso_operativo",
    ]),
    ("Envío / autorizado / tracking", [
        "empresa_envio", "tipo_entrega", "direccion", "codigo_postal", "localidad", "provincia",
        "observaciones", "sucursal_nombre", "autorizado_nombre", "autorizado_dni", "autorizado_telefono",
        "seguimiento", "andreani_estado", "andreani_ultima_sync", "andreani_eventos_json",
        "tracking_estado_externo", "tracking_ultima_sync", "tracking_error", "tracking_transportista",
        "tracking_url_consultada", "etiqueta_archivo", "comprobante_dux_archivo",
    ]),
    ("Estado / fechas / reclamos", [
        "estado", "fecha_creacion", "fecha_etiqueta_impresa", "fecha_embalado", "fecha_despachado",
        "fecha_entregado", "numero_reclamo", "fecha_hora_reclamo", "ultima_revision_reclamo",
        "observacion_reclamo", "motivo_no_entregado", "fecha_devolucion", "estado_devolucion",
        "observacion_devolucion", "numero_reclamo_ml", "resultado_reclamo_ml", "monto_recuperado_ml",
        "observacion_reclamo_ml",
    ]),
    ("IA / WhatsApp / reclamos ML", [
        "ml_mensajes_pendientes", "ml_mensajes_pendientes_count", "ultima_sync_mensajes_ml",
        "ia_recolector_estado", "ia_datos_detectados", "ia_faltantes", "ia_resumen",
        "ia_requiere_operador", "wa_estado", "wa_ultimo_contacto", "wa_recordatorio_1",
        "wa_recordatorio_2", "wa_listo_retirar_enviado", "wa_postventa_enviada",
        "correo_sucursales_ofrecidas", "costo_envio", "costo_envio_sucursal", "costo_envio_domicilio",
        "ia_ultimo_mensaje_hash", "ia_ultimo_analisis", "ia_error", "ia_respuesta_sugerida",
        "ia_sucursales_ofrecidas", "ia_respuesta_enviada_hash", "ia_ultima_respuesta_enviada",
        "ia_esperando_respuesta", "ia_ultimo_mensaje_bot", "ia_ultimo_mensaje_cliente", "ia_canal_activo", "ia_ultimo_timeout_operador",
        "ml_claim_id", "ml_claim_abierto", "ml_claim_status", "ml_claim_reason", "ultima_sync_claim_ml",
    ]),
]

ADMIN_PEDIDO_LABELS = {
    "cliente": "Cliente / titular", "dni": "DNI / CUIT", "telefono": "Teléfono", "mail": "Mail",
    "canal": "Canal", "id_venta": "ID venta", "ml_tipo": "Tipo ML", "empresa_envio": "Empresa envío",
    "tipo_entrega": "Tipo entrega", "direccion": "Dirección", "codigo_postal": "Código postal",
    "localidad": "Localidad", "provincia": "Provincia", "observaciones": "Observaciones",
    "sucursal_nombre": "Sucursal", "autorizado_nombre": "Autorizado nombre",
    "autorizado_dni": "Autorizado DNI", "autorizado_telefono": "Autorizado teléfono",
    "seguimiento": "Seguimiento", "estado": "Estado Fierro", "etiqueta_archivo": "Etiqueta archivo/URL",
    "comprobante_dux_archivo": "Comprobante DUX", "wa_estado": "Estado WhatsApp",
    "ia_resumen": "Resumen IA", "ia_requiere_operador": "IA requiere operador",
}


def _admin_valor_a_texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    return str(valor)


def _admin_parse_datetime(valor):
    valor = str(valor or "").strip()
    if not valor:
        return None
    formatos = [
        "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y",
    ]
    for fmt in formatos:
        try:
            return datetime.strptime(valor, fmt)
        except ValueError:
            pass
    raise ValueError(f"Fecha inválida: {valor}. Usá formato YYYY-MM-DD HH:MM.")


def _admin_parse_valor_pedido(campo, valor):
    columna = Pedido.__table__.columns.get(campo)
    if columna is None:
        return None

    valor = str(valor or "").strip()

    try:
        tipo_python = columna.type.python_type
    except Exception:
        tipo_python = str

    if tipo_python is bool:
        if valor == "":
            return None
        return valor.lower() in ["1", "true", "verdadero", "si", "sí", "on", "yes"]

    if tipo_python is int:
        return int(valor) if valor else None

    if tipo_python is float:
        if not valor:
            return None
        return float(valor.replace(",", "."))

    if tipo_python is datetime:
        return _admin_parse_datetime(valor)

    # Campos string/texto. En columnas NOT NULL dejamos cadena vacía, no None.
    if valor == "" and getattr(columna, "nullable", True):
        return None
    return valor


def _admin_tipo_input_pedido(campo):
    columna = Pedido.__table__.columns.get(campo)
    if columna is None:
        return "text"
    try:
        tipo_python = columna.type.python_type
    except Exception:
        tipo_python = str
    if tipo_python is bool:
        return "bool"
    if tipo_python is int:
        return "number"
    if tipo_python is float:
        return "decimal"
    if tipo_python is datetime:
        return "datetime"
    if str(columna.type).upper().startswith("TEXT") or campo in ["observaciones", "ia_resumen", "ia_error", "ml_campos_faltantes", "ml_mensaje_contacto", "andreani_eventos_json"]:
        return "textarea"
    return "text"


def _admin_campos_pedido_para_template(pedido):
    columnas = Pedido.__table__.columns
    usados = set()
    grupos = []

    for titulo, campos in ADMIN_PEDIDO_CAMPOS_GRUPOS:
        lista = []
        for campo in campos:
            if campo not in columnas or campo == "id":
                continue
            usados.add(campo)
            valor = getattr(pedido, campo, None)
            lista.append({
                "name": campo,
                "label": ADMIN_PEDIDO_LABELS.get(campo, campo.replace("_", " ").capitalize()),
                "tipo": _admin_tipo_input_pedido(campo),
                "value": _admin_valor_a_texto(valor),
            })
        if lista:
            grupos.append((titulo, lista))

    otros = []
    for columna in columnas:
        campo = columna.name
        if campo == "id" or campo in usados:
            continue
        valor = getattr(pedido, campo, None)
        otros.append({
            "name": campo,
            "label": ADMIN_PEDIDO_LABELS.get(campo, campo.replace("_", " ").capitalize()),
            "tipo": _admin_tipo_input_pedido(campo),
            "value": _admin_valor_a_texto(valor),
        })
    if otros:
        grupos.append(("Otros campos", otros))

    return grupos


@app.route("/pedido/<int:id>/admin/editar-completo", methods=["GET", "POST"])
@admin_required
def admin_editar_pedido_completo(id):
    pedido = Pedido.query.get_or_404(id)

    if request.method == "POST":
        cambios = []
        try:
            for columna in Pedido.__table__.columns:
                campo = columna.name
                if campo == "id" or campo not in request.form:
                    continue

                valor_anterior = getattr(pedido, campo, None)
                valor_nuevo = _admin_parse_valor_pedido(campo, request.form.get(campo))

                if _admin_valor_a_texto(valor_anterior) != _admin_valor_a_texto(valor_nuevo):
                    cambios.append(
                        f"{campo}: '{_admin_valor_a_texto(valor_anterior)}' → '{_admin_valor_a_texto(valor_nuevo)}'"
                    )
                    setattr(pedido, campo, valor_nuevo)

            db.session.commit()

            detalle = "; ".join(cambios) if cambios else "Sin cambios reales."
            registrar_auditoria(
                "Admin editó pedido completo",
                entidad="pedido",
                entidad_id=pedido.id,
                detalle=detalle,
            )

            return redirect(url_for("detalle_pedido", id=pedido.id, ok="Pedido actualizado por edición completa admin."))

        except Exception as e:
            db.session.rollback()
            return render_template(
                "admin_editar_pedido_completo.html",
                pedido=pedido,
                grupos_campos=_admin_campos_pedido_para_template(pedido),
                error=f"No se pudo guardar la edición completa: {e}",
            )

    return render_template(
        "admin_editar_pedido_completo.html",
        pedido=pedido,
        grupos_campos=_admin_campos_pedido_para_template(pedido),
        error="",
    )


@app.route("/pedido/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_pedido(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_editar_pedido(pedido):
        return redirect(url_for("detalle_pedido", id=pedido.id))

    modo = (request.args.get("modo") or "").strip()
    volver = (request.args.get("volver") or "").strip()
    if modo == "reclamos" and pedido.estado not in ["Despachado", "Verificar llegada a destino", "Listo para retirar", "Con reclamo en transporte", "Con demora de entrega"]:
        return redirect(url_for("detalle_pedido", id=pedido.id))

    if request.method == "POST":
        if modo == "reclamos":
            pedido.numero_reclamo = (request.form.get("numero_reclamo") or "").strip()
            pedido.observacion_reclamo = (request.form.get("observacion_reclamo") or "").strip()
            pedido.motivo_no_entregado = (request.form.get("motivo_no_entregado") or "").strip()

            if hay_reclamo_generado(pedido):
                if not pedido.fecha_hora_reclamo:
                    pedido.fecha_hora_reclamo = datetime.utcnow()
                pedido.ultima_revision_reclamo = datetime.utcnow()
                pedido.estado = Estado.RECLAMO

            db.session.commit()
            return redirect(url_for("detalle_pedido", id=pedido.id))

        if modo == "seguimiento":
            seguimiento_valor = (request.form.get("seguimiento") or "").strip()

            if not seguimiento_valor:
                return render_template(
                    "editar_pedido.html",
                    pedido=pedido,
                    items_texto=items_a_texto(pedido),
                    error="Falta número de seguimiento."
                )

            pedido.seguimiento = seguimiento_valor
            aplicar_autoavance_post_despacho(pedido)

            if (
                es_via_cargo(pedido.empresa_envio)
                and pedido.telefono
                and pedido.seguimiento
            ):
                try:
                    from modules.whatsapp.flows import wa_enviar_numero_seguimiento

                    wa_enviar_numero_seguimiento(pedido)

                except Exception as e:
                    print(f"[WA-DESPACHO] Error enviando seguimiento Vía Cargo: {e}")

            db.session.commit()

            if volver == "detalle":
                return redirect(url_for("detalle_pedido", id=pedido.id))
            return redirect(url_for("inicio"))

        etiqueta_actual = request.form.get("etiqueta_existente", "").strip()
        archivo_etiqueta = request.files.get("etiqueta")

        if archivo_etiqueta and archivo_etiqueta.filename:
            subida = guardar_etiqueta_subida(archivo_etiqueta)
            etiqueta_actual = subida.get("url", "")

        comprobante_dux_actual = request.form.get("comprobante_dux_existente", "").strip()
        archivo_comprobante_dux = request.files.get("comprobante_dux")

        if archivo_comprobante_dux and archivo_comprobante_dux.filename:
            subida_dux = guardar_comprobante_dux_subido(archivo_comprobante_dux)
            comprobante_dux_actual = subida_dux.get("url", "")

        canal = request.form.get("canal")
        ml_tipo = request.form.get("ml_tipo")

        # APB:
        # El canal y el tipo ML son identidad operativa del pedido.
        # Rol carga puede completar datos, pero NO puede transformar
        # un pedido ML/TN/Presencial en otro canal desde el formulario.
        if rol_actual() != "admin":
            canal = pedido.canal
            ml_tipo = pedido.ml_tipo

        empresa_envio = request.form.get("empresa_envio")
        tipo_entrega = request.form.get("tipo_entrega")
        direccion = request.form.get("direccion")
        codigo_postal = request.form.get("codigo_postal")
        localidad = request.form.get("localidad")
        provincia = request.form.get("provincia")
        observaciones = request.form.get("observaciones")
        sucursal_nombre = request.form.get("sucursal_nombre")
        autorizado_nombre = request.form.get("autorizado_nombre")
        autorizado_dni = request.form.get("autorizado_dni")
        autorizado_telefono = request.form.get("autorizado_telefono")

        if canal == "Mercado Libre" and ml_tipo == "Mercado Envíos":
            empresa_envio = ""
            tipo_entrega = ""
            direccion = ""
            codigo_postal = ""
            localidad = ""
            provincia = ""
            observaciones = ""
            sucursal_nombre = ""
            autorizado_nombre = ""
            autorizado_dni = ""
            autorizado_telefono = ""

        pedido.cliente = request.form.get("cliente")
        pedido.dni = request.form.get("dni")
        pedido.telefono = normalizar_telefono(request.form.get("telefono"))
        pedido.mail = request.form.get("mail")
        pedido.canal = canal
        pedido.id_venta = request.form.get("id_venta")
        pedido.ml_tipo = ml_tipo
        pedido.empresa_envio = empresa_envio
        pedido.tipo_entrega = tipo_entrega
        pedido.direccion = direccion
        pedido.codigo_postal = codigo_postal
        pedido.localidad = localidad
        pedido.provincia = provincia
        pedido.observaciones = observaciones
        pedido.sucursal_nombre = sucursal_nombre
        pedido.autorizado_nombre = autorizado_nombre
        pedido.autorizado_dni = autorizado_dni
        pedido.autorizado_telefono = autorizado_telefono
        seguimiento_valor = (request.form.get("seguimiento") or request.form.get("seguimiento_envio") or "").strip()
        pedido.seguimiento = seguimiento_valor

        if (
            es_via_cargo(pedido.empresa_envio)
            and pedido.telefono
            and pedido.seguimiento
        ):
            try:
                from modules.whatsapp.flows import wa_enviar_numero_seguimiento

                wa_enviar_numero_seguimiento(pedido)

            except Exception as e:
                print(f"[WA-DESPACHO] Error enviando seguimiento Vía Cargo desde edición: {e}")

        pedido.etiqueta_archivo = etiqueta_actual
        pedido.comprobante_dux_archivo = comprobante_dux_actual

        if es_guardado_parcial_acordas():
            db.session.commit()

            return redirect(url_for("inicio"))

        items_texto_nuevo = request.form.get("items_texto", "")

        if requiere_comprobante_dux_por_agregado(pedido, canal, ml_tipo, items_texto_nuevo) and not comprobante_dux_actual:
            pedido_temporal = {
                "id": pedido.id,
                "cliente": request.form.get("cliente", ""),
                "dni": request.form.get("dni", ""),
                "telefono": normalizar_telefono(request.form.get("telefono", "")),
                "mail": request.form.get("mail", ""),
                "canal": canal or "",
                "id_venta": request.form.get("id_venta", ""),
                "ml_tipo": ml_tipo or "",
                "empresa_envio": empresa_envio or "",
                "tipo_entrega": tipo_entrega or "",
                "direccion": direccion or "",
                "codigo_postal": codigo_postal or "",
                "localidad": localidad or "",
                "provincia": provincia or "",
                "observaciones": observaciones or "",
                "sucursal_nombre": sucursal_nombre or "",
                "autorizado_nombre": autorizado_nombre or "",
                "autorizado_dni": autorizado_dni or "",
                "autorizado_telefono": autorizado_telefono or "",
                "seguimiento": seguimiento_valor,
                "etiqueta_archivo": etiqueta_actual,
                "comprobante_dux_archivo": comprobante_dux_actual,
                "estado": pedido.estado
            }

            db.session.rollback()
            return render_template(
                "editar_pedido.html",
                pedido=pedido_temporal,
                items_texto=items_texto_nuevo,
                error="Agregaste productos extra a una compra de Mercado Libre / Acordás la Entrega. Para continuar, subí el comprobante DUX correspondiente."
            )

        cargar_items_desde_texto(pedido, items_texto_nuevo)
        actualizar_estado_automatico(pedido)

        errores = motor_bloqueo(pedido)

        if errores:
            db.session.rollback()

            pedido_temporal = {
                "id": pedido.id,
                "cliente": request.form.get("cliente", ""),
                "dni": request.form.get("dni", ""),
                "telefono": normalizar_telefono(request.form.get("telefono", "")),
                "mail": request.form.get("mail", ""),
                "canal": canal or "",
                "id_venta": request.form.get("id_venta", ""),
                "ml_tipo": ml_tipo or "",
                "empresa_envio": empresa_envio or "",
                "tipo_entrega": tipo_entrega or "",
                "direccion": direccion or "",
                "codigo_postal": codigo_postal or "",
                "localidad": localidad or "",
                "provincia": provincia or "",
                "observaciones": observaciones or "",
                "sucursal_nombre": sucursal_nombre or "",
                "autorizado_nombre": autorizado_nombre or "",
                "autorizado_dni": autorizado_dni or "",
                "autorizado_telefono": autorizado_telefono or "",
                "seguimiento": seguimiento_valor,
                "etiqueta_archivo": etiqueta_actual,
                "comprobante_dux_archivo": comprobante_dux_actual,
                "estado": pedido.estado
            }

            return render_template(
                "editar_pedido.html",
                pedido=pedido_temporal,
                items_texto=request.form.get("items_texto", ""),
                error="<br>".join(errores)
            )

        aplicar_autoavance_post_despacho(pedido)

        db.session.commit()

        return redirect(url_for("inicio"))

    return render_template(
        "editar_pedido.html",
        pedido=pedido,
        items_texto=items_a_texto(pedido),
        error=""
    )

def _enviar_whatsapp_api_pedido(pedido, texto, autor="operador"):
    """Envía WhatsApp por API y registra historial. No usa WhatsApp Web."""
    from modules.whatsapp.sender import wa_enviar_texto
    tel = normalizar_telefono(pedido.telefono)
    if not tel:
        registrar_whatsapp_mensaje(pedido, telefono=pedido.telefono, direccion="out", autor=autor, texto=texto, estado="error", error="Pedido sin teléfono válido")
        return False, "El pedido no tiene teléfono válido."
    ok = wa_enviar_texto(tel, texto, pedido=pedido, autor=autor)
    if ok:
        return True, "Mensaje enviado por WhatsApp API."
    return False, "No se pudo enviar por WhatsApp API. Revisá token/configuración Meta."


@app.route("/pedido/<int:id>/whatsapp/enviar", methods=["POST"])
@login_required
def whatsapp_enviar_operador(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_operar_whatsapp(pedido):
        return redirect(url_for(
            "detalle_pedido",
            id=pedido.id,
            error="No autorizado para operar WhatsApp."
        ))

    texto = (request.form.get("mensaje") or "").strip()
    if not texto:
        return redirect(url_for("detalle_pedido", id=pedido.id, error="Escribí un mensaje para enviar por WhatsApp."))

    pedido.wa_estado = "operador_manual"
    ok, msg = _enviar_whatsapp_api_pedido(pedido, texto, autor="operador")
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return redirect(url_for("detalle_pedido", id=pedido.id, ok=msg if ok else "", error="" if ok else msg))

@app.route("/pedido/<int:id>/whatsapp/iniciar-operador", methods=["POST"])
@login_required
def whatsapp_iniciar_chat_operador(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_operar_whatsapp(pedido):
        return redirect(url_for(
            "detalle_pedido",
            id=pedido.id,
            error="No autorizado para operar WhatsApp."
        ))

    tel = normalizar_telefono(pedido.telefono)

    if not tel or len(tel) < 12:
        return redirect(url_for("detalle_pedido", id=pedido.id, error="El pedido no tiene teléfono válido para WhatsApp."))

    try:
        from modules.whatsapp.config import WA_TEMPLATE_INICIO_CHAT_OPERADOR
        from modules.whatsapp.sender import wa_enviar_template

        nombre = (pedido.cliente or "Cliente").split()[0] or "Cliente"
        referencia = f"#{pedido.id_venta or pedido.id}"

        ok = wa_enviar_template(
            tel,
            WA_TEMPLATE_INICIO_CHAT_OPERADOR,
            parametros=[
                nombre,
                referencia,
            ],
            pedido=pedido,
            autor="operador",
        )

        if not ok:
            return redirect(url_for("detalle_pedido", id=pedido.id, error="No se pudo iniciar el chat por WhatsApp API. Revisá token/configuración Meta."))

        pedido.wa_estado = "operador_manual"
        pedido.ia_requiere_operador = True
        pedido.wa_ultimo_contacto = datetime.utcnow()

        actualizar_estado_conversacional(
            pedido,
            owner_actual="operador",
            canal_activo="wa",
            estado_conversacional="takeover_operador",
            takeover_activo=True,
            bot_pausado=True,
        )

        registrar_evento_operativo(
            pedido=pedido,
            tipo_evento="whatsapp_chat_operador_iniciado",
            origen="operador",
            canal="wa",
            owner="operador",
            estado_conversacional="takeover_operador",
            payload={
                "template": WA_TEMPLATE_INICIO_CHAT_OPERADOR,
                "telefono": tel,
                "wa_estado": pedido.wa_estado,
                "ia_requiere_operador": pedido.ia_requiere_operador,
            },
            resultado="ok",
            detalle="Operador inició chat WhatsApp mediante template aprobado. Bot pausado.",
            usuario=session.get("username", ""),
            procesado=True,
        )

        db.session.commit()

        return redirect(url_for("detalle_pedido", id=pedido.id, ok="Chat WhatsApp iniciado por operador mediante plantilla. El bot queda pausado."))

    except Exception as e:
        db.session.rollback()
        return redirect(url_for("detalle_pedido", id=pedido.id, error=f"No se pudo iniciar el chat WhatsApp: {e}"))

@app.route("/pedido/<int:id>/whatsapp/tomar", methods=["POST"])
@login_required
def whatsapp_tomar_conversacion(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_operar_whatsapp(pedido):
        return redirect(url_for(
            "detalle_pedido",
            id=pedido.id,
            error="No autorizado para operar WhatsApp."
        ))

    pedido.wa_estado = "operador_manual"
    pedido.ia_requiere_operador = True
    pedido.wa_ultimo_contacto = datetime.utcnow()
    db.session.commit()

    actualizar_estado_conversacional(
        pedido,
        owner_actual="operador",
        canal_activo="wa",
        estado_conversacional="takeover_operador",
        takeover_activo=True,
        bot_pausado=True,
    )

    registrar_evento_operativo(
        pedido=pedido,
        tipo_evento="takeover_operador",
        origen="operador",
        canal="wa",
        owner="operador",
        estado_conversacional="takeover_operador",
        payload={
            "wa_estado": pedido.wa_estado,
            "ia_requiere_operador": pedido.ia_requiere_operador,
        },
        resultado="ok",
        detalle="Operador tomó control de la conversación WhatsApp. Bot pausado.",
        usuario=session.get("username", ""),
        procesado=True,
    )

    return redirect(url_for("detalle_pedido", id=pedido.id, ok="Conversacion WhatsApp tomada por operador. El bot queda pausado."))


@app.route("/pedido/<int:id>/whatsapp/reactivar", methods=["POST"])
@login_required
def whatsapp_reactivar_bot(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_operar_whatsapp(pedido):
        return redirect(url_for(
            "detalle_pedido",
            id=pedido.id,
            error="No autorizado para operar WhatsApp."
        ))

    pedido.wa_estado = pedido.wa_estado if pedido.wa_estado and pedido.wa_estado != "operador_manual" else "esperando_datos"
    pedido.ia_requiere_operador = False
    pedido.wa_ultimo_contacto = datetime.utcnow()
    db.session.commit()

    actualizar_estado_conversacional(
        pedido,
        owner_actual="bot",
        canal_activo="wa",
        estado_conversacional="recolectando_datos",
        takeover_activo=False,
        bot_pausado=False,
    )

    registrar_evento_operativo(
        pedido=pedido,
        tipo_evento="bot_reactivado",
        origen="operador",
        canal="wa",
        owner="bot",
        estado_conversacional="recolectando_datos",
        payload={
            "wa_estado": pedido.wa_estado,
            "ia_requiere_operador": pedido.ia_requiere_operador,
        },
        resultado="ok",
        detalle="Operador reactivó el bot WhatsApp.",
        usuario=session.get("username", ""),
        procesado=True,
    )

    return redirect(url_for("detalle_pedido", id=pedido.id, ok="Bot WhatsApp reactivado."))

@app.route("/pedido/<int:id>/confirmar-entrega")
@login_required
def confirmar_entrega(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_ver_pedido(pedido):
        return redirect(url_for("inicio"))

    if not requiere_seguimiento_retiro(pedido):
        return redirect(url_for("inicio"))

    pedido.estado = Estado.LISTO_RETIRAR
    db.session.commit()

    registrar_evento_operativo(
        pedido=pedido,
        tipo_evento="pedido_listo_para_retirar",
        origen="operador",
        canal="sistema",
        owner="sistema",
        estado_conversacional="esperando_confirmacion_retiro",
        payload={
            "estado": pedido.estado,
            "sucursal_nombre": pedido.sucursal_nombre,
            "seguimiento": pedido.seguimiento or pedido.tn_tracking_number,
        },
        resultado="ok",
        detalle="Operador marcó el pedido como listo para retirar.",
        usuario=session.get("username", ""),
        procesado=True,
    )

    try:
        from modules.whatsapp.flows import wa_enviar_listo_para_retirar

        ok = wa_enviar_listo_para_retirar(pedido)
        msg = ""

    except Exception as e:
        ok = False
        msg = f"No se pudo enviar WhatsApp listo para retirar: {e}"

    return redirect(url_for("detalle_pedido", id=pedido.id, ok=texto_feedback_estado("Listo para retirar") if ok else "", error="" if ok else msg))

def checklist_cierre_pedido(pedido):
    """Checklist APB para cerrar pedidos entregados sin saltear pasos críticos."""
    items = []



    if pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Acordás la Entrega":
        items.append({
            "clave": "ml_confirmado",
            "texto": "Entrega confirmada / avisada en Mercado Libre.",
            "obligatorio": True,
            "detalle": "Este paso evita que el pedido quede abierto o con pago pendiente en ML.",
        })

    if pedido.tipo_entrega == "Sucursal":
        items.append({
            "clave": "retiro_confirmado",
            "texto": "Cliente retiró el pedido en sucursal.",
            "obligatorio": True,
            "detalle": "No cerrar si solo fue avisado; cerrar cuando el retiro esté confirmado.",
        })

    return items


@app.route("/pedido/<int:id>/cerrar")
@login_required
def cerrar_pedido(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_ver_pedido(pedido):
        return redirect(url_for("inicio"))
    
    if not puede_cerrar_pedido(pedido):
        return redirect(url_for(
            "detalle_pedido",
            id=pedido.id,
            error="Solo Admin o Carga pueden cerrar pedidos entregados y sin reclamo activo."
        ))

    bloqueos = []

    return render_template(
        "cerrar_pedido.html",
        pedido=pedido,
        checklist=checklist_cierre_pedido(pedido),
        bloqueos=bloqueos,
    )


@app.route("/pedido/<int:id>/cerrar/confirmar", methods=["POST"])
@login_required
def confirmar_cierre_pedido(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_ver_pedido(pedido):
        return redirect(url_for("inicio"))

    if not puede_cerrar_pedido(pedido):
        return redirect(url_for(
            "detalle_pedido",
            id=pedido.id,
            error="Solo Admin o Carga pueden cerrar pedidos entregados y sin reclamo activo."
        ))

    faltantes = []
    for item in checklist_cierre_pedido(pedido):
        if item.get("obligatorio") and request.form.get(item["clave"]) != "1":
            faltantes.append(item["texto"])

    if faltantes:
        return render_template(
            "cerrar_pedido.html",
            pedido=pedido,
            checklist=checklist_cierre_pedido(pedido),
            bloqueos=[],
            error="Faltan confirmar pasos obligatorios: " + " / ".join(faltantes),
        )

    pedido.estado = "Finalizado"
    db.session.commit()

    # APB:
    # La postventa ya no bloquea el cierre,
    # pero debe dispararse automáticamente después de finalizar.
    try:
        from modules.whatsapp.flows import wa_enviar_postventa

        wa_enviar_postventa(pedido)

    except Exception as e:
        print(
            f"[WA-POSTVENTA] No se pudo enviar postventa "
            f"pedido #{pedido.id}: {e}"
        )

    return redirect(url_for("detalle_pedido", id=pedido.id, ok=texto_feedback_estado("Finalizado")))


@app.route("/pedido/<int:id>/cerrar-ml")
@login_required
def cerrar_ml(id):
    # Compatibilidad con enlaces anteriores: ahora el cierre pasa por checklist APB.
    return redirect(url_for("cerrar_pedido", id=id))

@app.route("/pedido/<int:id>/marcar-no-entregado")
@login_required
def marcar_no_entregado(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_editar_pedido(pedido):
        return redirect(url_for("detalle_pedido", id=pedido.id))

    if pedido.estado not in ["Despachado", "Con demora de entrega", "Con reclamo en transporte", "Verificar llegada a destino", "Listo para retirar"]:
        return redirect(url_for("detalle_pedido", id=pedido.id))

    pedido.estado = "No entregado"

    if not pedido.motivo_no_entregado:
        pedido.motivo_no_entregado = "Pendiente de gestión de devolución"

    db.session.commit()

    return redirect(url_for("detalle_pedido", id=pedido.id, ok=texto_feedback_estado("No entregado")))

@app.route("/pedido/<int:id>/gestionar-devolucion", methods=["GET", "POST"])
@login_required
def gestionar_devolucion(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_editar_pedido(pedido):
        return redirect(url_for("detalle_pedido", id=pedido.id))

    if pedido.estado != "No entregado":
        return redirect(url_for("detalle_pedido", id=pedido.id))

    if request.method == "POST":
        form_data = {
            "fecha_devolucion": (request.form.get("fecha_devolucion") or "").strip(),
            "estado_devolucion": (request.form.get("estado_devolucion") or "").strip(),
            "observacion_devolucion": (request.form.get("observacion_devolucion") or "").strip(),
        }

        for item in pedido.items:
            form_data[f"estado_item_{item.id}"] = (request.form.get(f"estado_item_{item.id}") or "").strip()
            form_data[f"cantidad_ok_{item.id}"] = (request.form.get(f"cantidad_ok_{item.id}") or "0").strip() or "0"
            form_data[f"cantidad_danada_{item.id}"] = (request.form.get(f"cantidad_danada_{item.id}") or "0").strip() or "0"
            form_data[f"obs_item_{item.id}"] = (request.form.get(f"obs_item_{item.id}") or "").strip()

        fecha_devolucion_raw = form_data["fecha_devolucion"]
        estado_devolucion = form_data["estado_devolucion"]
        observacion_devolucion = form_data["observacion_devolucion"]

        if not fecha_devolucion_raw:
            return render_template(
                "gestionar_devolucion.html",
                pedido=pedido,
                error="Tenés que cargar la fecha de recepción de la devolución.",
                form_data=form_data
            )

        if not estado_devolucion:
            return render_template(
                "gestionar_devolucion.html",
                pedido=pedido,
                error="Tenés que indicar el estado de la devolución.",
                form_data=form_data
            )

        try:
            pedido.fecha_devolucion = datetime.strptime(fecha_devolucion_raw, "%Y-%m-%dT%H:%M")
        except ValueError:
            return render_template(
                "gestionar_devolucion.html",
                pedido=pedido,
                error="La fecha de devolución no tiene un formato válido.",
                form_data=form_data
            )

        for item in pedido.items:
            estado_item = form_data[f"estado_item_{item.id}"]
            obs_item = form_data[f"obs_item_{item.id}"]

            try:
                cantidad_ok = int(form_data[f"cantidad_ok_{item.id}"])
                cantidad_danada = int(form_data[f"cantidad_danada_{item.id}"])
            except ValueError:
                return render_template(
                    "gestionar_devolucion.html",
                    pedido=pedido,
                    error=f"Las cantidades del item {item.sku} no son válidas.",
                    form_data=form_data
                )

            if not estado_item:
                return render_template(
                    "gestionar_devolucion.html",
                    pedido=pedido,
                    error=f"Tenés que indicar el estado del item {item.sku}.",
                    form_data=form_data
                )

            if cantidad_ok < 0 or cantidad_danada < 0:
                return render_template(
                    "gestionar_devolucion.html",
                    pedido=pedido,
                    error=f"Las cantidades del item {item.sku} no pueden ser negativas.",
                    form_data=form_data
                )

            total = item.cantidad or 0

            if cantidad_ok + cantidad_danada == 0:
                return render_template(
                    "gestionar_devolucion.html",
                    pedido=pedido,
                    error=f"Tenés que indicar al menos una cantidad para el item {item.sku}.",
                    form_data=form_data
                )

            if cantidad_ok + cantidad_danada > total:
                return render_template(
                    "gestionar_devolucion.html",
                    pedido=pedido,
                    error=f"La suma de cantidades del item {item.sku} supera la cantidad original.",
                    form_data=form_data
                )

            if estado_item == "ok" and cantidad_danada > 0:
                return render_template(
                    "gestionar_devolucion.html",
                    pedido=pedido,
                    error=f"El item {item.sku} está marcado como OK pero tiene cantidad dañada.",
                    form_data=form_data
                )

            if estado_item == "danado" and cantidad_ok > 0:
                return render_template(
                    "gestionar_devolucion.html",
                    pedido=pedido,
                    error=f"El item {item.sku} está marcado como dañado pero tiene cantidad OK.",
                    form_data=form_data
                )

            item.estado_devolucion_item = estado_item
            item.cantidad_devuelta_ok = cantidad_ok
            item.cantidad_devuelta_danada = cantidad_danada
            item.observacion_devolucion_item = obs_item

        pedido.estado_devolucion = estado_devolucion
        pedido.observacion_devolucion = observacion_devolucion

        requiere_reclamo_ml = False

        if pedido.canal == "Mercado Libre":
            for item in pedido.items:
                if (
                    item.estado_devolucion_item in ["parcial", "danado"]
                    or (item.cantidad_devuelta_danada or 0) > 0
                ):
                    requiere_reclamo_ml = True
                    break

        if requiere_reclamo_ml:
            pedido.estado = "Reclamar a Mercado Libre"
        else:
            pedido.estado = "Finalizado"

        db.session.commit()
        return redirect(url_for("detalle_pedido", id=pedido.id))

    form_data = {
        "fecha_devolucion": pedido.fecha_devolucion.strftime("%Y-%m-%dT%H:%M") if pedido.fecha_devolucion else "",
        "estado_devolucion": pedido.estado_devolucion or "",
        "observacion_devolucion": pedido.observacion_devolucion or "",
    }

    for item in pedido.items:
        form_data[f"estado_item_{item.id}"] = item.estado_devolucion_item or ""
        form_data[f"cantidad_ok_{item.id}"] = str(item.cantidad_devuelta_ok or 0)
        form_data[f"cantidad_danada_{item.id}"] = str(item.cantidad_devuelta_danada or 0)
        form_data[f"obs_item_{item.id}"] = item.observacion_devolucion_item or ""

    return render_template(
        "gestionar_devolucion.html",
        pedido=pedido,
        error="",
        form_data=form_data
    )
@app.route("/pedido/<int:id>/cerrar-reclamo-ml-devolucion", methods=["GET", "POST"])
@login_required
def cerrar_reclamo_ml_devolucion(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_editar_pedido(pedido):
        return redirect(url_for("detalle_pedido", id=pedido.id))

    if pedido.estado != "Reclamar a Mercado Libre":
        return redirect(url_for("detalle_pedido", id=pedido.id))

    if request.method == "POST":
        numero_reclamo_ml = (request.form.get("numero_reclamo_ml") or "").strip()
        resultado_reclamo_ml = (request.form.get("resultado_reclamo_ml") or "").strip()
        monto_recuperado_raw = (request.form.get("monto_recuperado_ml") or "").strip()
        observacion_reclamo_ml = (request.form.get("observacion_reclamo_ml") or "").strip()

        if not numero_reclamo_ml:
            return render_template(
                "cerrar_reclamo_ml_devolucion.html",
                pedido=pedido,
                error="Tenés que cargar el número de reclamo de Mercado Libre."
            )

        if not resultado_reclamo_ml:
            return render_template(
                "cerrar_reclamo_ml_devolucion.html",
                pedido=pedido,
                error="Tenés que indicar el resultado del reclamo."
            )

        if not monto_recuperado_raw:
            return render_template(
                "cerrar_reclamo_ml_devolucion.html",
                pedido=pedido,
                error="Tenés que indicar el monto recuperado."
            )

        try:
            monto_recuperado_ml = float(monto_recuperado_raw.replace(",", "."))
        except ValueError:
            return render_template(
                "cerrar_reclamo_ml_devolucion.html",
                pedido=pedido,
                error="El monto recuperado no es válido."
            )

        if monto_recuperado_ml < 0:
            return render_template(
                "cerrar_reclamo_ml_devolucion.html",
                pedido=pedido,
                error="El monto recuperado no puede ser negativo."
            )

        pedido.numero_reclamo_ml = numero_reclamo_ml
        pedido.resultado_reclamo_ml = resultado_reclamo_ml
        pedido.monto_recuperado_ml = monto_recuperado_ml
        pedido.observacion_reclamo_ml = observacion_reclamo_ml
        pedido.estado = "Finalizado"

        db.session.commit()
        return redirect(url_for("detalle_pedido", id=pedido.id))

    return render_template(
        "cerrar_reclamo_ml_devolucion.html",
        pedido=pedido,
        error=""
    )

    pedido.estado = "Finalizado"
    db.session.commit()

    return redirect(url_for("detalle_pedido", id=pedido.id))
    
@app.route("/pedido/<int:id>/revisar-reclamo")
@login_required
def revisar_reclamo(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_editar_pedido(pedido):
        return redirect(url_for("detalle_pedido", id=pedido.id))

    if pedido.estado != "Con reclamo en transporte":
        return redirect(url_for("detalle_pedido", id=pedido.id))

    pedido.ultima_revision_reclamo = datetime.utcnow()

    if not pedido.fecha_hora_reclamo:
        pedido.fecha_hora_reclamo = datetime.utcnow()

    db.session.commit()

    return redirect(url_for("detalle_pedido", id=pedido.id, ok="Reclamo revisado correctamente."))


@app.route("/pedido/<int:id>/confirmar-revision-agregado", methods=["POST"])
@login_required
def confirmar_revision_agregado(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_ver_pedido(pedido):
        return redirect(url_for("inicio"))

    if rol_actual() not in ["admin", "despacho"]:
        return redirect(url_for(
            "detalle_pedido",
            id=pedido.id,
            error="Solo despacho o admin pueden confirmar la revisión del agregado."
        ))

    if not getattr(pedido, "agregado_pendiente_revision", False):
        return redirect(url_for(
            "detalle_pedido",
            id=pedido.id,
            ok="El pedido no tiene agregados pendientes de revisión."
        ))

    pedido.agregado_pendiente_revision = False
    pedido.agregado_revision_fecha = datetime.utcnow()
    pedido.agregado_revision_usuario = usuario_actual().username if usuario_actual() else ""

    registrar_auditoria(
        "Confirmó revisión de agregado APB",
        entidad="pedido",
        entidad_id=pedido.id,
        detalle="Despacho confirmó que revisó los items agregados antes de despachar."
    )

    db.session.commit()

    if rol_actual() == "despacho" and es_dispositivo_movil():

        return redirect(url_for(
            "despacho_mobile",
            ok="Agregado revisado por despacho. Ya se puede continuar el despacho."
        ))

    return redirect(url_for(
        "detalle_pedido",
        id=pedido.id,
        ok="Agregado revisado por despacho. Ya se puede continuar el despacho."
    ))

@app.route("/pedido/<int:id>/avanzar")
@login_required
def avanzar_pedido(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_ver_pedido(pedido):
        return redirect(url_for("inicio"))

    puede_avanzar, errores = puede_avanzar_pedido(pedido)

    if not puede_avanzar:
        if rol_actual() == "despacho" and es_dispositivo_movil():
            return redirect(url_for("despacho_mobile", ok="No se pudo avanzar: " + " / ".join(errores)))
        return render_template(
            "detalle_pedido.html",
            pedido=pedido,
            error="<br>".join(errores),
            ok_feedback="",
            accion_sugerida=accion_sugerida_pedido(pedido),
            texto_boton=texto_boton_estado(pedido),
            hay_autorizado=hay_autorizado,
            puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,            
            notas_pedido=[]
        )
    
    estado_anterior = pedido.estado
    nuevo = siguiente_estado(pedido.estado)

    if nuevo in ["Embalado", "Despachado"] and pedido.canal == "Mercado Libre":
        orden_ok, mensaje_ml = ml_validar_orden_operable_antes_de_despacho(pedido)
        if not orden_ok:
            if rol_actual() == "despacho" and es_dispositivo_movil():
                return redirect(url_for("despacho_mobile", ok=mensaje_ml))
            return redirect(url_for("detalle_pedido", id=pedido.id, error=mensaje_ml))

    if nuevo:
        aplicar_estado_y_fechas(pedido, nuevo)
        db.session.commit()

    mensaje_ok = texto_feedback_estado(pedido.estado)

    if rol_actual() == "despacho" and es_dispositivo_movil():
        return redirect(url_for("despacho_mobile", ok=mensaje_ok))

    # Si queda Embalado, mantener al operador dentro del detalle
    # para continuar directo con el despacho. Aplica también a admin.
    if pedido.estado == Estado.EMBALADO:
        return redirect(url_for("detalle_pedido", id=pedido.id, ok=mensaje_ok))

    if (
        pedido.estado == Estado.ENTREGADO
        and pedido.canal == "Mercado Libre"
        and pedido.ml_tipo == "Acordás la Entrega"
    ):
        return redirect(url_for("detalle_pedido", id=pedido.id, ok=mensaje_ok))

    if rol_actual() == "despacho":
        return redirect(url_for("inicio", ok=mensaje_ok))

    if rol_actual() == "carga":
        return redirect(url_for("detalle_pedido", id=pedido.id, ok=mensaje_ok))

    return redirect(url_for("inicio", ok=mensaje_ok))

def ia_llamar_openai_chat(prompt, temperatura=0.4):
    return ia_llamar_openai_chat_service(
        prompt,
        temperatura=temperatura,
    )



def asegurar_configuracion_inicial():
    """Carga defaults editables en DB para no hardcodear reglas operativas."""
    defaults = {
        "MAX_COSTO_ENVIO": ("0", "Tope interno de costo de envío. 0 = sin tope hasta configurarlo."),
        "MAX_PORCENTAJE_DOMICILIO": ("20", "Máximo porcentaje extra permitido para domicilio vs sucursal Correo."),
        "TRACKING_INTERVALO_MINUTOS": ("60", "Intervalo sugerido para consultar tracking externo."),
    }
    for clave, (valor, descripcion) in defaults.items():
        if not ConfiguracionSistema.query.filter_by(clave=clave).first():
            db.session.add(ConfiguracionSistema(clave=clave, valor=valor, descripcion=descripcion))
    db.session.commit()


def extraer_items_comprobante_dux_desde_pdf(archivo_pdf):
    """
    Lee un comprobante DUX en PDF con texto real y devuelve todos los items detectados.

    Soporta dos formas de extracción de DUX:
    1) Fila en una sola línea:
       C-MDF-151 CUADRO FRASES 3 PIEZAS 43X20 1,00 14.450,99 ...
    2) Columnas separadas por líneas, como devuelve PyMuPDF en algunos PDF:
       C-MDF-151
       CUADRO FRASES 3 PIEZAS 43X20
       1,00
       14.450,99
       ...

    Regla APB:
    - El SKU manda.
    - Si el SKU existe en la base de productos, se usa esa descripción.
    - La descripción del PDF queda como fallback.
    - La cantidad se toma de la columna Cant., no de números dentro de la descripción.
    """
    items = []
    texto = ""

    if not archivo_pdf or not archivo_pdf.filename:
        return {"ok": False, "items": [], "texto": "", "error": "No se recibió archivo PDF."}

    try:
        archivo_pdf.stream.seek(0)
        contenido = archivo_pdf.read()
        archivo_pdf.stream.seek(0)

        doc = fitz.open(stream=contenido, filetype="pdf")
        try:
            partes = []
            for page in doc:
                partes.append(page.get_text("text") or "")
            texto = "\n".join(partes)
        finally:
            doc.close()
    except Exception as e:
        try:
            archivo_pdf.stream.seek(0)
        except Exception:
            pass
        return {"ok": False, "items": [], "texto": "", "error": f"No se pudo leer el PDF DUX: {e}"}

    lineas = [l.strip() for l in texto.splitlines() if l and l.strip()]

    def _es_sku(valor):
        valor = (valor or "").strip().upper()
        return bool(re.match(r"^[A-Z0-9][A-Z0-9_\-\.\/]{1,40}$", valor))

    def _es_importe(valor):
        valor = (valor or "").strip()
        return bool(re.match(r"^\$?\s*[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}$|^\$?\s*[0-9]+,[0-9]{2}$", valor))

    def _parse_cantidad(valor):
        valor = (valor or "").strip().replace(".", "").replace(",", ".")
        try:
            cantidad_float = float(valor)
            cantidad = int(cantidad_float) if cantidad_float.is_integer() else int(round(cantidad_float))
        except Exception:
            cantidad = 1
        return max(cantidad, 1)

    def _descripcion_por_sku(sku, descripcion_pdf):
        """Devuelve la descripción correcta del item DUX.

        Regla APB:
        - Si el código es NOCODE / sin código, se usa SIEMPRE la descripción del PDF.
        - Si el SKU existe en catálogo pero su descripción está vacía o es "-", se usa la descripción del PDF.
        - Si el SKU existe en catálogo con descripción real, se usa la descripción del catálogo.
        """
        sku_norm = (sku or "").strip().upper()
        descripcion_pdf = re.sub(r"\s+", " ", (descripcion_pdf or "").strip(" -")).strip()

        if sku_norm in {"NOCODE", "NO-CODE", "NO_CODE", "SINCODIGO", "SIN-CODIGO", "SIN_CODIGO"}:
            return descripcion_pdf or sku_norm

        descripcion = descripcion_pdf
        try:
            producto = Producto.query.filter(Producto.sku.ilike(sku_norm)).first()
            if producto and producto.descripcion:
                desc_catalogo = re.sub(r"\s+", " ", (producto.descripcion or "").strip()).strip()
                if desc_catalogo and desc_catalogo not in {"-", ".", "NOCODE", "NO CODE", "SIN DESCRIPCION", "SIN DESCRIPCIÓN"}:
                    descripcion = desc_catalogo
        except Exception:
            pass

        return descripcion or sku_norm

    def _agregar_item(sku, descripcion_pdf, cantidad, linea_original):
        sku = (sku or "").strip().upper()
        descripcion = _descripcion_por_sku(sku, descripcion_pdf)
        if not sku or not descripcion:
            return
        clave = (sku, descripcion, cantidad)
        if clave in vistos:
            return
        vistos.add(clave)
        items.append({
            "sku": sku,
            "descripcion": descripcion,
            "cantidad": cantidad,
            "linea_original": linea_original,
        })

    vistos = set()

    # Caso 1: DUX extraído en una sola línea por item.
    patron_linea = re.compile(
        r"^([A-Z0-9][A-Z0-9_\-\.\/]{1,40})\s+(?:-\s+)?(.+?)\s+"
        r"([0-9]+(?:[\.,][0-9]{1,3})?)\s+"
        r"([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+,[0-9]{2})\s+"
        r"([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+,[0-9]{2})",
        re.IGNORECASE,
    )

    for linea in lineas:
        m = patron_linea.search(linea)
        if not m:
            continue
        sku = m.group(1)
        descripcion_pdf = (m.group(2) or "").strip(" -")
        cantidad = _parse_cantidad(m.group(3))
        _agregar_item(sku, descripcion_pdf, cantidad, linea)

    # Caso 2: DUX/PyMuPDF extrae cada columna en líneas separadas.
    # Estructura esperada:
    # SKU / DESCRIPCION / CANTIDAD / PRECIO / SUBTOTAL / IVA / TOTAL
    i = 0
    while i < len(lineas):
        sku = lineas[i].strip().upper()
        if not _es_sku(sku):
            i += 1
            continue

        # Evitar falsos positivos en encabezados o datos generales.
        if sku in {"COMPROBANTE", "FECHA", "IVA", "DNI", "TOTAL", "SUBTOTAL", "CANT", "CODIGO", "CÓDIGO", "DESCRIPCION", "DESCRIPCIÓN"}:
            i += 1
            continue

        if i + 2 >= len(lineas):
            i += 1
            continue

        descripcion_pdf = lineas[i + 1].strip()
        cantidad_txt = lineas[i + 2].strip()

        if not descripcion_pdf or _es_sku(descripcion_pdf):
            i += 1
            continue

        # La cantidad debe ser decimal tipo 1,00 y seguida por al menos un precio.
        if not re.match(r"^[0-9]+(?:[\.,][0-9]{1,3})?$", cantidad_txt):
            i += 1
            continue

        if i + 3 < len(lineas) and not _es_importe(lineas[i + 3]):
            i += 1
            continue

        cantidad = _parse_cantidad(cantidad_txt)
        linea_original = " | ".join(lineas[i:i + 7])
        _agregar_item(sku, descripcion_pdf, cantidad, linea_original)
        i += 7

    return {
        "ok": bool(items),
        "items": items,
        "texto": texto[:4000],
        "error": "" if items else "No se detectaron items en el comprobante DUX.",
    }

@app.route("/pedido/<int:id>/agregar-item", methods=["GET", "POST"])
@login_required
def agregar_item_pedido(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_agregar_item(pedido):
        registrar_auditoria(
            "Intento no autorizado de agregar item",
            entidad="pedido",
            entidad_id=id,
            detalle=(
                f"Rol: {rol_actual()} | "
                f"Estado pedido: {pedido.estado}"
            )
        )

        return redirect(url_for(
            "detalle_pedido",
            id=pedido.id,
            error="No se pueden agregar items en el estado actual del pedido."
        ))

    datos_form = {
        "comprobante_dux_url": "",
        "comprobante_dux_public_id": "",
        "comprobante_pago_url": "",
        "comprobante_pago_public_id": "",
        "items_json": "",
    }
    items_detectados = []
    mensaje_ok = ""
    error = ""

    if request.method == "POST":
        accion = (request.form.get("accion") or "guardar").strip()
        archivo_dux = request.files.get("comprobante_dux")
        archivo_pago = request.files.get("comprobante_pago")

        datos_form["comprobante_dux_url"] = (request.form.get("comprobante_dux_url") or "").strip()
        datos_form["comprobante_dux_public_id"] = (request.form.get("comprobante_dux_public_id") or "").strip()
        datos_form["comprobante_pago_url"] = (request.form.get("comprobante_pago_url") or "").strip()
        datos_form["comprobante_pago_public_id"] = (request.form.get("comprobante_pago_public_id") or "").strip()
        datos_form["items_json"] = (request.form.get("items_json") or "").strip()
        items_detectados = _items_agregado_desde_json(datos_form["items_json"])

        if accion == "leer_pdf":
            if not archivo_dux or not archivo_dux.filename:
                error = "Subí un comprobante DUX en PDF para leer los items."
                return render_template("agregar_item_pedido.html", pedido=pedido, error=error, datos=datos_form, items_detectados=items_detectados, mensaje_ok=mensaje_ok)

            nombre_archivo = (archivo_dux.filename or "").lower()
            if not nombre_archivo.endswith(".pdf"):
                error = "La lectura automática solo funciona con PDF de DUX. Subí el comprobante DUX en PDF."
                return render_template("agregar_item_pedido.html", pedido=pedido, error=error, datos=datos_form, items_detectados=items_detectados, mensaje_ok=mensaje_ok)

            resultado_pdf = extraer_items_comprobante_dux_desde_pdf(archivo_dux)
            items_detectados = resultado_pdf.get("items", []) or []

            if not items_detectados:
                error = resultado_pdf.get("error") or "No se detectaron items en el comprobante DUX."
                return render_template("agregar_item_pedido.html", pedido=pedido, error=error, datos=datos_form, items_detectados=items_detectados, mensaje_ok=mensaje_ok)

            archivo_dux.stream.seek(0)
            comprobante_dux = guardar_comprobante_dux_subido(archivo_dux)
            if not comprobante_dux.get("url"):
                error = "Se leyeron los items, pero no se pudo guardar el comprobante DUX. Volvé a intentar."
                return render_template("agregar_item_pedido.html", pedido=pedido, error=error, datos=datos_form, items_detectados=items_detectados, mensaje_ok=mensaje_ok)

            datos_form["comprobante_dux_url"] = comprobante_dux.get("url", "")
            datos_form["comprobante_dux_public_id"] = comprobante_dux.get("public_id", "")
            datos_form["items_json"] = json.dumps(items_detectados, ensure_ascii=False)
            mensaje_ok = "Comprobante DUX leído. Se van a agregar todos los items detectados. Cargá el comprobante de pago y confirmá."

            return render_template("agregar_item_pedido.html", pedido=pedido, error="", datos=datos_form, items_detectados=items_detectados, mensaje_ok=mensaje_ok)

        comprobante_dux_url = datos_form["comprobante_dux_url"]
        comprobante_dux_public_id = datos_form["comprobante_dux_public_id"]
        comprobante_pago_url = datos_form["comprobante_pago_url"]
        comprobante_pago_public_id = datos_form["comprobante_pago_public_id"]
        items_detectados = _items_agregado_desde_json(datos_form["items_json"])

        if not comprobante_dux_url:
            return render_template(
                "agregar_item_pedido.html",
                pedido=pedido,
                error="Primero tenés que leer y guardar el comprobante DUX del agregado.",
                datos=datos_form,
                items_detectados=items_detectados,
                mensaje_ok=mensaje_ok,
            )

        if not items_detectados:
            return render_template(
                "agregar_item_pedido.html",
                pedido=pedido,
                error="No hay items detectados para agregar. Volvé a leer el PDF DUX.",
                datos=datos_form,
                items_detectados=items_detectados,
                mensaje_ok=mensaje_ok,
            )

        if not comprobante_pago_url:
            if not archivo_pago or not archivo_pago.filename:
                return render_template(
                    "agregar_item_pedido.html",
                    pedido=pedido,
                    error="Adjuntá el comprobante de pago del agregado. Sin comprobante de pago no se guarda.",
                    datos=datos_form,
                    items_detectados=items_detectados,
                    mensaje_ok=mensaje_ok,
                )
            comprobante_pago = guardar_comprobante_pago_agregado_subido(archivo_pago)
            comprobante_pago_url = comprobante_pago.get("url", "")
            comprobante_pago_public_id = comprobante_pago.get("public_id", "")

        if not comprobante_pago_url:
            return render_template(
                "agregar_item_pedido.html",
                pedido=pedido,
                error="No se pudo guardar el comprobante de pago. Volvé a intentar.",
                datos=datos_form,
                items_detectados=items_detectados,
                mensaje_ok=mensaje_ok,
            )

        agregado = PedidoAgregadoAPB(
            pedido_id=pedido.id,
            usuario=(usuario_actual().username if usuario_actual() else ""),
            rol=rol_actual(),
            comprobante_dux_url=comprobante_dux_url,
            comprobante_dux_public_id=comprobante_dux_public_id,
            comprobante_pago_url=comprobante_pago_url,
            comprobante_pago_public_id=comprobante_pago_public_id,
            items_json=json.dumps(items_detectados, ensure_ascii=False),
        )
        db.session.add(agregado)

        for item_data in items_detectados:
            db.session.add(PedidoItem(
                pedido_id=pedido.id,
                sku=item_data.get("sku", ""),
                descripcion=item_data.get("descripcion", "") or item_data.get("sku", ""),
                cantidad=item_data.get("cantidad", 1),
            ))

        # Mantener compatibilidad con el campo histórico del pedido: queda el último DUX vinculado.
        pedido.comprobante_dux_archivo = comprobante_dux_url

        # APB:
        # Si el agregado se cargó cuando el pedido ya estaba en preparación,
        # despacho debe revisarlo antes de poder marcarlo como despachado.
        if pedido.estado in ESTADOS_DESPACHO_OPERATIVO:
            pedido.agregado_pendiente_revision = True
            pedido.agregado_revision_fecha = None
            pedido.agregado_revision_usuario = None

        db.session.commit()

        resumen_items = ", ".join([f"{i.get('sku')} x{i.get('cantidad')}" for i in items_detectados])
        registrar_auditoria(
            "Agregó items APB con comprobante DUX y pago",
            entidad="pedido",
            entidad_id=pedido.id,
            detalle=(
                f"Agregado APB #{agregado.id}. Items: {resumen_items}. "
                f"Comprobante DUX: {comprobante_dux_url}. "
                f"Comprobante pago: {comprobante_pago_url}. "
                f"Cloudinary DUX public_id: {comprobante_dux_public_id}. "
                f"Cloudinary pago public_id: {comprobante_pago_public_id}"
            )
        )

        return redirect(url_for("detalle_pedido", id=pedido.id, ok=f"Agregado APB confirmado: {len(items_detectados)} item(s)."))

    return render_template("agregar_item_pedido.html", pedido=pedido, error="", datos=datos_form, items_detectados=items_detectados, mensaje_ok=mensaje_ok)

def asegurar_usuarios_iniciales():

    # APB:
    # Nunca recrear usuarios automáticos si ya existe cualquier usuario.
    # Evita sobrescrituras o bootstrap accidental en producción.
    if UsuarioSistema.query.count() > 0:
        return

    # Seguridad:
    # No crear usuarios default automáticamente en Render/producción.
    # Solo permitir bootstrap local explícito.
    if os.environ.get("RENDER"):
        print("[APB] Bootstrap de usuarios omitido en Render.")
        return

    usuarios_base = [
        ("admin", "admin123", "admin", "Administrador"),
        ("carga", "carga123", "carga", "Operador de Carga"),
        ("despacho", "despacho123", "despacho", "Embalaje y Despacho"),
    ]
    for username, password, rol, nombre in usuarios_base:
        db.session.add(UsuarioSistema(
            username=username,
            password_hash=generate_password_hash(password),
            rol=rol,
            nombre=nombre,
            activo=True,
            creado_por="sistema",
        ))
    db.session.commit()



with app.app_context():
    db.create_all()
    
    asegurar_columnas_extra()
    asegurar_columnas_integracion_ml()
    asegurar_columnas_integracion_tn()
    asegurar_usuarios_iniciales()
    asegurar_configuracion_inicial()

    # ── Módulo WhatsApp Bot ──────────────────────────────────────────
    # Para activar: configurar WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID
    # y WHATSAPP_VERIFY_TOKEN en el .env y descomentar la línea siguiente:
    from modules.whatsapp import activar; activar(app)

# ── Scheduler: jobs periódicos ───────────────────────────────────
try:
    scheduler_enabled = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"

    if scheduler_enabled:
        from modules.automation.manager import iniciar_scheduler

        def _job_ml_mensajes():
            from modules.automation.jobs.ml_messages import ejecutar_job_ml_mensajes

            ejecutar_job_ml_mensajes(
                app,
                db
            )

        def _job_wa_timers():
            from modules.automation.jobs.wa_timers import ejecutar_job_wa_timers

            ejecutar_job_wa_timers(
                app,
                db
            )

        iniciar_scheduler(
            _job_ml_mensajes,
            _job_wa_timers
        )
    else:
        print("[SCHEDULER] Deshabilitado por SCHEDULER_ENABLED=false")
except Exception as e:
    print("[SCHEDULER] No se pudo iniciar:", e)
