import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

_TOKEN_CACHE = {
    "access_token": "",
    "expires_at": 0,
}


def andreani_configurada():
    return bool(os.getenv("ANDREANI_CLIENT_ID") and os.getenv("ANDREANI_CLIENT_SECRET"))


def _base_url():
    return (os.getenv("ANDREANI_BASE_URL") or "https://apis.andreani.com/v2").rstrip("/")


def _login_url():
    url = (os.getenv("ANDREANI_LOGIN_URL") or "").strip()
    if url:
        return url
    base = _base_url()
    if base.endswith("/v2"):
        base = base[:-3]
    return base.rstrip("/") + "/login"


def _leer_json_response(response):
    raw = response.read().decode("utf-8", "ignore")
    if not raw:
        return {}
    return json.loads(raw)


def _post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=20) as response:
        return _leer_json_response(response)


def _post_form(url, payload):
    data = urlencode(payload).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=20) as response:
        return _leer_json_response(response)


def _extraer_token(data):
    if not isinstance(data, dict):
        return "", 0
    token = data.get("access_token") or data.get("token") or data.get("accessToken") or data.get("jwt") or ""
    expires_in = data.get("expires_in") or data.get("expiresIn") or data.get("expires") or 24 * 3600
    try:
        expires_in = int(expires_in)
    except Exception:
        expires_in = 24 * 3600
    return str(token or "").strip(), expires_in


def andreani_obtener_token(forzar=False):
    if not andreani_configurada():
        raise RuntimeError("Credenciales Andreani no configuradas. Cargá ANDREANI_CLIENT_ID y ANDREANI_CLIENT_SECRET en Render.")

    ahora = int(time.time())
    if not forzar and _TOKEN_CACHE.get("access_token") and _TOKEN_CACHE.get("expires_at", 0) > ahora + 300:
        return _TOKEN_CACHE["access_token"]

    client_id = os.getenv("ANDREANI_CLIENT_ID", "").strip()
    client_secret = os.getenv("ANDREANI_CLIENT_SECRET", "").strip()
    url = _login_url()

    intentos = [
        ("json_client", _post_json, {"client_id": client_id, "client_secret": client_secret}),
        ("json_usuario", _post_json, {"username": client_id, "password": client_secret}),
        ("form_client", _post_form, {"client_id": client_id, "client_secret": client_secret}),
        ("form_usuario", _post_form, {"username": client_id, "password": client_secret}),
    ]

    errores = []
    for nombre, fn, payload in intentos:
        try:
            data = fn(url, payload)
            token, expires_in = _extraer_token(data)
            if token:
                _TOKEN_CACHE["access_token"] = token
                _TOKEN_CACHE["expires_at"] = ahora + min(expires_in, 24 * 3600)
                return token
            errores.append(f"{nombre}: respuesta sin token")
        except HTTPError as e:
            try:
                detalle = e.read().decode("utf-8", "ignore")[:300]
            except Exception:
                detalle = ""
            errores.append(f"{nombre}: HTTP {e.code} {detalle}")
        except URLError as e:
            errores.append(f"{nombre}: {e.reason}")
        except Exception as e:
            errores.append(f"{nombre}: {e}")

    raise RuntimeError("No se pudo obtener token Andreani. " + " | ".join(errores[:4]))


def _get_json(url, token):
    req = Request(
        url,
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urlopen(req, timeout=25) as response:
        return _leer_json_response(response)


def andreani_trazas_envio(numero_seguimiento):
    numero = str(numero_seguimiento or "").strip()
    if not numero:
        raise RuntimeError("El pedido no tiene número de seguimiento Andreani.")

    token = andreani_obtener_token()
    url = f"{_base_url()}/envios/{quote(numero)}/trazas"
    try:
        data = _get_json(url, token)
    except HTTPError as e:
        if e.code == 401:
            token = andreani_obtener_token(forzar=True)
            data = _get_json(url, token)
        else:
            try:
                detalle = e.read().decode("utf-8", "ignore")[:300]
            except Exception:
                detalle = ""
            raise RuntimeError(f"Andreani devolvió HTTP {e.code}. {detalle}")

    eventos = data.get("eventos") if isinstance(data, dict) else None
    if eventos is None and isinstance(data, list):
        eventos = data
    if eventos is None:
        eventos = []

    if not isinstance(eventos, list):
        eventos = []

    return {
        "raw": data,
        "eventos": eventos,
        "ultimo_evento": ultimo_evento_andreani(eventos),
    }


def _fecha_evento(evento):
    if not isinstance(evento, dict):
        return ""
    return str(evento.get("Fecha") or evento.get("fecha") or evento.get("fechaEvento") or evento.get("fechaEstado") or "")


def ultimo_evento_andreani(eventos):
    eventos_validos = [e for e in (eventos or []) if isinstance(e, dict)]
    if not eventos_validos:
        return {}
    return sorted(eventos_validos, key=_fecha_evento)[-1]


def resumen_evento_andreani(evento):
    if not isinstance(evento, dict) or not evento:
        return "Sin eventos"
    estado = evento.get("Estado") or evento.get("estado") or ""
    nombre_evento = evento.get("Evento") or evento.get("evento") or ""
    sucursal = evento.get("Sucursal") or evento.get("sucursal") or ""
    partes = [str(x).strip() for x in [estado, nombre_evento, sucursal] if str(x or "").strip()]
    return " | ".join(partes) if partes else "Evento Andreani registrado"
