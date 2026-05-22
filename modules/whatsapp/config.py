"""
modules/whatsapp/config.py
──────────────────────────
Configuración del módulo WhatsApp + flujo Correo Argentino.

Modo APB:
- Si faltan credenciales, el módulo queda inactivo y no rompe el sistema.
- Los valores operativos tienen default seguro.
- Más adelante estos defaults pueden pasar a ConfiguracionSistema desde panel admin.
"""

import os

# ── Credenciales Meta ──────────────────────────────────────────────
WA_TOKEN            = os.getenv("WHATSAPP_TOKEN", "")
WA_PHONE_NUMBER_ID  = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WA_VERIFY_TOKEN     = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
WA_API_URL          = f"https://graph.facebook.com/v19.0/{WA_PHONE_NUMBER_ID}/messages"

# ── Alias de pago ──────────────────────────────────────────────────
ALIAS_PAGO = "fierroargentogalicia"

# ── Timers WhatsApp ────────────────────────────────────────────────
TIMER_PRIMER_RECORDATORIO   = int(os.getenv("WA_TIMER_PRIMER_RECORDATORIO", 60 * 60))       # 1 hora
TIMER_SEGUNDO_RECORDATORIO  = int(os.getenv("WA_TIMER_SEGUNDO_RECORDATORIO", 60 * 60 * 3))   # 3 horas
TIMER_CROSS_SELL_SIGUIENTE  = int(os.getenv("WA_TIMER_CROSS_SELL", 60 * 5))                  # 5 minutos

# Scheduler central APB. Corre enganchado a requests para no abrir hilos raros en Render.
SCHEDULER_INTERVALO_SEGUNDOS = int(os.getenv("WA_SCHEDULER_INTERVALO_SEGUNDOS", 60 * 5))
TRACKING_INTERVALO_MINUTOS   = int(os.getenv("TRACKING_INTERVALO_MINUTOS", 60))

# ── Reglas Correo PP6040 ───────────────────────────────────────────
# El cliente NO ve costos. Esto es solo decisión interna.
MAX_COSTO_ENVIO_DEFAULT = float(os.getenv("MAX_COSTO_ENVIO_DEFAULT", "0") or 0)  # 0 = sin tope hasta cargarlo en admin/DB
MAX_PORCENTAJE_DOMICILIO_DEFAULT = float(os.getenv("MAX_PORCENTAJE_DOMICILIO_DEFAULT", "20") or 20)

# Pack AR clásico: a efectos operativos, sucursal / punto Correo.
CORREO_SERVICIO_PP6040 = "Pack AR Clásico"

# ── Estados WA normalizados ────────────────────────────────────────
WA_ESPERANDO_DATOS = "esperando_datos"
WA_ESPERANDO_OK_INICIO = "esperando_ok_inicio"
WA_ESPERANDO_CONFIRMACION_SUCURSAL = "esperando_confirmacion_sucursal"

WA_FALTA_ELEGIR_TRANSPORTE = "falta_elegir_transporte"
WA_REQUIERE_OPERADOR = "requiere_operador"
WA_CONFIRMADO_CLIENTE = "confirmado_cliente"

WA_DESPACHO_EN_PROCESO = "despacho_en_proceso"
WA_DESPACHADO = "despachado"
WA_LISTO_PARA_RETIRAR = "listo_para_retirar"
WA_POSTVENTA = "postventa"

WA_CROSS_SELL = "cross_sell"
WA_CROSS_SELL_CERRADO = "cross_sell_cerrado"

WA_FINALIZADO = "finalizado"
# ── Templates Meta WhatsApp ─────────────────────────────────────────
WA_TEMPLATE_LANG = "es_AR"

WA_TEMPLATE_INICIO_DESPACHO = "inicio_despacho_datos"
WA_TEMPLATE_INICIO_CHAT_OPERADOR = "inicio_chat_operador"
WA_TEMPLATE_PEDIDO_DATO = "pedido_dato_faltante"
WA_TEMPLATE_SEGUIMIENTO = "seguimiento_despacho"
WA_TEMPLATE_RETIRO = "listo_para_retirar"
WA_TEMPLATE_POSTVENTA_PARRILLA = "postventa_parrilla"

# ── Catálogo de cross-sell ─────────────────────────────────────────
CATALOGO = {
    "BPPC01": {
        "nombre":     "Funda para parrilla plegable",
        "descripcion": (
            "Aprovecho y te comento que tenemos la funda para esa parrilla, "
            "algo que es conveniente agregar a tu compra. No solo para proteger tu parrilla, "
            "además protege el entorno si la guardás sin tiempo para limpiarla bien después de usarla. "
            "Es de tela Cordura, hecha a medida y reforzada para que dure un montón! 💪"
        ),
        "precio":     8500,
        "imagen_url": "",
    },
    "KPADES": {
        "nombre":     "Kit pala y atizador (plegable)",
        "descripcion": (
            "Además también tenemos este kit de pala y atizador desarmables, "
            "pensado para la parrilla plegable ya que entra desarmado dentro de la parrilla plegada "
            "al guardar y se arma fácilmente enroscando los mangos 🔧"
        ),
        "precio":     8500,
        "imagen_url": "",
    },
    "KITPACH": {
        "nombre":     "Kit pala y atizador",
        "descripcion": (
            "Te cuento que podés agregar a tu compra este kit infaltable de pala y atizador "
            "construidos en hierro, muy prácticos y reforzados, para un buen manejo de las brasas 🔥"
        ),
        "precio":     7500,
        "imagen_url": "",
    },
    "B4030H": {
        "nombre":     "Brasero 30x40cm",
        "descripcion": (
            "También tenemos braseros, construidos en hierro de 10mm super robustos. "
            "Este es de 30 x 40 cm, ideal para acompañar tu parrilla 🔥"
        ),
        "precio":     28700,
        "imagen_url": "",
    },
    "B5030H": {
        "nombre":     "Brasero 30x53cm",
        "descripcion": (
            "También tenemos braseros, construidos en hierro de 10mm super robustos. "
            "Este es de 30 x 53 cm, el más grande de nuestra línea 🔥"
        ),
        "precio":     33700,
        "imagen_url": "",
    },
}

CROSS_SELL_POR_SKU = {
    "PP6040H":       ["BPPC01", "KPADES"],
    "PP6040H+FUNDA": ["KPADES"],
    "PA10060H": ["KITPACH", "B4030H", "B5030H"],
    "PA12060H": ["KITPACH", "B4030H", "B5030H"],
    "PA6040H":  ["KITPACH", "B4030H", "B5030H"],
    "PA7050H":  ["KITPACH", "B4030H", "B5030H"],
    "PA8050H":  ["KITPACH", "B4030H", "B5030H"],
    "PA9060H":  ["KITPACH", "B4030H", "B5030H"],
    "PF10060H": ["KITPACH", "B4030H", "B5030H"],
    "PF12060H": ["KITPACH", "B4030H", "B5030H"],
    "PF6040H":  ["KITPACH", "B4030H", "B5030H"],
    "PF7050H":  ["KITPACH", "B4030H", "B5030H"],
    "PF8050H":  ["KITPACH", "B4030H", "B5030H"],
    "PF9060H":  ["KITPACH", "B4030H", "B5030H"],
}


def modulo_activo():
    """Devuelve True solo si las credenciales están configuradas en el .env."""
    return bool(WA_TOKEN and WA_PHONE_NUMBER_ID and WA_VERIFY_TOKEN)
