"""
modules.bot_ml.api_client
-------------------------
Cliente base de Mercado Libre para Sistema Fierro.

APB / SaaS:
- Este modulo concentra configuracion, OAuth y llamadas HTTP base de ML.
- No debe depender de Flask routes.
- No debe depender directamente de modelos SQLAlchemy ni db.session.
- Las funciones que necesitan persistir en DB deben recibir objetos ya obtenidos
  por la capa que orquesta.
"""

import json
import os
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


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
        raise ValueError(f"ML conexion fallida: {e.reason}")


def ml_exchange_code_for_token(code):
    payload = {
        "grant_type": "authorization_code",
        "client_id": ml_client_id(),
        "client_secret": ml_client_secret(),
        "code": code,
        "redirect_uri": ml_redirect_uri(),
    }

    return ml_http_json(
        "POST",
        "https://api.mercadolibre.com/oauth/token",
        data=payload,
    )


def ml_guardar_token_en_cuenta(cuenta, token_data):
    cuenta.access_token = token_data.get("access_token") or cuenta.access_token
    cuenta.refresh_token = token_data.get("refresh_token") or cuenta.refresh_token

    expires_in = int(token_data.get("expires_in") or 0)
    if expires_in > 0:
        cuenta.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    cuenta.scope = token_data.get("scope") or cuenta.scope
    cuenta.estado_conexion = "conectada" if cuenta.access_token else "error"


def ml_refresh_access_token(cuenta):
    if not cuenta or not cuenta.refresh_token:
        raise ValueError("La cuenta de Mercado Libre no tiene refresh token guardado.")

    payload = {
        "grant_type": "refresh_token",
        "client_id": ml_client_id(),
        "client_secret": ml_client_secret(),
        "refresh_token": cuenta.refresh_token,
    }

    token_data = ml_http_json(
        "POST",
        "https://api.mercadolibre.com/oauth/token",
        data=payload,
    )

    ml_guardar_token_en_cuenta(cuenta, token_data)

    return cuenta


def ml_api_get_con_token(access_token, path, params=None):
    """
    GET autenticado a Mercado Libre usando un access token ya resuelto.

    APB / SaaS:
    - No busca cuenta.
    - No refresca token.
    - No commitea DB.
    - La capa orquestadora decide como obtener/persistir el token.
    """
    access_token = str(access_token or "").strip()
    if not access_token:
        raise ValueError("No hay access token valido para consultar Mercado Libre.")

    params = params or {}
    query = urlencode(params)

    url = f"https://api.mercadolibre.com{path}"
    if query:
        url = f"{url}?{query}"

    return ml_http_json(
        "GET",
        url,
        headers={"Authorization": f"Bearer {access_token}"},
    )


def ml_api_post_json_con_token(access_token, path, payload=None):
    """
    POST JSON autenticado a Mercado Libre usando un access token ya resuelto.
    """
    access_token = str(access_token or "").strip()
    if not access_token:
        raise ValueError("No hay access token valido para enviar a Mercado Libre.")

    url = f"https://api.mercadolibre.com{path}"
    data = json.dumps(payload or {}).encode("utf-8")

    req = Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    try:
        with urlopen(req) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}

    except HTTPError as e:
        detalle = e.read().decode("utf-8", errors="ignore")
        raise ValueError(f"Mercado Libre rechazo el mensaje: {detalle or e}")


def ml_api_get_binario_con_token(
    access_token,
    path,
    params=None,
    accept="application/pdf",
):
    """
    GET binario autenticado a Mercado Libre usando un access token ya resuelto.
    """
    access_token = str(access_token or "").strip()
    if not access_token:
        raise ValueError("No hay access token valido para descargar desde Mercado Libre.")

    params = params or {}
    query = urlencode(params)

    url = f"https://api.mercadolibre.com{path}"
    if query:
        url = f"{url}?{query}"

    req = Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Accept", accept)

    with urlopen(req) as response:
        contenido = response.read()
        content_type = response.headers.get("Content-Type", "")
        return contenido, content_type
