"""
modules/whatsapp/config.py
──────────────────────────
Variables de configuración del módulo WhatsApp.
Se leen del .env del servidor.

Para activar el módulo agregar al .env:
    WHATSAPP_TOKEN=<token permanente de tu app Meta>
    WHATSAPP_PHONE_NUMBER_ID=<ID del número en Meta>
    WHATSAPP_VERIFY_TOKEN=<string secreto que vos elegís>

Mientras estas variables no estén en el .env el módulo
no hace absolutamente nada.
"""

import os

# ── Credenciales Meta ──────────────────────────────────────────────
WA_TOKEN            = os.getenv("WHATSAPP_TOKEN", "")
WA_PHONE_NUMBER_ID  = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WA_VERIFY_TOKEN     = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
WA_API_URL          = f"https://graph.facebook.com/v19.0/{WA_PHONE_NUMBER_ID}/messages"

# ── Alias de pago ──────────────────────────────────────────────────
ALIAS_PAGO = "fierroargentogalicia"

# ── Timers (en segundos) ───────────────────────────────────────────
TIMER_PRIMER_RECORDATORIO   = 60 * 60       # 1 hora
TIMER_SEGUNDO_RECORDATORIO  = 60 * 60 * 3   # 3 horas
TIMER_CROSS_SELL_SIGUIENTE  = 60 * 5        # 5 minutos

# ── Catálogo de cross-sell ─────────────────────────────────────────
# imagen_url: dejar vacío hasta tener las fotos listas.
# Cuando actives el módulo te indicamos cómo cargar las imágenes.
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
        "imagen_url": "",   # ← completar cuando tengas la foto
    },
    "KPADES": {
        "nombre":     "Kit pala y atizador (plegable)",
        "descripcion": (
            "Además también tenemos este kit de pala y atizador desarmables, "
            "pensado para la parrilla plegable ya que entra desarmado dentro de la parrilla plegada "
            "al guardar y se arma fácilmente enroscando los mangos 🔧"
        ),
        "precio":     8500,
        "imagen_url": "",   # ← completar cuando tengas la foto
    },
    "KITPACH": {
        "nombre":     "Kit pala y atizador",
        "descripcion": (
            "Te cuento que podés agregar a tu compra este kit infaltable de pala y atizador "
            "construidos en hierro, muy prácticos y reforzados, para un buen manejo de las brasas 🔥"
        ),
        "precio":     7500,
        "imagen_url": "",   # ← completar cuando tengas la foto
    },
    "B4030H": {
        "nombre":     "Brasero 30x40cm",
        "descripcion": (
            "También tenemos braseros, construidos en hierro de 10mm super robustos. "
            "Este es de 30 x 40 cm, ideal para acompañar tu parrilla 🔥"
        ),
        "precio":     28700,
        "imagen_url": "",   # ← completar cuando tengas la foto
    },
    "B5030H": {
        "nombre":     "Brasero 30x53cm",
        "descripcion": (
            "También tenemos braseros, construidos en hierro de 10mm super robustos. "
            "Este es de 30 x 53 cm, el más grande de nuestra línea 🔥"
        ),
        "precio":     33700,
        "imagen_url": "",   # ← completar cuando tengas la foto
    },
}

# ── Mapa de cross-sell por SKU ─────────────────────────────────────
# Define qué productos se ofrecen y en qué orden para cada SKU comprado.
CROSS_SELL_POR_SKU = {
    "PP6040H":       ["BPPC01", "KPADES"],
    "PP6040H+FUNDA": ["KPADES"],
    # Parrillas PA y PF — todas las medidas
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
