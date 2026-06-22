"""
modules/transportes/correo_argentino.py
──────────────────────────────────────
Integración Correo Argentino PAQ.AR API 2.0.

IMPORTANTE:
- Esta API NO usa email/password ni /token.
- Usa headers:
    Authorization: Apikey <CORREO_ARGENTINO_API_KEY>
    agreement: <CORREO_ARGENTINO_AGREEMENT>
- Base producción:
    https://api.correoargentino.com.ar/paqar/v1
- Base test:
    https://apitest.correoargentino.com.ar/paqar/v1

Variables Render requeridas:
    CORREO_ARGENTINO_API_KEY
    CORREO_ARGENTINO_AGREEMENT
Opcional:
    CORREO_ARGENTINO_BASE_URL
    CORREO_ARGENTINO_EXT_CLIENT
    CORREO_ARGENTINO_ENV

Compatibilidad:
- Mantiene nombres usados por selector.py:
    cotizar_correo(cp_destino, tipo_entrega="S")
    obtener_sucursales_correo_por_pedido(pedido)

Nota APB:
El PDF PAQ.AR 2.0 que estamos usando documenta auth, alta de órdenes,
cancelación, rótulos, tracking y agencias/sucursales. No documenta un endpoint
de cotización de tarifas. Por eso cotizar_correo() queda como respuesta segura
hasta tener endpoint/tabla de tarifas real.
"""

import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from datetime import datetime

# ─────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────

DEFAULT_PROD_URL = "https://api.correoargentino.com.ar/paqar/v1"
DEFAULT_TEST_URL = "https://apitest.correoargentino.com.ar/paqar/v1"

CORREO_ENV = (os.getenv("CORREO_ARGENTINO_ENV") or "prod").strip().lower()

if os.getenv("CORREO_ARGENTINO_BASE_URL"):
    CA_BASE_URL = os.getenv("CORREO_ARGENTINO_BASE_URL", "").rstrip("/")
elif CORREO_ENV in ["test", "qa", "dev"]:
    CA_BASE_URL = DEFAULT_TEST_URL
else:
    CA_BASE_URL = DEFAULT_PROD_URL

CA_API_KEY = (os.getenv("CORREO_ARGENTINO_API_KEY") or "").strip()
CA_AGREEMENT = (os.getenv("CORREO_ARGENTINO_AGREEMENT") or "").strip()
CA_EXT_CLIENT = (os.getenv("CORREO_ARGENTINO_EXT_CLIENT") or "").strip()

# Compatibilidad con nombres viejos, para que Render Shell no explote si se consultan.
CA_EMAIL = (os.getenv("CORREO_ARGENTINO_EMAIL") or "").strip()
CA_PASSWORD = (os.getenv("CORREO_ARGENTINO_PASSWORD") or "").strip()
CPS_ORIGEN = ["8504", "8500"]

# Parámetros PP6040 vigentes.
PP6040_PESO = int(os.getenv("CORREO_PP6040_PESO_GR", "3000"))
PP6040_ALTO = int(os.getenv("CORREO_PP6040_ALTO_CM", "5"))
PP6040_ANCHO = int(os.getenv("CORREO_PP6040_ANCHO_CM", "30"))
PP6040_LARGO = int(os.getenv("CORREO_PP6040_LARGO_CM", "40"))


# ─────────────────────────────────────────────
# HTTP helpers PAQ.AR
# ─────────────────────────────────────────────

def _credenciales_configuradas():
    return bool(CA_API_KEY and CA_AGREEMENT)


def _headers(extra=None):
    h = {
        "Authorization": f"Apikey {CA_API_KEY}",
        "agreement": str(CA_AGREEMENT),
        "Accept": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _leer_error_http(e):
    try:
        return e.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def _request_json(method, endpoint, payload=None, params=None, timeout=20):
    """Request JSON genérico contra PAQ.AR."""
    if not _credenciales_configuradas():
        raise RuntimeError(
            "Faltan CORREO_ARGENTINO_API_KEY y/o CORREO_ARGENTINO_AGREEMENT en Render."
        )

    endpoint = "/" + str(endpoint or "").lstrip("/")
    url = f"{CA_BASE_URL}{endpoint}"

    if params:
        qs = urlencode(params, doseq=True)
        url = f"{url}?{qs}"

    data = None
    headers = _headers()

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=data, headers=headers, method=method.upper())

    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw.strip():
                return {"_status": resp.status, "_raw": ""}
            try:
                data = json.loads(raw)
            except Exception:
                data = {"_status": resp.status, "_raw": raw}
            if isinstance(data, dict):
                data.setdefault("_status", resp.status)
            return data
    except HTTPError as e:
        body = _leer_error_http(e)
        print(f"[CORREO PAQAR] HTTP {e.code} {method} {endpoint}: {body}")
        raise
    except URLError as e:
        print(f"[CORREO PAQAR] URL error {method} {endpoint}: {e}")
        raise


def _request_raw(method, endpoint, payload=None, params=None, timeout=20):
    """Request que puede devolver texto/binario/base64 sin forzar JSON."""
    if not _credenciales_configuradas():
        raise RuntimeError(
            "Faltan CORREO_ARGENTINO_API_KEY y/o CORREO_ARGENTINO_AGREEMENT en Render."
        )

    endpoint = "/" + str(endpoint or "").lstrip("/")
    url = f"{CA_BASE_URL}{endpoint}"

    if params:
        qs = urlencode(params, doseq=True)
        url = f"{url}?{qs}"

    data = None
    headers = _headers()
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=data, headers=headers, method=method.upper())

    with urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


# ─────────────────────────────────────────────
# Autenticación / diagnóstico
# ─────────────────────────────────────────────

def validar_credenciales_correo():
    """GET /auth. La respuesta correcta es HTTP 204 sin body."""
    if not _credenciales_configuradas():
        return {
            "ok": False,
            "status": None,
            "error": "Faltan CORREO_ARGENTINO_API_KEY y/o CORREO_ARGENTINO_AGREEMENT en Render.",
            "base_url": CA_BASE_URL,
            "tipo": "correo_argentino_paqar",
        }

    url = f"{CA_BASE_URL}/auth"
    req = Request(url, headers=_headers(), method="GET")

    try:
        with urlopen(req, timeout=15) as resp:
            return {
                "ok": resp.status == 204,
                "status": resp.status,
                "error": None,
                "base_url": CA_BASE_URL,
                "agreement": CA_AGREEMENT,
                "tipo": "correo_argentino_paqar",
            }
    except HTTPError as e:
        body = _leer_error_http(e)
        return {
            "ok": False,
            "status": e.code,
            "error": body or str(e),
            "base_url": CA_BASE_URL,
            "agreement": CA_AGREEMENT,
            "tipo": "correo_argentino_paqar",
        }
    except Exception as e:
        return {
            "ok": False,
            "status": None,
            "error": str(e),
            "base_url": CA_BASE_URL,
            "agreement": CA_AGREEMENT,
            "tipo": "correo_argentino_paqar",
        }


# ─────────────────────────────────────────────
# Sucursales / agencias
# ─────────────────────────────────────────────

PROVINCIA_A_CODIGO = {
    "salta": "A",
    "buenos aires": "B",
    "provincia de buenos aires": "B",
    "caba": "C",
    "capital federal": "C",
    "ciudad autonoma de buenos aires": "C",
    "ciudad autónoma de buenos aires": "C",
    "san luis": "D",
    "entre rios": "E",
    "entre ríos": "E",
    "la rioja": "F",
    "santiago del estero": "G",
    "chaco": "H",
    "san juan": "J",
    "catamarca": "K",
    "la pampa": "L",
    "mendoza": "M",
    "misiones": "N",
    "formosa": "P",
    "neuquen": "Q",
    "neuquén": "Q",
    "rio negro": "R",
    "río negro": "R",
    "santa fe": "S",
    "tucuman": "T",
    "tucumán": "T",
    "chubut": "U",
    "tierra del fuego": "V",
    "corrientes": "W",
    "cordoba": "X",
    "córdoba": "X",
    "jujuy": "Y",
    "santa cruz": "Z",
}


def _norm(s):
    import unicodedata
    s = str(s or "").strip().lower()
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def codigo_provincia_correo(provincia):
    p = _norm(provincia)
    return PROVINCIA_A_CODIGO.get(p, "")


def _obtener_sucursales_correo_paqar(state_id=None, pickup_availability=True, package_reception=None):
    """GET /agencies con filtros opcionales."""
    params = {}
    if state_id:
        params["stateId"] = state_id
    if pickup_availability is not None:
        params["pickup_availability"] = "true" if pickup_availability else "false"
    if package_reception is not None:
        params["package_reception"] = "true" if package_reception else "false"

    try:
        data = _request_json("GET", "/agencies", params=params)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            return data["data"]
        return []
    except Exception as e:
        print("[CORREO PAQAR] Error obteniendo agencias:", e)
        return []


def _mapear_sucursal_paqar(s):
    loc = s.get("location") or {}
    geo = loc.get("geolocation") or {}

    return {
        "id": s.get("agency_id") or s.get("agencyId") or s.get("id"),
        "agency_id": s.get("agency_id") or s.get("agencyId") or s.get("id"),
        "nombre": s.get("agency_name") or s.get("agencyName") or "Punto Correo",
        "direccion": " ".join([
            str(loc.get("street_name") or "").strip(),
            str(loc.get("street_number") or "").strip(),
        ]).strip(),
        "localidad": loc.get("city_name") or "",
        "provincia": loc.get("state_name") or "",
        "cp": loc.get("zip_code") or "",
        "lat": geo.get("latitude"),
        "lng": geo.get("longitude"),
        "horario": s.get("schedule") or "",
        "telefono": s.get("phone") or "",
        "email": s.get("email") or "",
        "pickup_availability": s.get("pickup_availability"),
        "package_reception": s.get("package_reception"),
        "raw": s,
    }


def obtener_sucursales_correo_por_pedido(pedido):
    """Devuelve agencias Correo ordenadas por distancia real al cliente.

    APB/SaaS:
    - La API de Correo puede filtrar por provincia, pero eso no alcanza.
    - CP/CPA/localidad/provincia sirven para normalizar ubicación del cliente.
    - La oferta final se decide por distancia real:
      cliente con coordenadas -> sucursales con coordenadas -> ordenar por km.
    - Si no hay coordenadas confiables, devuelve [] para escalar a operador.
    """
    import os

    from services.sucursales_distancia import ordenar_sucursales_por_distancia

    provincia = getattr(pedido, "provincia", "") or ""
    state_id = codigo_provincia_correo(provincia)

    sucs = []

    # Primero intentar MiCorreo si está habilitado.
    try:
        from services.correo_argentino_micorreo import (
            consultar_sucursales as consultar_sucursales_micorreo,
        )

        resultado_micorreo = consultar_sucursales_micorreo(
            province_code=state_id or None,
        )

        if resultado_micorreo.get("ok"):
            sucs = list(resultado_micorreo.get("sucursales") or [])
        elif resultado_micorreo.get("error"):
            print(
                "[CORREO MICORREO] No se pudieron obtener sucursales:",
                resultado_micorreo.get("error"),
            )

    except Exception as e:
        print("[CORREO MICORREO] Error obteniendo sucursales:", e)

    # Fallback PAQ.AR.
    if not sucs:
        agencias = obtener_sucursales_correo(
            state_id=state_id or None,
            pickup_availability=True,
            package_reception=None,
        )
        sucs = [_mapear_sucursal_paqar(a) for a in agencias]

    if not sucs:
        return []

    prov_pedido = _norm(getattr(pedido, "provincia", "") or "")

    def _provincia_compatible(sucursal):
        if not prov_pedido:
            return True

        prov_sucursal = _norm(sucursal.get("provincia") or "")

        if not prov_sucursal:
            return True

        return prov_pedido in prov_sucursal or prov_sucursal in prov_pedido

    # La provincia solo se usa como reducción de universo.
    # La decisión final siempre la toma la distancia.
    sucs_compatibles = [s for s in sucs if _provincia_compatible(s)]

    if sucs_compatibles:
        sucs = sucs_compatibles

    radio_max_km = float(os.getenv("CORREO_SUCURSALES_RADIO_MAX_KM", "90") or 90)

    resultado_distancia = ordenar_sucursales_por_distancia(
        pedido=pedido,
        sucursales=sucs,
        radio_max_km=radio_max_km,
        limite=10,
        permitir_normalizar_pedido=True,
    )

    if not resultado_distancia.get("ok"):
        print(
            f"[CORREO PAQAR] Sin sucursales Correo confiables por distancia. "
            f"pedido={getattr(pedido, 'id', '?')} "
            f"motivo={resultado_distancia.get('motivo')} "
            f"cliente={resultado_distancia.get('cliente')}"
        )
        return []

    print(
        f"[CORREO PAQAR] Sucursales Correo ordenadas por distancia. "
        f"pedido={getattr(pedido, 'id', '?')} "
        f"cantidad={len(resultado_distancia.get('sucursales') or [])}"
    )

    return resultado_distancia.get("sucursales") or []

def cotizar_correo(cp_destino, tipo_entrega="S"):
    """Compatibilidad con selector.py.

    Si MiCorreo integración básica está habilitado, usa /rates.
    Si no, conserva fallback PAQ.AR legacy.
    """
    try:
        from services.correo_argentino_micorreo import (
            cotizar_envio as cotizar_envio_micorreo,
            micorreo_habilitado,
        )

        if micorreo_habilitado():
            resultado_micorreo = cotizar_envio_micorreo(
                cp_destino=cp_destino,
                modalidad=tipo_entrega,
                peso_gr=PP6040_PESO,
                alto_cm=PP6040_ALTO,
                ancho_cm=PP6040_ANCHO,
                largo_cm=PP6040_LARGO,
            )
            return _cotizacion_legacy_desde_micorreo(
                resultado_micorreo,
                tipo_entrega=tipo_entrega,
            )
    except Exception as e:
        print("[CORREO MICORREO] Error cotizando:", e)

    if not _credenciales_configuradas():
        return {
            "disponible": False,
            "precio": None,
            "plazo_dias": None,
            "tipo": "correo_argentino_paqar",
            "error": "Faltan CORREO_ARGENTINO_API_KEY y/o CORREO_ARGENTINO_AGREEMENT en Render.",
        }

    auth = validar_credenciales_correo()
    if not auth.get("ok"):
        return {
            "disponible": False,
            "precio": None,
            "plazo_dias": None,
            "tipo": "correo_argentino_paqar",
            "error": f"Credenciales PAQ.AR inválidas: {auth.get('error')}",
        }

    return {
        "disponible": False,
        "precio": None,
        "plazo_dias": None,
        "tipo": "correo_argentino_paqar",
        "error": "PAQ.AR API 2.0 no documenta endpoint de cotización de tarifas. Usar alta de orden/sucursales/tracking o solicitar endpoint tarifario a Correo.",
    }


# ─────────────────────────────────────────────
# Tracking
# ─────────────────────────────────────────────

def consultar_tracking_paqar(tracking_numbers, ext_client=None):
    """GET /tracking. Acepta un TN o lista de TN."""
    if isinstance(tracking_numbers, str):
        tracking_numbers = [tracking_numbers]

    payload = [{"trackingNumber": str(tn).strip()} for tn in tracking_numbers if str(tn or "").strip()]
    params = {}
    ext = ext_client if ext_client is not None else CA_EXT_CLIENT
    if ext:
        params["extClient"] = str(ext).zfill(3)[-3:]

    try:
        # Aunque la doc diga GET con body, urllib permite GET con data de forma irregular.
        # Usamos POST-like raw si el gateway lo tolera; si no, se ajusta con la respuesta real.
        return _request_json("GET", "/tracking", payload=payload, params=params)
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "tracking_numbers": tracking_numbers,
            "tipo": "correo_argentino_paqar",
        }


# ─────────────────────────────────────────────
# Alta de orden / etiqueta: preparado para próxima fase
# ─────────────────────────────────────────────

def crear_orden_paqar(payload_order):
    """POST /orders. Espera payload ya validado según manual."""
    return _request_json("POST", "/orders", payload=payload_order)


def obtener_rotulos_paqar(tracking_numbers, seller_id="", label_format="10x15"):
    """POST /labels. Devuelve respuesta JSON con fileBase64."""
    if isinstance(tracking_numbers, str):
        tracking_numbers = [tracking_numbers]
    payload = [{"sellerId": seller_id or "", "trackingNumber": tn} for tn in tracking_numbers]
    params = {}
    if label_format:
        params["labelFormat"] = label_format
    return _request_json("POST", "/labels", payload=payload, params=params)


def cancelar_orden_paqar(tracking_number):
    """PATCH /orders/{trackingNumber}/cancel."""
    endpoint = f"/orders/{tracking_number}/cancel"
    return _request_json("PATCH", endpoint, payload={})


# Alias legados por si alguna parte vieja del sistema los usa.
def cotizar_correo_argentino(cp_destino):
    return cotizar_correo(cp_destino, tipo_entrega="S")


def obtener_sucursales_correo(cp_destino=None):
    return obtener_sucursales_correo_por_pedido(type("PedidoTmp", (), {
        "codigo_postal": cp_destino or "",
        "provincia": "",
        "localidad": "",
        "direccion": "",
    })())
