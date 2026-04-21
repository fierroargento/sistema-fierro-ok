import os
import re
import pandas as pd
import fitz
import cloudinary
import cloudinary.uploader
from datetime import datetime
from functools import wraps

from flask import Flask, request, redirect, render_template, url_for, jsonify, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, inspect
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
        resultado = cloudinary.uploader.upload(archivo, resource_type="raw")
        return resultado["secure_url"]
    except Exception as e:
        print("Error subiendo a Cloudinary:", e)
        return ""




def generar_preview_etiqueta_pdf(nombre_archivo):
    ruta_pdf = os.path.join(app.config["UPLOAD_FOLDER"], nombre_archivo)

    if not os.path.exists(ruta_pdf):
        return None

    base_nombre = os.path.splitext(nombre_archivo)[0]
    nombre_preview = f"{base_nombre}__preview_recortado.png"
    ruta_preview = os.path.join(app.config["UPLOAD_FOLDER"], nombre_preview)

    if os.path.exists(ruta_preview):
        try:
            if os.path.getmtime(ruta_preview) >= os.path.getmtime(ruta_pdf):
                return nombre_preview
        except OSError:
            pass

    try:
        doc = fitz.open(ruta_pdf)
    except Exception:
        return None

    try:
        page = doc[0]
        zoom = 3
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        width = pix.width
        height = pix.height
        channels = pix.n
        data = pix.samples

        umbral_blanco = 245
        min_x, min_y = width, height
        max_x, max_y = -1, -1

        for y in range(height):
            row_offset = y * width * channels
            for x in range(width):
                i = row_offset + x * channels
                r = data[i]
                g = data[i + 1]
                b = data[i + 2]

                if r < umbral_blanco or g < umbral_blanco or b < umbral_blanco:
                    if x < min_x:
                        min_x = x
                    if y < min_y:
                        min_y = y
                    if x > max_x:
                        max_x = x
                    if y > max_y:
                        max_y = y

        if max_x == -1 or max_y == -1:
            clip_rect = page.rect
        else:
            margen_px = 12
            min_x = max(0, min_x - margen_px)
            min_y = max(0, min_y - margen_px)
            max_x = min(width - 1, max_x + margen_px)
            max_y = min(height - 1, max_y + margen_px)

            clip_rect = fitz.Rect(
                min_x / zoom,
                min_y / zoom,
                (max_x + 1) / zoom,
                (max_y + 1) / zoom,
            )

        pix_recortado = page.get_pixmap(matrix=matrix, clip=clip_rect, alpha=False)
        pix_recortado.save(ruta_preview)

        return nombre_preview
    except Exception:
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
        and pedido.seguimiento
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
            pass

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


def accion_sugerida_pedido(pedido):
    if pedido.estado == "Cargando Pedido":
        if not pedido.cliente:
            return "Falta cargar cliente"

        if not pedido.canal:
            return "Falta elegir canal"

        if pedido.canal == "Mercado Libre" and not pedido.ml_tipo:
            return "Falta elegir tipo ML"

        if pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Mercado Envíos" and not pedido.seguimiento:
            return "Falta cargar seguimiento"

        if pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Mercado Envíos" and not pedido.etiqueta_archivo:
            return "Falta adjuntar etiqueta"

        if pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Acordás la Entrega" and not pedido.empresa_envio:
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

def accion_principal_pedido(pedido, origen="inicio"):
    rol = rol_actual()
    es_inicio = origen == "inicio"

    clase_base = "btn btn-accion-rapida"
    clase_confirmar = "btn btn-accion-rapida btn-confirmar"

    if requiere_contacto_cliente(pedido):
        return {
            "tipo": "completar_carga",
            "texto": "Completar carga",
            "url": url_for("editar_pedido", id=pedido.id),
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
        return pedido.estado in ["Etiqueta Lista", "Etiqueta Impresa", "Embalado", "Despachado"]

    return False





def puede_editar_pedido(pedido):
    rol = rol_actual()

    if rol == "admin":
        return True

    if rol == "carga":
        return pedido.estado in ["Cargando Pedido", "Despachado", "Con demora de entrega", "Con reclamo en transporte", "Verificar llegada a destino", "Listo para retirar", "No entregado", "Reclamar a Mercado Libre", "Entregado"]

    return False


def puede_crear_pedido():
    return rol_actual() in ["admin", "carga"]


def puede_ver_historico():
    return rol_actual() in ["admin", "carga"]


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


@app.context_processor
def inyectar_contexto_global():
    return {
        "usuario_logueado": usuario_actual(),
        "rol_actual": rol_actual(),
        "titulo_inicio_por_rol": titulo_inicio_por_rol,
        "subtitulo_inicio_por_rol": subtitulo_inicio_por_rol,
        "puede_crear_pedido": puede_crear_pedido,
        "puede_ver_historico": puede_ver_historico,
        "puede_editar_pedido": puede_editar_pedido,
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

    return render_template(
        "index.html",
        pedidos=pedidos,
        resumen_operativo=resumen_operativo(pedidos),
        accion_sugerida_pedido=accion_sugerida_pedido,
        texto_boton_estado=texto_boton_estado,
        puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente
    )



@app.route("/ayuda")
@login_required
def ayuda():
    return render_template("ayuda.html")


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
    ruta_archivo = os.path.join(app.config["UPLOAD_FOLDER"], nombre_archivo)

    if not os.path.exists(ruta_archivo):
        return "El adjunto solicitado ya no está disponible en el servidor.", 404

    return send_from_directory(app.config["UPLOAD_FOLDER"], nombre_archivo)


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

    if pedido.estado in ["Cargando Pedido", "Etiqueta Lista"] and (
        pedido.estado == "Etiqueta Lista"
        or puede_imprimir_etiqueta_directamente(pedido)
        or puede_imprimir_acordas_entrega(pedido)
    ):
        aplicar_estado_y_fechas(pedido, "Etiqueta Impresa")
        db.session.commit()

    if pedido.empresa_envio == "Vía Cargo" and not es_mercado_envios(pedido):
        return render_template(
            "imprimir_etiqueta_interna.html",
            pedido=pedido,
            hay_autorizado=hay_autorizado,
            volver_url=(url_for("detalle_pedido", id=pedido.id) if origen == "detalle" else url_for("inicio"))
        )

    if not pedido.etiqueta_archivo:
        return render_template(
            "detalle_pedido.html",
            pedido=pedido,
            error="No hay etiqueta adjunta para imprimir.",
            accion_sugerida=accion_sugerida_pedido(pedido),
            texto_boton=texto_boton_estado(pedido),
            hay_autorizado=hay_autorizado,
            puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,
            whatsapp_url=whatsapp_link_pedido(pedido)
        )

    extension = pedido.etiqueta_archivo.rsplit(".", 1)[-1].lower() if "." in pedido.etiqueta_archivo else ""
    ruta_etiqueta = os.path.join(app.config["UPLOAD_FOLDER"], pedido.etiqueta_archivo)

    if not os.path.exists(ruta_etiqueta):
        return render_template(
            "detalle_pedido.html",
            pedido=pedido,
            error="La etiqueta adjunta ya no está disponible en el servidor.",
            accion_sugerida=accion_sugerida_pedido(pedido),
            texto_boton=texto_boton_estado(pedido),
            hay_autorizado=hay_autorizado,
            puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,
            whatsapp_url=whatsapp_link_pedido(pedido)
        )

    url_original = url_for("ver_etiqueta", nombre_archivo=pedido.etiqueta_archivo)

    if extension == "pdf":
        nombre_preview = generar_preview_etiqueta_pdf(pedido.etiqueta_archivo)
        if not nombre_preview:
            return render_template(
                "detalle_pedido.html",
                pedido=pedido,
                error="No se pudo generar la vista previa de la etiqueta.",
                accion_sugerida=accion_sugerida_pedido(pedido),
                texto_boton=texto_boton_estado(pedido),
                hay_autorizado=hay_autorizado,
                puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,
                whatsapp_url=whatsapp_link_pedido(pedido)
            )
        url_archivo = url_for("ver_etiqueta", nombre_archivo=nombre_preview)
    else:
        url_archivo = url_original

    return render_template(
        "imprimir_etiqueta.html",
        pedido=pedido,
        url_archivo=url_archivo,
        url_original=url_original,
        extension=extension
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
            etiqueta_existente = guardar_etiqueta_subida(archivo_etiqueta)

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

    return render_template(
        "detalle_pedido.html",
        pedido=pedido,
        error="",
        accion_sugerida=accion_sugerida_pedido(pedido),
        texto_boton=texto_boton_estado(pedido),
        hay_autorizado=hay_autorizado,
        puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,
        whatsapp_url=whatsapp_link_pedido(pedido)
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
            etiqueta_actual = guardar_etiqueta_subida(archivo_etiqueta)

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

    return redirect(url_for("inicio"))


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

    return redirect(url_for("inicio"))


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

    return redirect(url_for("detalle_pedido", id=pedido.id))

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

    return redirect(url_for("detalle_pedido", id=pedido.id))


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
            accion_sugerida=accion_sugerida_pedido(pedido),
            texto_boton=texto_boton_estado(pedido),
            hay_autorizado=hay_autorizado,
            puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,
            whatsapp_url=whatsapp_link_pedido(pedido)
        )

    nuevo = siguiente_estado(pedido.estado)

    if nuevo:
        aplicar_estado_y_fechas(pedido, nuevo)
        db.session.commit()

    return redirect(url_for("inicio"))


with app.app_context():
    db.create_all()
    asegurar_columnas_extra()

    ruta_excel = os.path.join(app.root_path, "productos.xlsx")
    if Producto.query.count() == 0 and os.path.exists(ruta_excel):
        try:
            sincronizar_productos_desde_excel(ruta_excel)
        except Exception as e:
            print("No se pudo cargar productos iniciales desde Excel:", e)

if __name__ == "__main__":
    app.run(debug=True)
