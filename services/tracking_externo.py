import re
import html
import unicodedata
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _normalizar(txt):
    txt = str(txt or "")
    txt = unicodedata.normalize("NFD", txt)
    txt = "".join(ch for ch in txt if unicodedata.category(ch) != "Mn")
    return txt.lower().strip()


def _limpiar_texto_html(raw):
    texto = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw or "")
    texto = re.sub(r"(?is)<style.*?>.*?</style>", " ", texto)
    texto = re.sub(r"(?is)<noscript.*?>.*?</noscript>", " ", texto)
    texto = re.sub(r"(?s)<[^>]+>", " ", texto)
    texto = html.unescape(texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


ESTADOS_VIA_CARGO = [
    "ENTREGADA",
    "RECIBIDO EN DESTINO",
    "EN VIAJE",
    "LLEGADA A CENTRO DE DISTRIBUCION",
    "LLEGADA A CENTRO DE DISTRIBUCIÓN",
    "INGRESO A VIA CARGO",
]

ESTADOS_CORREO = [
    "ENTREGADO",
    "ENTREGA EN SUCURSAL",
    "EN ESPERA EN SUCURSAL",
    "INTENTO DE ENTREGA",
    "EN PROCESO DE CLASIFICACION",
    "EN PROCESO DE CLASIFICACIÓN",
    "LLEGADA AL CENTRO DE PROCESAMIENTO",
    "INGRESO AL CORREO",
    "PREIMPOSICION",
    "PREIMPOSICIÓN",
    "REPESAJE",
]

ESTADOS_ANDREANI = [
    "ENTREGADO",
    "ENTREGADA",
    "ENTREGA EN SUCURSAL",
    "EN ESPERA EN SUCURSAL",
    "DISPONIBLE PARA RETIRAR",
    "LISTO PARA RETIRAR",
    "EN SUCURSAL",
    "INTENTO DE ENTREGA",
    "VISITA SIN ENTREGAR",
    "NO ENTREGADO",
    "EN DISTRIBUCION",
    "EN DISTRIBUCIÓN",
    "EN TRANSITO",
    "EN TRÁNSITO",
    "EN VIAJE",
    "INGRESO",
    "ADMITIDO",
    "PROCESAMIENTO",
]


def _lista_estados_por_transporte(transporte):
    t = _normalizar(transporte)
    if "via cargo" in t or "via" in t and "cargo" in t:
        return ESTADOS_VIA_CARGO
    if "correo" in t or "mercado env" in t:
        return ESTADOS_CORREO
    if "andreani" in t:
        return ESTADOS_ANDREANI
    return ESTADOS_ANDREANI + ESTADOS_VIA_CARGO + ESTADOS_CORREO


def _extraer_estado_por_patrones(texto, transporte=""):
    """Devuelve el estado logístico más reciente encontrado.

    Las páginas de tracking muestran el evento más nuevo arriba. Por eso se toma
    la primera aparición real en el texto limpio, no una búsqueda genérica por
    palabras sueltas.
    """
    if not texto:
        return ""

    normal = _normalizar(texto)
    candidatos = []

    for estado in _lista_estados_por_transporte(transporte):
        estado_norm = _normalizar(estado)
        pos = normal.find(estado_norm)
        if pos >= 0:
            candidatos.append((pos, estado.upper()))

    if candidatos:
        candidatos.sort(key=lambda x: x[0])
        return candidatos[0][1]

    # Fallback controlado para páginas que cambian el texto exacto.
    patrones = [
        r"(entregad[oa](?:\s+al\s+destinatario)?)",
        r"(entrega\s+en\s+sucursal)",
        r"(en\s+espera\s+en\s+sucursal)",
        r"(recibido\s+en\s+destino)",
        r"(disponible\s+para\s+retirar[^.]{0,80})",
        r"(listo\s+para\s+retirar[^.]{0,80})",
        r"(en\s+sucursal[^.]{0,80})",
        r"(intento\s+de\s+entrega[^.]{0,80})",
        r"(no\s+entregad[oa][^.]{0,80})",
        r"(en\s+distribuci[oó]n[^.]{0,80})",
        r"(en\s+tr[aá]nsito[^.]{0,80})",
        r"(en\s+viaje[^.]{0,80})",
        r"(en\s+proceso\s+de\s+clasificaci[oó]n)",
        r"(llegada\s+al\s+centro\s+de\s+procesamiento)",
        r"(llegada\s+a\s+centro\s+de\s+distribuci[oó]n)",
        r"(ingreso\s+al\s+correo)",
        r"(ingreso\s+a\s+via\s+cargo)",
        r"(preimposici[oó]n)",
    ]

    for patron in patrones:
        m = re.search(patron, texto, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip(" -:;,.").upper()

    return ""


def interpretar_estado_logistico(texto, transporte=""):
    """Mapea estados externos a clases seguras del Sistema Fierro.

    Retornos posibles:
    - entregado: se puede pasar a Entregado.
    - sucursal: se puede pasar a Verificar llegada a destino.
    - incidencia: requiere revisión; no autoavanza para no romper flujo.
    - transito: guardar info, no cambiar estado interno.
    - desconocido: guardar error, no cambiar estado interno.
    """
    t = _normalizar(texto)

    if not t:
        return "desconocido"

    if any(x in t for x in ["no entreg", "fallid", "rechaz", "devol", "incid", "siniestr", "imposible entregar"]):
        return "incidencia"

    # Correo puede mostrar INTENTO DE ENTREGA como historia y ENTREGA EN SUCURSAL como estado.
    # Si el último estado detectado es intento, se deja como incidencia para revisión manual.
    if "intento de entrega" in t or "visita sin entregar" in t:
        return "incidencia"

    if "entregad" in t and "no entreg" not in t:
        return "entregado"

    if any(x in t for x in [
        "recibido en destino",
        "entrega en sucursal",
        "en espera en sucursal",
        "sucursal",
        "retirar",
        "retiro",
        "disponible",
        "destino",
    ]):
        return "sucursal"

    if any(x in t for x in [
        "transito", "distribucion", "viaje", "clasificacion", "procesamiento",
        "ingreso", "preimposicion", "repesaje", "admitido",
    ]):
        return "transito"

    return "desconocido"


def _leer_url(url):
    req = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept-Language": "es-AR,es;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    with urlopen(req, timeout=15) as resp:
        raw = resp.read(800000).decode("utf-8", errors="ignore")
    return raw


def consultar_tracking_url(url, transporte="", seguimiento=""):
    """Consulta una URL pública de tracking y devuelve el estado detectado.

    Modo APB:
    - si lee un estado claro, lo devuelve;
    - si la web cambia, bloquea o requiere formulario, devuelve error;
    - nunca lanza excepción hacia el sistema principal.
    """
    if not url:
        return {"estado": "", "error": "No hay URL de tracking"}

    try:
        raw = _leer_url(url)
    except HTTPError as e:
        return {"estado": "", "error": f"HTTP {e.code}"}
    except URLError as e:
        return {"estado": "", "error": f"Error de conexión: {e.reason}"}
    except Exception as e:
        return {"estado": "", "error": str(e)}

    texto = _limpiar_texto_html(raw)
    estado = _extraer_estado_por_patrones(texto, transporte=transporte)
    if not estado:
        return {
            "estado": "Sin estado detectado",
            "error": "No se detectó un estado logístico claro en la página",
            "texto_muestra": texto[:1200],
        }

    clasificacion = interpretar_estado_logistico(estado, transporte=transporte)
    if clasificacion == "desconocido":
        return {
            "estado": estado,
            "error": "Estado detectado, pero sin mapeo seguro",
            "texto_muestra": texto[:1200],
        }

    return {
        "estado": estado,
        "error": None,
        "texto_muestra": texto[:1200],
    }


def consultar_correo_formulario(seguimiento, mercado_envios=False):
    """Consulta real segura de Correo Argentino.

    Usa el endpoint interno que utiliza la web de Correo:
    - action=mercadolibre para Mercado Envíos
    - action=ecommerce para Acordás / e-commerce

    Modo APB:
    - si lee un estado claro, lo devuelve;
    - si falla o la respuesta cambia, devuelve error controlado;
    - nunca lanza excepción hacia el sistema principal.
    """
    seguimiento = str(seguimiento or "").strip()
    if not seguimiento:
        return {"estado": "", "error": "No hay seguimiento"}

    url = "https://www.correoargentino.com.ar/sites/all/modules/custom/ca_forms/api/wsFacade.php"
    action = "mercadolibre" if mercado_envios else "ecommerce"

    data = urlencode({"action": action, "id": seguimiento}).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html, */*; q=0.01",
            "Accept-Language": "es-AR,es;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://www.correoargentino.com.ar",
            "Referer": "https://www.correoargentino.com.ar/formularios/mercadolibre" if mercado_envios else "https://www.correoargentino.com.ar/formularios/e-commerce",
            "X-Requested-With": "XMLHttpRequest",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=15) as resp:
            raw = resp.read(800000).decode("utf-8", errors="ignore")
    except HTTPError as e:
        return {"estado": "", "error": f"HTTP {e.code}"}
    except URLError as e:
        return {"estado": "", "error": f"Error de conexión: {e.reason}"}
    except Exception as e:
        return {"estado": "", "error": str(e)}

    texto = _limpiar_texto_html(raw)
    estado = _extraer_estado_por_patrones(texto, transporte="Correo Argentino")

    if not estado:
        return {
            "estado": "Sin estado detectado",
            "error": "No se detectó un estado logístico claro en Correo",
            "texto_muestra": texto[:1200],
        }

    clasificacion = interpretar_estado_logistico(estado, transporte="Correo Argentino")
    if clasificacion == "desconocido":
        return {
            "estado": estado,
            "error": "Estado detectado, pero sin mapeo seguro",
            "texto_muestra": texto[:1200],
        }

    return {
        "estado": estado,
        "error": None,
        "texto_muestra": texto[:1200],
    }
