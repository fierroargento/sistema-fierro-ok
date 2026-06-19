import re
import html
import json
import unicodedata
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)


def _headers_navegador(referer="", accept_json=False):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
        "Accept": "application/json,text/plain,*/*" if accept_json else "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,text/plain,*/*;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "close",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
    }
    if not accept_json:
        headers["Upgrade-Insecure-Requests"] = "1"
    if referer:
        headers["Referer"] = referer
    return headers


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
    "ENTREGADO",
    "ENTREGADA",
    "ENTREGADO AL DESTINATARIO",
    "RECIBIDO EN DESTINO",
    "RECIBIDO EN SUCURSAL DESTINO",
    "DISPONIBLE PARA RETIRAR",
    "LISTO PARA RETIRAR",
    "EN SUCURSAL",
    "EN VIAJE",
    "EN TRANSITO",
    "EN TRÁNSITO",
    "LLEGADA A CENTRO DE DISTRIBUCION",
    "LLEGADA A CENTRO DE DISTRIBUCIÓN",
    "INGRESO A VIA CARGO",
    "INGRESO A VIA CARGO EN ORIGEN",
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
    "EN CAMINO",
    "INGRESADO",
    "INGRESO",
    "ADMITIDO",
    "PROCESAMIENTO",
]


def _lista_estados_por_transporte(transporte):
    t = _normalizar(transporte)
    if "via cargo" in t or ("via" in t and "cargo" in t):
        return ESTADOS_VIA_CARGO
    if "correo" in t or "mercado env" in t:
        return ESTADOS_CORREO
    if "andreani" in t:
        return ESTADOS_ANDREANI
    return ESTADOS_ANDREANI + ESTADOS_VIA_CARGO + ESTADOS_CORREO




# Estados reales vistos en navegador. Se evalúan antes que la lista general
# para evitar que textos secundarios del sitio ganen por posición.
ESTADOS_PRIORITARIOS_REALES = [
    ("andreani", "en camino", "EN CAMINO"),
    ("andreani", "tu envio se encuentra en camino", "EN CAMINO"),
    ("andreani", "tu envío se encuentra en camino", "EN CAMINO"),
    ("andreani", "ingresado", "INGRESADO"),
    ("andreani", "visitas pendientes", "EN CAMINO"),
    ("via cargo", "ingreso a via cargo", "INGRESO A VIA CARGO"),
    ("via cargo", "via cargo estandar", "INGRESO A VIA CARGO"),
    ("via cargo", "recibido en destino", "RECIBIDO EN DESTINO"),
    ("via cargo", "en viaje", "EN VIAJE"),
    ("via cargo", "entregada", "ENTREGADA"),
    ("via cargo", "entregado", "ENTREGADO"),
]


def _extraer_estado_prioritario(texto, transporte=""):
    """Detecta estados reales observados en Andreani/Vía Cargo antes del parser general."""
    normal = _normalizar(texto)
    trans = _normalizar(transporte)

    for scope, needle, estado in ESTADOS_PRIORITARIOS_REALES:
        if scope in trans and needle in normal:
            return estado

    if "ingreso a via cargo" in normal:
        return "INGRESO A VIA CARGO"
    if "tu envio se encuentra en camino" in normal or "tu envío se encuentra en camino" in normal:
        return "EN CAMINO"
    if re.search(r"\ben camino\b", normal):
        return "EN CAMINO"

    return ""

def _extraer_estado_por_patrones(texto, transporte=""):
    """Devuelve el estado logístico más reciente encontrado.

    Las páginas de tracking suelen mostrar el evento más nuevo arriba. Por eso
    se toma la primera aparición real en el texto limpio.
    """
    if not texto:
        return ""

    prioritario = _extraer_estado_prioritario(texto, transporte=transporte)
    if prioritario:
        return prioritario

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

    patrones = [
        r"(entregad[oa](?:\s+al\s+destinatario)?)",
        r"(entrega\s+en\s+sucursal)",
        r"(en\s+espera\s+en\s+sucursal)",
        r"(recibido\s+en\s+destino)",
        r"(disponible\s+para\s+retirar[^.]{0,80})",
        r"(listo\s+para\s+retirar[^.]{0,80})",
        r"(en\s+sucursal[^.]{0,80})",
        r"(intento\s+de\s+entrega[^.]{0,80})",
        r"(visita\s+sin\s+entregar[^.]{0,80})",
        r"(no\s+entregad[oa][^.]{0,80})",
        r"(en\s+distribuci[oó]n[^.]{0,80})",
        r"(en\s+tr[aá]nsito[^.]{0,80})",
        r"(en\s+viaje[^.]{0,80})",
        r"(en\s+camino[^.]{0,80})",
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
            return m.group(1).strip(" -:;,.\n\t").upper()

    return ""


def interpretar_estado_logistico(texto, transporte=""):
    """Mapea estados externos a clases seguras del Sistema Fierro.

    Retornos posibles:
    - entregado: se puede pasar a Entregado, salvo protección ML Acordás en app.py.
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
        "transito", "distribucion", "viaje", "camino", "clasificacion", "procesamiento",
        "ingreso", "ingresado", "preimposicion", "repesaje", "admitido",
    ]):
        return "transito"

    return "desconocido"


def _leer_url(url, referer="", accept_json=False):
    req = Request(url, headers=_headers_navegador(referer=referer, accept_json=accept_json))
    with urlopen(req, timeout=25) as resp:
        raw = resp.read(1600000).decode("utf-8", errors="ignore")
    return raw


def _extraer_numero_envio(url="", seguimiento=""):
    seguimiento = str(seguimiento or "").strip()
    if seguimiento:
        return seguimiento
    m = re.search(r"/(\d{8,})/?$", str(url or ""))
    if m:
        return m.group(1)
    m = re.search(r"NumeroEnvio=(\d{8,})", str(url or ""), flags=re.I)
    if m:
        return m.group(1)
    return ""


def _texto_desde_json(data):
    partes = []

    def walk(obj):
        if obj is None:
            return
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, (dict, list, tuple)):
                    walk(value)
                else:
                    partes.append(str(value))
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                walk(item)
        else:
            partes.append(str(obj))

    walk(data)
    return " ".join(partes)


def _consultar_andreani_oficial(seguimiento=""):
    """Consulta Andreani usando credenciales oficiales si están configuradas.

    Esto evita depender del HTML público cuando Render no ve lo mismo que el navegador.
    Si no hay credenciales o Andreani devuelve error, se informa y se usa fallback HTML.
    """
    numero = str(seguimiento or "").strip()
    if not numero:
        return "", "No hay seguimiento Andreani"

    try:
        from services.andreani import andreani_configurada, andreani_trazas_envio, resumen_evento_andreani
    except Exception as e:
        return "", f"No se pudo importar servicio Andreani: {e}"

    try:
        if not andreani_configurada():
            return "", "Credenciales Andreani no configuradas"
        data = andreani_trazas_envio(numero)
        evento = data.get("ultimo_evento") or {}
        estado = resumen_evento_andreani(evento)
        if estado and estado != "Sin eventos":
            return estado.upper(), None
        # Si no hay evento único, buscar en todo el JSON
        texto = _texto_desde_json(data)
        estado = _extraer_estado_por_patrones(texto, transporte="Andreani")
        if estado:
            return estado, None
        return "", "Andreani oficial sin eventos legibles"
    except Exception as e:
        return "", str(e)


def _consultar_andreani_publico(url, seguimiento=""):
    numero = _extraer_numero_envio(url, seguimiento)
    if not numero:
        return "", "No se pudo obtener número Andreani"
    public_url = f"https://www.andreani.com/envio/{quote(numero)}"

    try:
        raw = _leer_url(public_url, referer="https://www.andreani.com/", accept_json=False)
    except HTTPError as e:
        return "", f"HTTP {e.code} Andreani público"
    except URLError as e:
        return "", f"Error de conexión Andreani público: {e.reason}"
    except Exception as e:
        return "", str(e)

    texto = _limpiar_texto_html(raw)
    estado = _extraer_estado_por_patrones(texto, transporte="Andreani")
    if estado:
        return estado, None
    return "", "Andreani público no devolvió estado legible: " + texto[:250]


def _consultar_via_cargo_endpoint(url, seguimiento=""):
    """Consulta el endpoint interno real visto en Network.

    En navegador se ve:
      https://ws.busplus.com.ar/alerce/tracking?NumeroEnvio=<nro>&tokenRecaptcha=<token>

    Probamos sin Selenium. Si Vía Cargo exige token Recaptcha válido, devolvemos error
    controlado y el sistema no rompe.
    """
    numero = _extraer_numero_envio(url, seguimiento)
    if not numero:
        return "", "No se pudo obtener NumeroEnvio"

    referer = url or f"https://viacargo.com.ar/seguimiento-de-envio/{numero}/"
    urls = [
        # Endpoint real visto en Network de Vía Cargo.
        f"https://ws.busplus.com.ar/alerce/tracking?{urlencode({'NumeroEnvio': numero, 'tokenRecaptcha': ''})}",
        f"https://ws.busplus.com.ar/alerce/tracking?{urlencode({'NumeroEnvio': numero})}",
        f"https://viacargo.com.ar/alerce/tracking?{urlencode({'NumeroEnvio': numero, 'tokenRecaptcha': ''})}",
    ]

    errores = []
    for api_url in urls:
        try:
            raw = _leer_url(api_url, referer=referer, accept_json=True)
        except HTTPError as e:
            try:
                detalle = e.read().decode("utf-8", errors="ignore")[:300]
            except Exception:
                detalle = ""
            errores.append(f"{api_url}: HTTP {e.code} {detalle}")
            continue
        except URLError as e:
            errores.append(f"{api_url}: {e.reason}")
            continue
        except Exception as e:
            errores.append(f"{api_url}: {e}")
            continue

        texto_html = _limpiar_texto_html(raw)
        estado = _extraer_estado_por_patrones(texto_html, transporte="Via Cargo")
        if estado:
            return estado, None

        try:
            data = json.loads(raw)
            texto_json = _texto_desde_json(data)
            estado = _extraer_estado_por_patrones(texto_json, transporte="Via Cargo")
            if estado:
                return estado, None
        except Exception:
            pass

        # Fallback: buscar directamente en el raw por si viene escapado.
        estado = _extraer_estado_por_patrones(raw, transporte="Via Cargo")
        if estado:
            return estado, None

        errores.append(f"{api_url}: respuesta sin estado legible")

    return "", " | ".join(errores[:2]) or "Endpoint Via Cargo no devolvió estado legible"


def consultar_tracking_url(url, transporte="", seguimiento=""):
    """Consulta una URL pública/API de tracking y devuelve el estado detectado.

    Modo APB:
    - si lee un estado claro, lo devuelve;
    - si la web cambia, bloquea o requiere formulario, devuelve error;
    - nunca lanza excepción hacia el sistema principal.
    """
    if not url:
        return {"estado": "", "error": "No hay URL de tracking"}

    transporte_norm = _normalizar(transporte)
    url_norm = _normalizar(url)

    # Andreani: preferir API oficial si está configurada. Si no, fallback público.
    if "andreani" in transporte_norm or "andreani.com" in url_norm:
        estado_oficial, error_oficial = _consultar_andreani_oficial(seguimiento=seguimiento)
        if estado_oficial:
            return {
                "estado": estado_oficial,
                "error": None,
                "texto_muestra": estado_oficial[:1200],
            }
        estado_publico, error_publico = _consultar_andreani_publico(url, seguimiento=seguimiento)
        if estado_publico:
            return {
                "estado": estado_publico,
                "error": None,
                "texto_muestra": estado_publico[:1200],
            }
        return {
            "estado": "Sin estado detectado",
            "error": error_publico or error_oficial or "No se detectó estado Andreani",
            "texto_muestra": "",
        }

    # Vía Cargo: usar endpoint interno real visto en Network. El HTML público queda como fallback.
    if "via cargo" in transporte_norm or "vía cargo" in transporte_norm or "viacargo.com" in url_norm:
        estado_api, error_api = _consultar_via_cargo_endpoint(url, seguimiento=seguimiento)
        if estado_api:
            return {
                "estado": estado_api,
                "error": None,
                "texto_muestra": estado_api[:1200],
            }
        # fallback HTML público
        try:
            raw = _leer_url(url, referer="https://viacargo.com.ar/", accept_json=False)
            texto = _limpiar_texto_html(raw)
            estado = _extraer_estado_por_patrones(texto, transporte=transporte)
            if estado:
                return {
                    "estado": estado,
                    "error": None,
                    "texto_muestra": texto[:1200],
                }
            return {
                "estado": "Sin estado detectado",
                "error": error_api or "No se detectó un estado logístico claro en Vía Cargo",
                "texto_muestra": texto[:1200],
            }
        except Exception as e:
            return {
                "estado": "Sin estado detectado",
                "error": error_api or str(e),
                "texto_muestra": "",
            }

    # Genérico: HTML simple.
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



# ─────────────────────────────────────────────
# Bridge MiCorreo integración básica
# ─────────────────────────────────────────────
# Mantiene el formulario público como fallback, pero permite usar /shipping/tracking
# cuando CORREO_MICORREO_ENABLED=true.
_consultar_correo_formulario_publico_fallback = consultar_correo_formulario


def consultar_correo_formulario(seguimiento, mercado_envios=False):
    try:
        from services.correo_argentino_micorreo import (
            consultar_tracking_envio,
            micorreo_habilitado,
        )

        if micorreo_habilitado():
            resultado_micorreo = consultar_tracking_envio(seguimiento)
            estado = str(resultado_micorreo.get("estado") or "").strip()

            if resultado_micorreo.get("ok") and estado:
                try:
                    clasificacion = interpretar_estado_logistico(
                        estado,
                        transporte="Correo Argentino",
                    )
                except Exception:
                    clasificacion = ""

                return {
                    "estado": estado,
                    "error": None,
                    "clasificacion": clasificacion,
                    "origen": "micorreo",
                    "raw": resultado_micorreo,
                }
    except Exception as e:
        print("[CORREO MICORREO] Error consultando tracking:", e)

    return _consultar_correo_formulario_publico_fallback(
        seguimiento,
        mercado_envios=mercado_envios,
    )
