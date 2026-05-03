"""
modules/transportes/correo_argentino.py
────────────────────────────────────────
Integración con la API REST de MiCorreo (Correo Argentino).
Documentación oficial: https://api.correoargentino.com.ar/micorreo/v1

Credenciales en .env:
    CORREO_ARGENTINO_EMAIL=fierro.argentoventas@gmail.com
    CORREO_ARGENTINO_PASSWORD=tu_contraseña
"""

import os
import json
import base64
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# ── Configuración ────────────────────────────────────────────────────
CA_EMAIL     = os.getenv("CORREO_ARGENTINO_EMAIL", "")
CA_PASSWORD  = os.getenv("CORREO_ARGENTINO_PASSWORD", "")
CA_BASE_URL  = "https://api.correoargentino.com.ar/micorreo/v1"

# Datos del paquete PP6040 (plegable)
PP6040_PESO   = 3000   # gramos
PP6040_ALTO   = 5      # cm
PP6040_ANCHO  = 30     # cm
PP6040_LARGO  = 40     # cm

# CPs de origen (comarca - se prueba el más conveniente)
CPS_ORIGEN = ["8504", "8500"]

# Cache del token para no pedir uno nuevo en cada cotización
_token_cache = {
    "token":      None,
    "expires":    None,
    "customerId": None,
}


def _modulo_activo():
    return bool(CA_EMAIL and CA_PASSWORD)


def _ca_post(endpoint, payload=None, token=None):
    """Realiza un POST a la API de MiCorreo."""
    url = f"{CA_BASE_URL}/{endpoint.lstrip('/')}"
    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        # Basic Auth para obtener el token
        credenciales = base64.b64encode(f"{CA_EMAIL}:{CA_PASSWORD}".encode()).decode()
        headers["Authorization"] = f"Basic {credenciales}"

    req = Request(
        url,
        data=json.dumps(payload or {}).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ca_get(endpoint, params=None, token=None):
    """Realiza un GET a la API de MiCorreo."""
    from urllib.parse import urlencode
    url = f"{CA_BASE_URL}/{endpoint.lstrip('/')}"
    if params:
        url += "?" + urlencode(params)

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(url, headers=headers, method="GET")
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _obtener_token():
    """
    Obtiene el JWT de autenticación.
    Usa cache para no pedir uno nuevo en cada cotización.
    Renueva si está por vencer.
    """
    global _token_cache

    ahora = datetime.utcnow()

    # Verificar si el token en cache sigue siendo válido (margen de 5 min)
    if (
        _token_cache["token"]
        and _token_cache["expires"]
        and _token_cache["expires"] > ahora + timedelta(minutes=5)
    ):
        return _token_cache["token"], _token_cache["customerId"]

    # Obtener nuevo token
    try:
        data = _ca_post("/token")
        token = data.get("token", "")
        expires_str = data.get("expires", "")

        try:
            expires = datetime.strptime(expires_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            expires = ahora + timedelta(hours=2)

        # Obtener customerId
        customer_data = _ca_post(
            "/users/validate",
            {"email": CA_EMAIL, "password": CA_PASSWORD},
            token=token,
        )
        customer_id = customer_data.get("customerId", "")

        _token_cache = {
            "token":      token,
            "expires":    expires,
            "customerId": customer_id,
        }

        print(f"[CORREO ARG] Token obtenido, customerId={customer_id}, expira={expires_str}")
        return token, customer_id

    except HTTPError as e:
        print(f"[CORREO ARG] Error HTTP {e.code} obteniendo token:", e.read().decode())
        return None, None
    except Exception as e:
        print(f"[CORREO ARG] Error obteniendo token:", e)
        return None, None


def cotizar_correo(cp_destino, tipo_entrega="D"):
    """
    Cotiza el envío del PP6040 desde los CPs de origen al CP destino.

    cp_destino: CP del cliente (string)
    tipo_entrega: "D" domicilio, "S" sucursal

    Devuelve dict con:
        {
            "disponible": True/False,
            "precio": 12500.0,
            "plazo_dias": 3,
            "cp_origen": "8500",
            "tipo": "correo_argentino",
            "servicio": "Envío Clásico",
            "error": None  # o mensaje de error
        }
    """
    if not _modulo_activo():
        return {"disponible": False, "error": "Correo Argentino no configurado", "tipo": "correo_argentino"}

    token, customer_id = _obtener_token()
    if not token or not customer_id:
        return {"disponible": False, "error": "Error de autenticación", "tipo": "correo_argentino"}

    cp_destino = str(cp_destino or "").strip()
    if not cp_destino:
        return {"disponible": False, "error": "CP destino vacío", "tipo": "correo_argentino"}

    mejor = None

    # Probar con cada CP de origen y quedarse con el más barato
    for cp_origen in CPS_ORIGEN:
        try:
            payload = {
                "customerId":            customer_id,
                "postalCodeOrigin":      cp_origen,
                "postalCodeDestination": cp_destino,
                "deliveredType":         tipo_entrega,
                "dimensions": {
                    "weight": PP6040_PESO,
                    "height": PP6040_ALTO,
                    "width":  PP6040_ANCHO,
                    "length": PP6040_LARGO,
                },
            }

            data = _ca_post("/rates", payload, token=token)

            # La API devuelve lista de servicios disponibles
            servicios = data if isinstance(data, list) else data.get("rates", [data])

            for servicio in servicios:
                precio = float(servicio.get("price") or servicio.get("precio") or 0)
                if precio <= 0:
                    continue

                plazo = int(servicio.get("days") or servicio.get("plazo") or 0)
                nombre_servicio = servicio.get("name") or servicio.get("service") or "Envío Clásico"

                if mejor is None or precio < mejor["precio"]:
                    mejor = {
                        "disponible":  True,
                        "precio":      precio,
                        "plazo_dias":  plazo,
                        "cp_origen":   cp_origen,
                        "tipo":        "correo_argentino",
                        "servicio":    nombre_servicio,
                        "error":       None,
                    }

            print(f"[CORREO ARG] CP origen {cp_origen} → destino {cp_destino}: {mejor}")

        except HTTPError as e:
            error_body = e.read().decode()
            print(f"[CORREO ARG] Error HTTP {e.code} cotizando CP {cp_origen}→{cp_destino}:", error_body)
            # 402 generalmente significa CP destino no disponible
            if e.code == 402:
                continue
        except Exception as e:
            print(f"[CORREO ARG] Error cotizando CP {cp_origen}→{cp_destino}:", e)
            continue

    if mejor:
        return mejor

    return {
        "disponible": False,
        "precio":     None,
        "tipo":       "correo_argentino",
        "error":      f"Sin cobertura para CP {cp_destino}",
    }


def obtener_sucursales_correo(provincia_code):
    """
    Devuelve las sucursales de Correo Argentino para una provincia.
    provincia_code: "B" (Buenos Aires), "C" (CABA), "X" (Córdoba), etc.

    Códigos de provincia:
    B=Buenos Aires, C=CABA, X=Córdoba, S=Santa Fe, M=Mendoza,
    T=Tucumán, H=Chaco, P=Formosa, N=Misiones, E=Entre Ríos,
    W=Corrientes, G=Santiago del Estero, A=Salta, J=San Juan,
    D=San Luis, K=Catamarca, F=La Rioja, Q=Neuquén, R=Río Negro,
    U=Chubut, Z=Santa Cruz, V=Tierra del Fuego, L=La Pampa, Y=Jujuy
    """
    if not _modulo_activo():
        return []

    token, customer_id = _obtener_token()
    if not token or not customer_id:
        return []

    try:
        data = _ca_get(
            "/agencies",
            params={"customerId": customer_id, "provinceCode": provincia_code},
            token=token,
        )
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[CORREO ARG] Error obteniendo sucursales provincia {provincia_code}:", e)
        return []
