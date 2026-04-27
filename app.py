import os
import re
import json
import hashlib
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlencode
import pandas as pd
import numpy as np
import fitz
import cloudinary
import cloudinary.uploader
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, redirect, render_template, url_for, jsonify, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, inspect, or_
from werkzeug.utils import secure_filename

app = Flask(__name__)
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
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "uploads")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "fierro-apb-roles-v1")

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)

USUARIOS = {
    "admin": {"password": "admin123", "rol": "admin", "nombre": "Administrador"},
    "carga": {"password": "carga123", "rol": "carga", "nombre": "Operador de Carga"},
    "despacho": {"password": "despacho123", "rol": "despacho", "nombre": "Embalaje y Despacho"},
}


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
    # APB RECLAMOS ML
    # =====================
    asegurar_columna_si_no_existe("ml_claim_id", "VARCHAR(50)")
    asegurar_columna_si_no_existe("ml_claim_abierto", "BOOLEAN DEFAULT FALSE")
    asegurar_columna_si_no_existe("ml_claim_status", "VARCHAR(50)")
    asegurar_columna_si_no_existe("ml_claim_reason", "VARCHAR(200)")
    asegurar_columna_si_no_existe("ultima_sync_claim_ml", "TIMESTAMP")


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
    telefono = "" if raw is None else str(raw).strip()

    if not telefono:
        return ""

    telefono = telefono.replace("+", "")
    solo_digitos = re.sub(r"\D", "", telefono)

    if solo_digitos.startswith("549"):
        return solo_digitos

    if solo_digitos.startswith("54"):
        resto = solo_digitos[2:]
        if resto.startswith("9"):
            return "54" + resto
        return "549" + resto

    if solo_digitos.startswith("15"):
        solo_digitos = solo_digitos[2:]

    return "549" + solo_digitos


def whatsapp_link_pedido(pedido):
    numero = normalizar_telefono(pedido.telefono)
    if not numero:
        return ""

    mensaje = f"Hola {pedido.cliente or ''}, te escribimos de Fierro por tu pedido #{pedido.id}."
    from urllib.parse import quote
    return f"https://wa.me/{numero}?text={quote(mensaje)}"

def requiere_seguimiento_retiro(pedido):
    return bool(
        pedido.estado == "Verificar llegada a destino"
        and pedido.tipo_entrega == "Sucursal"
        and (
            (
                pedido.canal == "Mercado Libre"
                and pedido.ml_tipo == "Acordás la Entrega"
            )
            or (
                pedido.canal == "Tienda Nube"
                and pedido.empresa_envio == "Vía Cargo"
            )
            or (
                pedido.canal == "Mayorista"
                and pedido.empresa_envio == "Vía Cargo"
            )
        )
    )


def whatsapp_link_confirmar_entrega(pedido):
    numero = normalizar_telefono(pedido.telefono)
    if not numero:
        return ""

    mensaje = (
        f"Hola {pedido.cliente or ''}, te escribimos de Fierro por tu pedido #{pedido.id}. "
        f"Tu compra ya está disponible para retirar en sucursal. "
        f"Cuando la retires, por favor avisame así cerramos la entrega. ¡Gracias!"
    )

    from urllib.parse import quote
    return f"https://wa.me/{numero}?text={quote(mensaje)}"

def es_mercado_envios(pedido):
    return pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Mercado Envíos"


def es_tnube(pedido):
    return pedido.canal == "Tienda Nube"


def es_tnube_via_cargo(pedido):
    return es_tnube(pedido) and pedido.empresa_envio == "Vía Cargo"


def es_mayorista(pedido):
    return pedido.canal == "Mayorista"


def es_mayorista_via_cargo(pedido):
    return es_mayorista(pedido) and pedido.empresa_envio == "Vía Cargo"


def usa_flujo_etiqueta_directa(pedido):
    return es_mercado_envios(pedido) or (es_tnube(pedido) and pedido.empresa_envio in ["Andreani", "Correo Argentino"])


def es_ml_acordas_entrega(pedido):
    return pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Acordás la Entrega"


def usa_flujo_acordas_entrega(pedido):
    return es_ml_acordas_entrega(pedido) or es_tnube_via_cargo(pedido) or es_mayorista_via_cargo(pedido)


def puede_imprimir_etiqueta_directamente(pedido):
    return bool(
        usa_flujo_etiqueta_directa(pedido)
        and pedido.etiqueta_archivo
        and len(pedido.items) > 0
    )


def despacho_completo(pedido):
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
            pedido.empresa_envio == "Vía Cargo"
            or bool(pedido.etiqueta_archivo)
        )
    )


def requiere_contacto_cliente(pedido):
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
    if pedido.estado == "Cargando Pedido" and (
        puede_imprimir_etiqueta_directamente(pedido)
        or puede_imprimir_acordas_entrega(pedido)
    ):
        pedido.estado = "Etiqueta Lista"
        return

    if debe_pasar_a_demora_entrega(pedido):
        pedido.estado = "Con demora de entrega"


def aplicar_autoavance_post_despacho(pedido):
    if pedido.estado != "Despachado":
        return

    if pedido.empresa_envio == "Vía Cargo":
        if pedido.seguimiento:
            pedido.estado = "Verificar llegada a destino"
        return

    if (
        pedido.canal == "Mercado Libre"
        and pedido.ml_tipo == "Acordás la Entrega"
        and pedido.empresa_envio in ["Andreani", "Correo Argentino"]
        and pedido.seguimiento
    ):
        pedido.estado = "Verificar llegada a destino"


def aplicar_estado_y_fechas(pedido, nuevo_estado):
    if not nuevo_estado:
        return

    pedido.estado = nuevo_estado
    ahora = datetime.utcnow()

    if nuevo_estado == "Etiqueta Impresa":
        if not pedido.fecha_etiqueta_impresa:
            pedido.fecha_etiqueta_impresa = ahora
    elif nuevo_estado == "Embalado":
        pedido.fecha_embalado = ahora
    elif nuevo_estado == "Despachado":
        pedido.fecha_despachado = ahora
        aplicar_autoavance_post_despacho(pedido)
    elif nuevo_estado == "Entregado":
        pedido.fecha_entregado = ahora

        if usa_flujo_etiqueta_directa(pedido) or es_tnube_via_cargo(pedido) or es_mayorista_via_cargo(pedido):
            pedido.estado = "Finalizado"


def motor_bloqueo(pedido):
    errores = []

    if not pedido.cliente:
        errores.append("Falta cliente.")

    if not pedido.canal:
        errores.append("Falta canal.")

    if not pedido.items:
        errores.append("No hay productos cargados.")

    if pedido.canal == "Mercado Libre":
        if not pedido.ml_tipo:
            errores.append("Falta tipo de envío ML.")

        elif pedido.ml_tipo == "Mercado Envíos":
            if not pedido.seguimiento:
                errores.append("Falta seguimiento ML.")
            if not pedido.etiqueta_archivo:
                errores.append("Falta adjuntar etiqueta.")

        elif pedido.ml_tipo == "Acordás la Entrega":
            if parece_nickname_ml(pedido.cliente, pedido.ml_buyer_nickname) and not (pedido.ml_billing_nombre or "").strip():
                errores.append("Falta nombre real del cliente.")
            if not (pedido.dni or "").strip() and not (pedido.ml_billing_documento or "").strip():
                errores.append("Falta DNI/CUIT del cliente.")
            if not (pedido.telefono or "").strip():
                errores.append("Falta teléfono del cliente.")

    requiere_datos_envio = True

    if usa_flujo_acordas_entrega(pedido) and not despacho_completo(pedido):
        requiere_datos_envio = False

    if requiere_datos_envio and pedido.empresa_envio:
        if not pedido.tipo_entrega:
            errores.append("Falta tipo de entrega.")

        if pedido.tipo_entrega == "Domicilio":
            if not pedido.direccion or not pedido.localidad or not pedido.provincia:
                errores.append("Faltan datos domicilio.")
            if not pedido.codigo_postal:
                errores.append("Falta CP.")

        if pedido.tipo_entrega == "Sucursal":
            if not pedido.sucursal_nombre:
                errores.append("Falta nombre de sucursal.")
            if not pedido.direccion or not pedido.localidad or not pedido.provincia:
                errores.append("Faltan datos sucursal.")

            if hay_autorizado(pedido):
                if not pedido.autorizado_nombre:
                    errores.append("Falta nombre del autorizado.")
                if not pedido.autorizado_dni:
                    errores.append("Falta DNI del autorizado.")
                if not pedido.autorizado_telefono:
                    errores.append("Falta teléfono del autorizado.")

    if requiere_datos_envio and not pedido.empresa_envio and not usa_flujo_etiqueta_directa(pedido):
        errores.append("Falta transporte.")

    if pedido.empresa_envio in ["Andreani", "Correo Argentino"]:
        if not pedido.seguimiento:
            errores.append("Falta número de seguimiento.")
        if not pedido.etiqueta_archivo:
            errores.append("Falta adjuntar etiqueta.")

    if es_tnube(pedido) and not pedido.empresa_envio:
        errores.append("Falta transporte.")

    return errores


def siguiente_estado(e):
    flujo = {
        "Cargando Pedido": "Etiqueta Lista",
        "Etiqueta Lista": "Etiqueta Impresa",
        "Etiqueta Impresa": "Embalado",
        "Embalado": "Despachado",
        "Despachado": "Entregado",
        "Con demora de entrega": "Entregado",
        "Con reclamo en transporte": "Entregado",
        "Verificar llegada a destino": "Entregado",
        "Listo para retirar": "Entregado",
    }
    return flujo.get(e)


def texto_boton_estado(pedido):
    if pedido.estado == "Cargando Pedido":
        if requiere_contacto_cliente(pedido):
            return "Contactar cliente"
        if puede_imprimir_etiqueta_directamente(pedido):
            return "Imprimir etiqueta"
        if pedido.empresa_envio == "Vía Cargo":
            return "Preparar pedido"
        return "Generar etiqueta"

    if pedido.estado == "Etiqueta Lista":
        return "Imprimir etiqueta"

    if pedido.estado == "Etiqueta Impresa":
        return "Marcar embalado"

    if pedido.estado == "Embalado":
        return "Marcar despachado"

    if pedido.estado in ["Despachado", "Con demora de entrega", "Con reclamo en transporte"]:
        if pedido.empresa_envio == "Vía Cargo" and not pedido.seguimiento:
            return "Cargar seguimiento"
        return "Marcar entregado"

    if pedido.estado == "Verificar llegada a destino":
        if pedido.tipo_entrega == "Sucursal":
            return "Avisar al cliente"
        return "Marcar entregado"

    if pedido.estado == "Listo para retirar":
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
        "Verificar llegada a destino": "Pedido despachado correctamente.",
        "Listo para retirar": "Cliente avisado correctamente.",
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

        if pedido.empresa_envio == "Vía Cargo":
            return "Pedido listo para imprimir etiqueta"

        return "Pedido listo para generar etiqueta"

    if pedido.estado == "Etiqueta Lista":
        return "Imprimir etiqueta"

    if pedido.estado == "Etiqueta Impresa":
        return "Embalar pedido"

    if pedido.estado == "Embalado":
        return "Despachar pedido"

    if pedido.estado == "Con demora de entrega":
        return "Iniciar reclamo"

    if pedido.estado in ["Despachado", "Con reclamo en transporte"]:
        if pedido.empresa_envio == "Vía Cargo" and not pedido.seguimiento:
            return "Cargar seguimiento"
        return "Confirmar entrega"

    if pedido.estado == "Verificar llegada a destino":
        return "Hacer seguimiento"

    if pedido.estado == "Listo para retirar":
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

    # Paso 3: Envío
    if requiere_contacto_cliente(pedido):
        return 3

    if pedido.empresa_envio and not pedido.tipo_entrega:
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

    if requiere_contacto_cliente(pedido):
        return {
            "tipo": "completar_carga",
            "texto": "Completar carga",
            "url": url_for("editar_pedido", id=pedido.id, paso=primer_paso_pendiente_carga(pedido)),
            "clases": clase_confirmar,
            "target": "",
        }

    if puede_imprimir_pedido(pedido):
        return {
            "tipo": "imprimir_etiqueta",
            "texto": "Imprimir etiqueta",
            "url": url_for("lanzar_impresion", id=pedido.id, origen=origen),
            "clases": "btn btn-accion-rapida btn-confirmar" if es_inicio else "btn btn-accion-rapida btn-confirmar",
            "target": "_blank" if es_inicio else "",
        }

    if pedido.estado == "Verificar llegada a destino" and rol in ["carga", "admin"] and pedido.tipo_entrega == "Sucursal":
        return {
            "tipo": "avisar_cliente",
            "texto": "Avisar al Cliente",
            "url": url_for("confirmar_entrega", id=pedido.id),
            "clases": clase_confirmar,
            "target": "_blank",
        }

    if pedido.estado == "Listo para retirar" and rol in ["carga", "admin"] and pedido.tipo_entrega == "Sucursal":
        return {
            "tipo": "marcar_entregado",
            "texto": "Marcar entregado",
            "url": url_for("avanzar_pedido", id=pedido.id),
            "clases": clase_confirmar,
            "target": "",
        }

    if pedido.estado == "Verificar llegada a destino" and rol in ["carga", "admin"] and pedido.tipo_entrega == "Domicilio":
        return {
            "tipo": "marcar_entregado",
            "texto": "Marcar entregado",
            "url": url_for("avanzar_pedido", id=pedido.id),
            "clases": clase_confirmar,
            "target": "",
        }

    if pedido.estado == "Entregado" and rol in ["carga", "admin"] and pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Acordás la Entrega":
        return {
            "tipo": "cerrar_ml",
            "texto": "Ya avisé Mercado Libre",
            "url": url_for("cerrar_ml", id=pedido.id),
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

    if (rol == "admin") or (rol == "carga" and pedido.estado in ["Despachado", "Con demora de entrega", "Con reclamo en transporte", "No entregado"]) or (rol == "despacho" and pedido.estado in ["Etiqueta Impresa", "Embalado"]):
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
    if pedido.estado == "Etiqueta Impresa":
        return pedido.fecha_etiqueta_impresa or pedido.fecha_creacion

    if pedido.estado == "Embalado":
        return pedido.fecha_embalado or pedido.fecha_etiqueta_impresa or pedido.fecha_creacion

    if pedido.estado in ["Despachado", "Con demora de entrega", "Con reclamo en transporte", "Verificar llegada a destino", "Listo para retirar", "No entregado"]:
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

    # RECLAMOS ML SIEMPRE CRÍTICOS
    if pedido.estado == "Reclamar a Mercado Libre":
        return "rojo"
    # ---------------------------
    # PEDIDOS DESPACHADOS (seguimiento)
    # ---------------------------
    if pedido.estado in ["Despachado", "Con demora de entrega", "Con reclamo en transporte", "Verificar llegada a destino", "Listo para retirar", "No entregado"]:
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

    pedidos = Pedido.query.all()

    sin_despachar = 0
    sin_carga = 0
    seguimiento = 0
    reclamos_sin_revision = 0

    for pedido in pedidos:
        if pedido.estado == "Cargando Pedido" and pedido.fecha_creacion:
            if (ahora - pedido.fecha_creacion).total_seconds() >= 4 * 3600:
                sin_carga += 1

        if pedido.estado in ["Etiqueta Lista", "Etiqueta Impresa", "Embalado"]:
            ref = fecha_referencia_estado(pedido)
            if ref and (ahora - ref).total_seconds() >= 24 * 3600:
                sin_despachar += 1

        if pedido.empresa_envio == "Vía Cargo" and pedido.estado in ["Despachado", "Con demora de entrega", "Con reclamo en transporte", "Verificar llegada a destino", "Listo para retirar"]:
            ref = pedido.fecha_despachado or fecha_referencia_estado(pedido)
            if ref and (ahora - ref).total_seconds() >= 72 * 3600:
                seguimiento += 1

        if pedido.estado == "Con reclamo en transporte":
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
        if sin_carga:
            alertas.append({"tipo": "amarilla", "texto": f"{sin_carga} pedidos con carga incompleta desde hace más de 4 hs"})

        if seguimiento:
            alertas.append({"tipo": "amarilla", "texto": f"{seguimiento} pedidos para seguimiento logístico (72 hs)"})

        if reclamos_sin_revision:
            alertas.append({"tipo": "roja", "texto": f"{reclamos_sin_revision} pedidos con reclamo sin revisar desde hace más de 24 hs"})

    return alertas


def pedido_sin_despacho(pedido):
    return bool(
        pedido
        and pedido.estado not in ["Despachado", "Con demora de entrega", "Con reclamo en transporte", "Verificar llegada a destino", "Listo para retirar", "No entregado", "Entregado", "Finalizado"]
    )


def resumen_operativo(pedidos):
    resumen = {
        "rojo": 0,
        "amarillo": 0,
        "verde": 0,
        "gris": 0,
        "sin_despacho": 0,
        "total": 0,
    }

    for pedido in pedidos:
        color = semaforo_pedido(pedido)
        resumen[color] = resumen.get(color, 0) + 1
        if pedido_sin_despacho(pedido):
            resumen["sin_despacho"] += 1
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
            or (canal == "Tienda Nube" and empresa_envio == "Vía Cargo")
        )
        and accion_guardado_paso2() in ["guardar_y_seguir_despues", "coordinar_whatsapp"]
    )

def usuario_actual():
    username = session.get("username")
    if not username:
        return None
    return USUARIOS.get(username)


def rol_actual():
    usuario = usuario_actual()
    if not usuario:
        return ""
    return usuario["rol"]


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not usuario_actual():
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def estados_visibles_inicio():
    rol = rol_actual()

    if rol == "admin":
        return [
            "Cargando Pedido",
            "Etiqueta Lista",
            "Etiqueta Impresa",
            "Embalado",
            "Despachado",
            "Con demora de entrega",
            "Con reclamo en transporte",
            "Verificar llegada a destino",
            "Listo para retirar",
            "No entregado",
            "Reclamar a Mercado Libre",
            "Entregado",
        ]

    if rol == "carga":
        return ["Cargando Pedido", "Despachado", "Con demora de entrega", "Con reclamo en transporte", "Verificar llegada a destino", "Listo para retirar", "No entregado", "Reclamar a Mercado Libre", "Entregado"]

    if rol == "despacho":
        return ["Etiqueta Lista", "Etiqueta Impresa", "Embalado"]

    return []


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
        return pedido.estado in ["Cargando Pedido", "Despachado", "Con demora de entrega", "Con reclamo en transporte", "Verificar llegada a destino", "Listo para retirar", "No entregado", "Entregado"]

    if rol == "despacho":
        return pedido.estado in ["Etiqueta Lista", "Etiqueta Impresa", "Embalado"]

    return False





def puede_editar_pedido(pedido):
    rol = rol_actual()

    if rol == "admin":
        return True

    if rol == "carga":
        return pedido.estado in ["Cargando Pedido", "Despachado", "Con demora de entrega", "Con reclamo en transporte", "Verificar llegada a destino", "Listo para retirar", "No entregado", "Reclamar a Mercado Libre", "Entregado"]

    return False


def puede_eliminar_pedido(pedido):
    # APB: solo Admin puede borrar pedidos, sin importar estado/canal/instancia.
    return rol_actual() == "admin"


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

    imprimible = pedido.estado == "Etiqueta Lista"

    if rol == "admin":
        return pedido.estado not in ["Entregado", "Finalizado"] and imprimible

    if rol == "despacho":
        return pedido.estado not in ["Entregado", "Finalizado"] and imprimible

    return False


def puede_contactar_cliente(pedido):
    rol = rol_actual()
    if rol not in ["admin", "carga"]:
        return False
    return requiere_contacto_cliente(pedido) and bool(whatsapp_link_pedido(pedido))


def requiere_cargar_seguimiento(pedido):
    return bool(
        pedido.estado in ["Despachado", "Con reclamo en transporte"]
        and pedido.empresa_envio == "Vía Cargo"
        and not pedido.seguimiento
    )


def puede_avanzar_segun_rol(pedido):
    rol = rol_actual()

    if rol == "admin":
        return True, []

    if rol == "carga":
        if pedido.estado in ["Despachado", "Con demora de entrega", "Con reclamo en transporte", "Verificar llegada a destino", "Listo para retirar", "No entregado", "Reclamar a Mercado Libre"]:
            return True, []
        return False, ["Este estado lo trabaja Embalaje y Despacho."]

    if rol == "despacho":
        if pedido.estado in ["Etiqueta Impresa", "Embalado"]:
            return True, []
        return False, ["Este estado lo trabaja el operador de Carga."]

    return False, ["No tenés permisos para esta acción."]


def puede_avanzar_pedido(pedido):
    errores = motor_bloqueo(pedido)

    if pedido.estado == "Cargando Pedido" and errores:
        return False, errores

    if pedido.estado == "Despachado":
        if pedido.empresa_envio == "Vía Cargo" and not pedido.seguimiento:
            return False, ["En Vía Cargo el seguimiento se carga después del despacho."]

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


def puede_administrar_integraciones():
    return rol_actual() == "admin"


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


def tracking_info_pedido(pedido):
    """Devuelve acceso rapido al seguimiento del pedido.

    Regla APB:
    - Andreani y Via Cargo abren directo el seguimiento.
    - Correo Argentino no tiene URL directa confiable: copia el seguimiento y abre el formulario correcto.
    - Mercado Envios se trata como Correo ML aunque empresa_envio venga guardada como "Mercado Envios".
    """
    if not pedido:
        return None

    seguimiento = str(getattr(pedido, "seguimiento", None) or "").strip()
    if not seguimiento:
        return None

    transporte = str(getattr(pedido, "empresa_envio", None) or "").strip().lower()
    tipo_ml = str(getattr(pedido, "ml_tipo", None) or "").strip().lower()

    es_mercado_envios = (
        "mercado envios" in tipo_ml
        or "mercado envíos" in tipo_ml
        or "mercado envios" in transporte
        or "mercado envíos" in transporte
    )

    # Mercado Envios usa el formulario especial de Correo Argentino ML,
    # incluso cuando el campo transporte queda como "Mercado Envios".
    if es_mercado_envios:
        return {
            "url": "https://www.correoargentino.com.ar/formularios/mercadolibre",
            "copiar": True,
            "seguimiento": seguimiento,
            "titulo": "Copiar seguimiento y abrir Correo Argentino Mercado Libre",
        }

    if "andreani" in transporte:
        return {
            "url": f"https://www.andreani.com/envio/{seguimiento}",
            "copiar": False,
            "seguimiento": seguimiento,
            "titulo": "Abrir seguimiento Andreani",
        }

    if "via cargo" in transporte or "vía cargo" in transporte:
        return {
            "url": f"https://viacargo.com.ar/seguimiento-de-envio/{seguimiento}/",
            "copiar": False,
            "seguimiento": seguimiento,
            "titulo": "Abrir seguimiento Via Cargo",
        }

    if "correo" in transporte:
        return {
            "url": "https://www.correoargentino.com.ar/formularios/e-commerce",
            "copiar": True,
            "seguimiento": seguimiento,
            "titulo": "Copiar seguimiento y abrir Correo Argentino e-commerce",
        }

    return None


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
        "Etiqueta Lista",
        "Etiqueta Impresa",
        "Embalado",
        "Despachado",
        "Verificar llegada a destino",
        "Listo para retirar",
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
            return ml_api_post_json(path, payload)
        except Exception as e:
            ultimo_error = e
            print("No se pudo enviar mensaje ML por", path, e)

    raise ValueError(str(ultimo_error or "No se pudo enviar el mensaje a Mercado Libre."))
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


def ml_logistica_no_operable(order, shipment):
    shipping = order.get("shipping") or {}
    tags = order.get("tags") or []

    valores = [
        shipment.get("logistic_type"),
        shipment.get("mode"),
        shipping.get("logistic_type"),
        shipping.get("mode"),
    ]

    valores_normalizados = [str(v or "").lower().strip() for v in valores]
    tags_normalizados = [str(t or "").lower().strip() for t in tags]

    if (
        "fulfillment" in valores_normalizados
        or "fulfillment" in tags_normalizados
        or "meli_full" in tags_normalizados
        or "mercado_envios_full" in tags_normalizados
        or "full" in tags_normalizados
    ):
        return True, "Mercado Envíos Full"

    if (
        "self_service" in valores_normalizados
        or "self_service" in tags_normalizados
        or "flex" in valores_normalizados
        or "flex" in tags_normalizados
        or "mercado_envios_flex" in tags_normalizados
    ):
        return True, "Mercado Envíos Flex"

    return False, ""


def ml_es_envio_full(order, shipment):
    no_operable, motivo = ml_logistica_no_operable(order, shipment)
    return no_operable and motivo == "Mercado Envíos Full"


def ml_es_mercado_envios_order(order, shipment=None):
    return ml_mapear_tipo(order or {}, shipment or {}) == "Mercado Envíos"


def ml_envio_ya_despachado(order, shipment=None):
    shipment = shipment or {}
    shipping = (order or {}).get("shipping") or {}
    estados = {
        str(shipment.get("status") or "").lower().strip(),
        str(shipping.get("status") or "").lower().strip(),
    }
    estados.discard("")
    return bool(estados.intersection({"shipped", "delivered", "not_delivered", "cancelled", "returned"}))


CLAIM_ESTADOS_BLOQUEANTES = {"opened", "under_review", "mediating", "claim_opened"}


def ml_obtener_claim_de_order(order_id, pack_id=None):
    """
    Busca un reclamo activo para una order/pack en Mercado Libre.
    Devuelve el claim dict o None.
    """
    order_id = str(order_id or "").strip()
    pack_id = str(pack_id or "").strip()

    consultas = []
    if order_id:
        consultas.append({"order_id": order_id, "role": "seller", "limit": 5})
        consultas.append({"resource_id": order_id, "role": "seller", "limit": 5})
    if pack_id and pack_id != order_id:
        consultas.append({"resource_id": pack_id, "role": "seller", "limit": 5})

    for params in consultas:
        try:
            data = ml_api_get("/post-purchase/v1/claims/search", params=params)
            claims = []
            if isinstance(data, dict):
                claims = data.get("data") or data.get("results") or data.get("claims") or []
            elif isinstance(data, list):
                claims = data

            if not isinstance(claims, list):
                claims = []

            for claim in claims:
                status = str((claim or {}).get("status") or "").lower().strip()
                if status in CLAIM_ESTADOS_BLOQUEANTES:
                    return claim

        except Exception as e:
            print(f"[ML-CLAIMS] Error buscando claim params={params}: {e}")

    return None


def ml_marcar_claim_en_pedido(pedido, claim):
    """Guarda o limpia datos del reclamo ML en el pedido."""
    if not pedido:
        return

    if claim:
        pedido.ml_claim_id = str(claim.get("id") or claim.get("claim_id") or "").strip()
        pedido.ml_claim_abierto = True
        pedido.ml_claim_status = str(claim.get("status") or "").lower().strip()
        pedido.ml_claim_reason = str(claim.get("reason_id") or claim.get("type") or claim.get("stage") or "").strip()
    else:
        pedido.ml_claim_abierto = False
        pedido.ml_claim_status = ""
        pedido.ml_claim_reason = ""

    pedido.ultima_sync_claim_ml = datetime.utcnow()


def ml_sync_claims_pedidos_operativos():
    """
    Consulta claims para pedidos ML operativos.
    Respaldo para cuando el webhook no trae/impacta el evento.
    """
    cuenta = cuenta_ml_actual()
    if not cuenta:
        return 0

    estados_operativos = [
        "Cargando Pedido",
        "Etiqueta Lista",
        "Etiqueta Impresa",
        "Embalado",
        "Despachado",
        "Verificar llegada a destino",
        "Listo para retirar",
        "Con demora de entrega",
        "Con reclamo en transporte",
        "Con reclamo por demora",
    ]

    pedidos = Pedido.query.filter(
        Pedido.canal == "Mercado Libre",
        Pedido.estado.in_(estados_operativos)
    ).all()

    marcados = 0

    for pedido in pedidos:
        order_id = str(getattr(pedido, "id_venta", "") or "").strip()
        pack_id = str(getattr(pedido, "ml_pack_id", "") or "").strip()
        if not order_id and not pack_id:
            continue

        claim = ml_obtener_claim_de_order(order_id, pack_id)
        ml_marcar_claim_en_pedido(pedido, claim)
        if claim:
            marcados += 1

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[ML-CLAIMS-SYNC] Error commit: {e}")

    return marcados


def ml_pedido_tiene_claim(pedido):
    return bool(pedido and getattr(pedido, "ml_claim_abierto", False))


def ml_validar_orden_operable_antes_de_despacho(pedido):
    """
    Revalida en vivo contra Mercado Libre antes de embalar o despachar.
    Evita operar pedidos que se cancelaron o cambiaron de estado en ML
    entre la ultima sincronizacion y la accion del operador.
    """
    if not pedido or pedido.canal != "Mercado Libre" or not pedido.id_venta:
        return True, ""

    try:
        order = ml_obtener_order(pedido.id_venta)
        if not order:
            return True, ""

        estado_order = str(order.get("status") or "").lower().strip()
        pedido.ml_order_status = estado_order or pedido.ml_order_status

        shipping = order.get("shipping") or {}
        shipping_id = str(shipping.get("id") or pedido.ml_shipping_id or "").strip()
        shipment = ml_obtener_shipment(shipping_id) if shipping_id else {}

        estado_shipping = str((shipment or {}).get("status") or shipping.get("status") or "").lower().strip()
        if estado_shipping:
            pedido.ml_shipping_status = estado_shipping
        if shipping_id:
            pedido.ml_shipping_id = shipping_id
        pedido.ultima_sync_ml = datetime.utcnow()

        estados_order_bloqueados = {"cancelled", "invalid"}
        estados_shipping_bloqueados = {"cancelled", "not_delivered", "returned"}
        estados_shipping_ya_operados = {"shipped", "delivered"}

        if estado_order in estados_order_bloqueados:
            db.session.commit()
            return False, f"Mercado Libre informa que la venta esta {estado_order}. No corresponde embalar ni despachar."

        if estado_shipping in estados_shipping_bloqueados:
            db.session.commit()
            return False, f"Mercado Libre informa que el envio esta {estado_shipping}. No corresponde embalar ni despachar."

        if pedido.ml_tipo == "Mercado Envíos" and estado_shipping in estados_shipping_ya_operados:
            db.session.commit()
            return False, f"Mercado Libre informa que el envio ya figura {estado_shipping}. Revisar la venta antes de operar."

        # --- APB: bloquear operación si ML tiene reclamo activo ---
        if getattr(pedido, "ml_claim_abierto", False):
            db.session.commit()
            return False, (
                f"Este pedido tiene un reclamo activo en Mercado Libre "
                f"(ID: {pedido.ml_claim_id or 'sin ID'}). "
                "No corresponde embalar ni despachar. Atender el reclamo primero."
            )

        claim_live = ml_obtener_claim_de_order(pedido.id_venta, getattr(pedido, "ml_pack_id", "") or "")
        if claim_live:
            ml_marcar_claim_en_pedido(pedido, claim_live)
            db.session.commit()
            return False, (
                f"Mercado Libre reporta un reclamo activo "
                f"({claim_live.get('reason_id') or claim_live.get('type') or 'sin motivo informado'}). "
                "No corresponde embalar ni despachar. Atender el reclamo primero."
            )

        db.session.commit()
        return True, ""

    except Exception as e:
        db.session.rollback()
        print("No se pudo revalidar orden ML antes de embalar/despachar:", e)
        return True, ""


def ml_preparar_etiqueta_mercado_envios(order, shipment=None):
    shipping = (order or {}).get("shipping") or {}
    shipment = shipment or {}
    shipping_id = str(shipping.get("id") or shipment.get("id") or "").strip()
    if not shipping_id:
        return ""
    nombre_pdf = ml_guardar_etiqueta_pdf(shipping_id)
    if not nombre_pdf:
        return ""
    return os.path.basename(str(nombre_pdf))


def ml_order_debe_omitirse(order, shipment=None):
    order_id = str(order.get("id") or "").strip()
    if not order_id:
        return True, "sin ID de orden"

    estado = str(order.get("status") or "").lower().strip()
    if estado in ["cancelled", "invalid"]:
        return True, f"estado ML {estado}"

    no_operable, motivo = ml_logistica_no_operable(order, shipment or {})
    if no_operable:
        return True, motivo

    return False, ""


def ml_borrar_pedido_importado_si_corresponde(pedido):
    if not pedido:
        return False

    if pedido.canal != "Mercado Libre":
        return False

    if pedido.origen != "mercadolibre":
        return False

    if pedido.estado != "Cargando Pedido":
        return False

    db.session.delete(pedido)
    return True


def ml_upsert_pedido_desde_order(order):
    order_id = str(order.get("id") or "").strip()

    omitir, motivo_omision = ml_order_debe_omitirse(order)
    if omitir:
        pedido_existente = ml_pedido_existente_por_order_id(order_id)
        if ml_borrar_pedido_importado_si_corresponde(pedido_existente):
            return None, False, f"{motivo_omision} - pedido importado eliminado"
        return None, False, motivo_omision

    shipment = ml_obtener_shipment((order.get("shipping") or {}).get("id"))

    omitir, motivo_omision = ml_order_debe_omitirse(order, shipment)
    if omitir:
        pedido_existente = ml_pedido_existente_por_order_id(order_id)
        if ml_borrar_pedido_importado_si_corresponde(pedido_existente):
            return None, False, f"{motivo_omision} - pedido importado eliminado"
        return None, False, motivo_omision

    etiqueta_ml_preparada = ""
    if ml_es_mercado_envios_order(order, shipment):
        if ml_envio_ya_despachado(order, shipment):
            pedido_existente = ml_pedido_existente_por_order_id(order_id)
            if ml_borrar_pedido_importado_si_corresponde(pedido_existente):
                return None, False, "Mercado Envíos ya enviado - pedido importado eliminado"
            return None, False, "Mercado Envíos ya enviado"

        etiqueta_ml_preparada = ml_preparar_etiqueta_mercado_envios(order, shipment)
        if not etiqueta_ml_preparada:
            pedido_existente = ml_pedido_existente_por_order_id(order_id)
            if ml_borrar_pedido_importado_si_corresponde(pedido_existente):
                return None, False, "__ML_ME_SIN_ETIQUETA__ - pedido importado eliminado"
            return None, False, "__ML_ME_SIN_ETIQUETA__"

    billing_info = ml_obtener_billing_info(order_id)

    pedido = ml_pedido_existente_por_order_id(order_id)
    creado = pedido is None

    if creado:
        pedido = Pedido(
            cliente=ml_nombre_cliente(order, shipment),
            canal="Mercado Libre",
            id_venta=order_id,
            estado="Cargando Pedido",
            origen="mercadolibre",
        )
        db.session.add(pedido)

    pedido.origen = "mercadolibre"
    pedido.canal = "Mercado Libre"
    pedido.id_venta = order_id

    pedido.mail = pedido.mail or ""
    pedido.telefono = pedido.telefono or ""
    pedido.observaciones = (pedido.observaciones or "").strip()
    pedido.ml_pack_id = str(order.get("pack_id") or "").strip() or pedido.ml_pack_id
    pedido.ml_order_status = order.get("status") or pedido.ml_order_status
    pedido.ultima_sync_ml = datetime.utcnow()
    if etiqueta_ml_preparada:
        pedido.etiqueta_archivo = etiqueta_ml_preparada

    ml_aplicar_datos_envio(pedido, order, shipment)
    ml_aplicar_apb_en_pedido(pedido, order, shipment, billing_info)

    order_items = order.get("order_items") or []
    existentes = {str(item.sku or "").strip(): item for item in pedido.items}
    usados = set()

    for order_item in order_items:
        item_data = order_item.get("item") or {}
        sku = str(item_data.get("seller_sku") or item_data.get("id") or "").strip()
        if not sku:
            sku = str(item_data.get("id") or "SIN-SKU").strip()

        descripcion = str(item_data.get("title") or "Producto ML").strip()
        cantidad = int(order_item.get("quantity") or 1)

        item = existentes.get(sku)
        if item is None:
            item = PedidoItem(sku=sku, descripcion=descripcion, cantidad=cantidad)
            pedido.items.append(item)
        else:
            item.descripcion = descripcion
            item.cantidad = cantidad
        usados.add(sku)

    if pedido.estado == "Cargando Pedido":
        for sku, item in list(existentes.items()):
            if sku not in usados:
                db.session.delete(item)

    estado_anterior = pedido.estado
    actualizar_estado_automatico(pedido)

    if not creado and estado_anterior != pedido.estado and estado_anterior != "Cargando Pedido":
        pedido.estado = estado_anterior

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
    pedidos = (
        Pedido.query
        .filter_by(canal="Mercado Libre", origen="mercadolibre", estado="Cargando Pedido")
        .order_by(Pedido.id.asc())
        .all()
    )

    eliminados = 0
    detalles = []

    for pedido in pedidos:
        order_id = str(pedido.id_venta or "").strip()
        if not order_id:
            continue

        order = ml_obtener_order(order_id)
        if not order:
            continue

        shipment = ml_obtener_shipment((order.get("shipping") or {}).get("id"))
        omitir, motivo = ml_order_debe_omitirse(order, shipment)

        if omitir and ml_borrar_pedido_importado_si_corresponde(pedido):
            eliminados += 1
            detalles.append(f"{order_id}: eliminado ({motivo})")

    return eliminados, detalles


def ml_sync_manual(limit=20):
    cuenta = cuenta_ml_actual()
    if not cuenta:
        raise ValueError("No hay cuenta de Mercado Libre conectada.")

    eliminados_existentes, detalles_eliminados = ml_limpiar_pedidos_ml_no_operables_existentes()

    orders = ml_obtener_orders_recientes(cuenta, limit=limit)
    creados = 0
    actualizados = 0
    omitidos = 0
    errores = list(detalles_eliminados)
    mercado_envios_sin_etiqueta = 0
    mercado_envios_sin_etiqueta_ids = []

    for order in orders:
        order_id = str(order.get("id") or "").strip() or "sin_id"
        try:
            pedido, creado, motivo_omision = ml_upsert_pedido_desde_order(order)
            if not pedido:
                omitidos += 1
                if motivo_omision and "__ML_ME_SIN_ETIQUETA__" in motivo_omision:
                    mercado_envios_sin_etiqueta += 1
                    mercado_envios_sin_etiqueta_ids.append(order_id)
                    errores.append(f"{order_id}: omitido (Mercado Envíos sin etiqueta)")
                elif motivo_omision:
                    errores.append(f"{order_id}: omitido ({motivo_omision})")
                continue

            if creado:
                creados += 1
            else:
                actualizados += 1
        except Exception as e:
            omitidos += 1
            errores.append(f"{order_id}: {e}")

    mensajes_pendientes = ml_sync_mensajes_pendientes_pedidos()
    claims_marcados = ml_sync_claims_pedidos_operativos()

    cuenta.last_sync_at = datetime.utcnow()
    cuenta.last_sync_status = "ok" if not errores else "parcial"

    detalle = f"Pedidos leídos: {len(orders)} | Nuevos: {creados} | Actualizados: {actualizados} | Omitidos: {omitidos} | Eliminados no operables: {eliminados_existentes} | Mensajes ML pendientes: {mensajes_pendientes} | Reclamos ML detectados: {claims_marcados}"
    if errores:
        detalle += " | Detalle: " + " ; ".join(errores[:5])

    cuenta.last_sync_detail = detalle

    session["ml_me_sin_etiqueta_count"] = mercado_envios_sin_etiqueta
    session["ml_me_sin_etiqueta_ids"] = mercado_envios_sin_etiqueta_ids[:10]

    db.session.commit()

    return {
        "leidos": len(orders),
        "creados": creados,
        "actualizados": actualizados,
        "omitidos": omitidos,
        "eliminados": eliminados_existentes,
        "mensajes_pendientes": mensajes_pendientes,
        "claims_marcados": claims_marcados,
        "errores": errores,
        "me_sin_etiqueta": mercado_envios_sin_etiqueta,
    }


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
        "puede_contactar_cliente": puede_contactar_cliente,
        "whatsapp_link_pedido": whatsapp_link_pedido,
        "requiere_contacto_cliente": requiere_contacto_cliente,
        "requiere_cargar_seguimiento": requiere_cargar_seguimiento,
        "tiempo_transcurrido": tiempo_transcurrido,
        "fecha_referencia_estado": fecha_referencia_estado,
        "alertas_operativas": alertas_operativas,
        "semaforo_pedido": semaforo_pedido,
        "accion_principal_pedido": accion_principal_pedido,
        "ml_datos_apb_pedido": ml_datos_apb_pedido,
        "ml_link_detalle_venta": ml_link_detalle_venta,
        "ml_link_chat_venta": ml_link_chat_venta,
        "ml_pedido_tiene_mensajes_pendientes": ml_pedido_tiene_mensajes_pendientes,
        "ml_pedido_tiene_chat_iniciado": ml_pedido_tiene_chat_iniciado,
        "ml_pedido_tiene_claim": ml_pedido_tiene_claim,
        "fecha_argentina": fecha_argentina,
        "tracking_info_pedido": tracking_info_pedido,
        "generar_mensaje_contacto_ml": generar_mensaje_contacto_ml,
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if usuario_actual():
        return redirect(url_for("inicio"))

    error = ""

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        usuario = USUARIOS.get(username)

        if not usuario or usuario["password"] != password:
            error = "Usuario o contraseña incorrectos."
        else:
            session["username"] = username
            return redirect(url_for("inicio"))

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def inicio():
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
        pedido = (Pedido.query.filter_by(canal="Mercado Libre", ml_shipping_id=shipment_id).order_by(Pedido.id.asc()).first())
        if pedido:
            pedido.ml_shipping_status = str(shipment.get("status") or pedido.ml_shipping_status or "").strip()
            pedido.ml_logistic_type = str(shipment.get("logistic_type") or pedido.ml_logistic_type or "").strip()
            pedido.ml_shipping_mode = str(shipment.get("mode") or pedido.ml_shipping_mode or "").strip()
            pedido.ultima_sync_ml = datetime.utcnow()
            db.session.commit()
            print(f"[WEBHOOK ML] Shipment actualizado {shipment_id}. pedido_id={pedido.id}")
            return True
        print(f"[WEBHOOK ML] Shipment {shipment_id} sin pedido vinculado en Fierro")
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

@app.route("/webhook/mercadolibre", methods=["GET", "POST"])
@app.route("/admin/integraciones/mercadolibre/webhook", methods=["GET", "POST"])
def webhook_mercadolibre():
    """
    Webhook ML. No requiere login porque lo llama Mercado Libre.
    Para mensajes: marca el pedido con badge pendiente sin esperar la sync manual/cron.
    """
    if request.method == "GET":
        return "OK", 200

    try:
        data = request.get_json(silent=True) or {}
        print("[WEBHOOK ML]", data)

        topic = str(data.get("topic") or data.get("type") or "").lower()
        resource = str(data.get("resource") or "").strip()

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
                    print(f"[WEBHOOK ML] Mensaje pack={pack_id} -> pedido #{pedido.id} pendientes={count}")
                else:
                    print(f"[WEBHOOK ML] Mensaje pack={pack_id} sin pedido vinculado")
            else:
                ids = ml_extraer_ids_mensaje_ml(data)
                if not ids and resource:
                    ids = ml_resolver_ids_desde_recurso_mensaje(resource)

                marcados = ml_marcar_mensajes_pendientes_por_ids(ids, count=1, commit=True)

                # Fallback seguro: si el webhook no trae IDs claros, intentamos sync por pack en pedidos operativos.
                if marcados == 0:
                    total = ml_sync_mensajes_pendientes_pedidos()
                    db.session.commit()
                    print(f"[WEBHOOK ML] Mensaje sin match directo. Sync mensajes total={total}")
                else:
                    print(f"[WEBHOOK ML] Mensaje vinculado a {marcados} pedido(s). IDs={sorted(ids)}")

        elif "order" in topic or "/orders/" in resource:
            order_id = ""
            match = re.search(r"/orders/([^/?#]+)", resource)
            if match:
                order_id = match.group(1)
            ml_sync_pedido_por_order_id_webhook(order_id)

        elif "shipment" in topic or "/shipments/" in resource:
            shipment_id = ""
            match = re.search(r"/shipments/([^/?#]+)", resource)
            if match:
                shipment_id = match.group(1)
            ml_sync_shipment_por_id_webhook(shipment_id)

        elif "claim" in topic or "/claims/" in resource:
            ml_marcar_reclamo_webhook(resource)

        return "OK", 200

    except Exception as e:
        db.session.rollback()
        print("[WEBHOOK ML ERROR]", e)
        # ML espera 200 para no insistir infinitamente; logueamos pero no rompemos.
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


@app.route("/admin/integraciones")
@login_required
def admin_integraciones():
    if not puede_administrar_integraciones():
        return redirect(url_for("inicio"))

    cuenta_ml = cuenta_ml_actual()
    faltantes = ml_config_faltante()
    ok_feedback = (request.args.get("ok") or "").strip()
    error = (request.args.get("error") or "").strip()

    return render_template(
        "admin_integraciones.html",
        cuenta_ml=cuenta_ml,
        faltantes=faltantes,
        ok_feedback=ok_feedback,
        error=error,
    )


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
        resultado = ml_sync_manual(limit=50)
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
        return redirect(url_for("inicio"))

    actualizar_estado_automatico(pedido)
    db.session.commit()

    origen = (request.args.get("origen") or "").strip()

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
        return redirect(url_for("inicio"))

    actualizar_estado_automatico(pedido)

    if pedido.empresa_envio == "Vía Cargo" and not es_mercado_envios(pedido):
        aplicar_estado_y_fechas(pedido, "Etiqueta Impresa")
        db.session.commit()
        return render_template(
            "imprimir_etiqueta_interna.html",
            pedido=pedido,
            hay_autorizado=hay_autorizado,
            volver_url=(url_for("detalle_pedido", id=pedido.id) if origen == "detalle" else url_for("inicio"))
        )

    if es_mercado_envios(pedido):
        try:
            etiqueta_ok = ml_asegurar_etiqueta_disponible(pedido)
        except Exception as e:
            print("No se pudo asegurar etiqueta ML:", e)
            etiqueta_ok = False

        if not etiqueta_ok:
            db.session.commit()
            return render_template(
                "detalle_pedido.html",
                pedido=pedido,
                error="La etiqueta de Mercado Envíos todavía no está disponible. Resincronizá ML o probá de nuevo en unos minutos.",
                ok_feedback="",
                accion_sugerida=accion_sugerida_pedido(pedido),
                texto_boton=texto_boton_estado(pedido),
                hay_autorizado=hay_autorizado,
                puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,
                whatsapp_url=whatsapp_link_pedido(pedido)
            )

    if not pedido.etiqueta_archivo:
        return render_template(
            "detalle_pedido.html",
            pedido=pedido,
            error="No hay etiqueta adjunta para imprimir.",
            ok_feedback="",
            accion_sugerida=accion_sugerida_pedido(pedido),
            texto_boton=texto_boton_estado(pedido),
            hay_autorizado=hay_autorizado,
            puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,
            whatsapp_url=whatsapp_link_pedido(pedido)
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
            return render_template(
                "detalle_pedido.html",
                pedido=pedido,
                error="La etiqueta no está disponible en el servidor. Probá resincronizar ML.",
                ok_feedback="",
                accion_sugerida=accion_sugerida_pedido(pedido),
                texto_boton=texto_boton_estado(pedido),
                hay_autorizado=hay_autorizado,
                puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,
                whatsapp_url=whatsapp_link_pedido(pedido)
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
        etiqueta_existente = request.form.get("etiqueta_existente", "").strip()
        archivo_etiqueta = request.files.get("etiqueta")

        if archivo_etiqueta and archivo_etiqueta.filename:
            subida = guardar_etiqueta_subida(archivo_etiqueta)
            etiqueta_existente = subida.get("url", "")

        canal = request.form.get("canal")
        ml_tipo = request.form.get("ml_tipo")

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
            etiqueta_archivo=etiqueta_existente
        )

        db.session.add(pedido)
        db.session.flush()

        if es_guardado_parcial_acordas():
            db.session.commit()

            if accion_guardado_paso2() == "coordinar_whatsapp":
                whatsapp_url = whatsapp_link_pedido(pedido)
                if whatsapp_url:
                    return redirect(whatsapp_url)

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
                etiqueta_guardada=etiqueta_existente
            )

        db.session.commit()

        if canal == "Mercado Libre" and ml_tipo == "Acordás la Entrega" and not despacho_completo(pedido):
            return redirect(url_for("inicio"))

        return redirect(url_for("inicio"))

    return render_template("nuevo_pedido.html", error="", form_data={}, etiqueta_guardada="")


@app.route("/pedido/<int:id>")
@login_required
def detalle_pedido(id):
    pedido = Pedido.query.get_or_404(id)

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

    return render_template(
        "detalle_pedido.html",
        pedido=pedido,
        error=error,
        ok_feedback=ok_feedback,
        accion_sugerida=accion_sugerida_pedido(pedido),
        texto_boton=texto_boton_estado(pedido),
        hay_autorizado=hay_autorizado,
        puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,
        whatsapp_url=whatsapp_link_pedido(pedido)
    )


def marcar_contacto_iniciado_pedido(pedido):
    if not pedido:
        return
    pedido.contacto_iniciado = True
    if not pedido.fecha_contacto:
        pedido.fecha_contacto = datetime.utcnow()


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


@app.route("/pedido/<int:id>/eliminar", methods=["POST"])
@login_required
def eliminar_pedido(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_eliminar_pedido(pedido):
        return redirect(url_for("detalle_pedido", id=pedido.id, error="Solo Admin puede eliminar pedidos."))

    pedido_numero = pedido.id
    try:
        db.session.delete(pedido)
        db.session.commit()
        return redirect(url_for("inicio", ok=f"Pedido #{pedido_numero} eliminado correctamente."))
    except Exception as e:
        db.session.rollback()
        return redirect(url_for("detalle_pedido", id=id, error=f"No se pudo eliminar el pedido: {e}"))


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

    if not puede_ver_pedido(pedido) or rol_actual() not in ["admin", "carga"]:
        return redirect(url_for("detalle_pedido", id=pedido.id, error="No autorizado."))

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
        texto_api = generar_mensaje_contacto_ml_api(pedido)
        texto_visible = generar_mensaje_contacto_ml(pedido)
        ml_enviar_mensaje_acordas(pedido, texto_api)
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
                pedido.estado = "Con reclamo en transporte"

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

            db.session.commit()

            if volver == "detalle":
                return redirect(url_for("detalle_pedido", id=pedido.id))
            return redirect(url_for("inicio"))

        etiqueta_actual = request.form.get("etiqueta_existente", "").strip()
        archivo_etiqueta = request.files.get("etiqueta")

        if archivo_etiqueta and archivo_etiqueta.filename:
            subida = guardar_etiqueta_subida(archivo_etiqueta)
            etiqueta_actual = subida.get("url", "")

        canal = request.form.get("canal")
        ml_tipo = request.form.get("ml_tipo")

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
        pedido.etiqueta_archivo = etiqueta_actual

        if es_guardado_parcial_acordas():
            db.session.commit()

            if accion_guardado_paso2() == "coordinar_whatsapp":
                whatsapp_url = whatsapp_link_pedido(pedido)
                if whatsapp_url:
                    return redirect(whatsapp_url)

            return redirect(url_for("inicio"))

        cargar_items_desde_texto(pedido, request.form.get("items_texto", ""))
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

@app.route("/pedido/<int:id>/confirmar-entrega")
@login_required
def confirmar_entrega(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_ver_pedido(pedido):
        return redirect(url_for("inicio"))

    if not requiere_seguimiento_retiro(pedido):
        return redirect(url_for("inicio"))

    pedido.estado = "Listo para retirar"
    db.session.commit()

    whatsapp_url = whatsapp_link_confirmar_entrega(pedido)
    if whatsapp_url:
        return redirect(whatsapp_url)

    return redirect(url_for("detalle_pedido", id=pedido.id, ok=texto_feedback_estado("Listo para retirar")))

@app.route("/pedido/<int:id>/cerrar-ml")
@login_required
def cerrar_ml(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_ver_pedido(pedido):
        return redirect(url_for("inicio"))

    if not (
        pedido.estado == "Entregado"
        and pedido.canal == "Mercado Libre"
        and pedido.ml_tipo == "Acordás la Entrega"
    ):
        return redirect(url_for("inicio"))

    pedido.estado = "Finalizado"
    db.session.commit()

    return redirect(url_for("detalle_pedido", id=pedido.id, ok=texto_feedback_estado("Finalizado")))

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

@app.route("/pedido/<int:id>/avanzar")
@login_required
def avanzar_pedido(id):
    pedido = Pedido.query.get_or_404(id)

    if not puede_ver_pedido(pedido):
        return redirect(url_for("inicio"))

    puede_avanzar, errores = puede_avanzar_pedido(pedido)

    if not puede_avanzar:
        return render_template(
            "detalle_pedido.html",
            pedido=pedido,
            error="<br>".join(errores),
            ok_feedback="",
            accion_sugerida=accion_sugerida_pedido(pedido),
            texto_boton=texto_boton_estado(pedido),
            hay_autorizado=hay_autorizado,
            puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,
            whatsapp_url=whatsapp_link_pedido(pedido)
        )

    nuevo = siguiente_estado(pedido.estado)

    if nuevo in ["Embalado", "Despachado"] and pedido.canal == "Mercado Libre":
        orden_ok, mensaje_ml = ml_validar_orden_operable_antes_de_despacho(pedido)
        if not orden_ok:
            return redirect(url_for("detalle_pedido", id=pedido.id, error=mensaje_ml))

    if nuevo:
        aplicar_estado_y_fechas(pedido, nuevo)
        db.session.commit()

    mensaje_ok = texto_feedback_estado(pedido.estado)

    if rol_actual() == "despacho":
        if pedido.estado == "Embalado":
            return redirect(url_for("detalle_pedido", id=pedido.id, ok=mensaje_ok))
        return redirect(url_for("inicio", ok=mensaje_ok))

    if rol_actual() == "carga":
        return redirect(url_for("detalle_pedido", id=pedido.id, ok=mensaje_ok))

    return redirect(url_for("inicio", ok=mensaje_ok))


with app.app_context():
    db.create_all()
    
    asegurar_columnas_extra()
    asegurar_columnas_integracion_ml()
