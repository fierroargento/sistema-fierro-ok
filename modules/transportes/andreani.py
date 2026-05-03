"""
modules/transportes/andreani.py
────────────────────────────────
Integración con la API de Andreani.
⚠️  EN STANDBY — requiere credenciales de API de Andreani.

Para activar:
    1. Solicitar credenciales a integraciones@andreani.com
    2. Agregar al .env:
        ANDREANI_USUARIO=tu_usuario
        ANDREANI_PASSWORD=tu_password
        ANDREANI_CONTRATO=AND00SUC  (o el contrato que te asignen)
    3. Descomentar la función cotizar_andreani_real() abajo

Mientras tanto cotizar_andreani() devuelve disponible=False
para que el selector use Correo Argentino automáticamente.
"""

import os
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# ── Configuración ────────────────────────────────────────────────────
ANDREANI_USUARIO   = os.getenv("ANDREANI_USUARIO", "")
ANDREANI_PASSWORD  = os.getenv("ANDREANI_PASSWORD", "")
ANDREANI_CONTRATO  = os.getenv("ANDREANI_CONTRATO", "AND00SUC")
ANDREANI_BASE_URL  = "https://apis.andreani.com/v1"

# Datos del paquete PP6040
PP6040_PESO_G  = 3000   # gramos
PP6040_VOLUMEN = 6000   # cm³ (30x40x5)


def _modulo_activo():
    return bool(ANDREANI_USUARIO and ANDREANI_PASSWORD)


def cotizar_andreani(cp_destino):
    """
    Cotiza el envío del PP6040 con Andreani.

    Mientras no haya credenciales devuelve disponible=False
    y el selector usa Correo Argentino automáticamente.

    Devuelve dict con:
        {
            "disponible": True/False,
            "precio": 11200.0,
            "plazo_dias": 2,
            "tipo": "andreani",
            "servicio": "Estándar",
            "error": None
        }
    """
    if not _modulo_activo():
        return {
            "disponible": False,
            "precio":     None,
            "tipo":       "andreani",
            "error":      "Credenciales Andreani no configuradas — pendiente solicitar a integraciones@andreani.com",
        }

    # ── Cuando tengas credenciales, descomentar esto ──────────────────
    # return _cotizar_andreani_real(cp_destino)
    # ─────────────────────────────────────────────────────────────────

    return {
        "disponible": False,
        "precio":     None,
        "tipo":       "andreani",
        "error":      "Módulo Andreani en standby",
    }


# ── Implementación real (activar cuando lleguen las credenciales) ─────

def _cotizar_andreani_real(cp_destino):
    """
    Cotización real via API de Andreani.
    Activar cuando se tengan las credenciales.
    """
    try:
        # 1) Obtener token
        credenciales = json.dumps({
            "usuario":    ANDREANI_USUARIO,
            "contrasena": ANDREANI_PASSWORD,
        }).encode("utf-8")

        req_token = Request(
            f"{ANDREANI_BASE_URL}/usuarios/tokens",
            data=credenciales,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req_token, timeout=10) as r:
            token_data = json.loads(r.read().decode("utf-8"))
        token = token_data.get("token", "")

        if not token:
            return {"disponible": False, "tipo": "andreani", "error": "No se pudo obtener token Andreani"}

        # 2) Cotizar
        payload = json.dumps({
            "cpDestino":  str(cp_destino),
            "contrato":   ANDREANI_CONTRATO,
            "peso":       PP6040_PESO_G,
            "volumen":    PP6040_VOLUMEN,
        }).encode("utf-8")

        req_cot = Request(
            f"{ANDREANI_BASE_URL}/tarifas",
            data=payload,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        with urlopen(req_cot, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))

        precio = float(data.get("tarifaConIva") or data.get("tarifa") or 0)
        plazo  = int(data.get("diasHabiles") or 0)

        if precio <= 0:
            return {"disponible": False, "tipo": "andreani", "error": "Sin cobertura para ese CP"}

        return {
            "disponible": True,
            "precio":     precio,
            "plazo_dias": plazo,
            "tipo":       "andreani",
            "servicio":   "Estándar",
            "error":      None,
        }

    except HTTPError as e:
        print(f"[ANDREANI] Error HTTP {e.code}:", e.read().decode())
        return {"disponible": False, "tipo": "andreani", "error": f"Error HTTP {e.code}"}
    except Exception as e:
        print(f"[ANDREANI] Error:", e)
        return {"disponible": False, "tipo": "andreani", "error": str(e)}
