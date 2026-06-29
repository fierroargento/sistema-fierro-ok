"""
services/correo_argentino_micorreo.py

Integración Correo Argentino / MiCorreo - integración básica.

APB SaaS:
- No depende de app.py.
- No guarda credenciales en código.
- No genera envíos, no paga, no imprime etiquetas.
- Cubre funciones seguras ya validadas:
  token, customerId, sucursales y cotización.

Variables esperadas:
- CORREO_MICORREO_ENABLED=true/false
- CORREO_MICORREO_BASE_URL
- CORREO_MICORREO_INTEGRACION_USER
- CORREO_MICORREO_INTEGRACION_PASS
- CORREO_MICORREO_USER
- CORREO_MICORREO_PASS
- CORREO_MICORREO_CUSTOMER_ID
- CORREO_MICORREO_CP_ORIGEN
"""

import base64
import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TIPO_INTEGRACION = "correo_argentino_micorreo"

DEFAULT_BASE_URL = "https://api.correoargentino.com.ar/micorreo/v1"

FUNCIONES_MICORREO_DEFAULT = {
    "cotizacion": True,
    "sucursales": True,
    "tracking": True,
    "importacion_envios": False,
    "etiquetas": False,
    "pago": False,
}

FUNCIONES_MICORREO_ENV = {
    "cotizacion": "CORREO_MICORREO_FEATURE_COTIZACION",
    "sucursales": "CORREO_MICORREO_FEATURE_SUCURSALES",
    "tracking": "CORREO_MICORREO_FEATURE_TRACKING",
    "importacion_envios": "CORREO_MICORREO_FEATURE_IMPORTACION_ENVIOS",
    "etiquetas": "CORREO_MICORREO_FEATURE_ETIQUETAS",
    "pago": "CORREO_MICORREO_FEATURE_PAGO",
}


@dataclass(frozen=True)
class MicorreoConfig:
    enabled: bool
    base_url: str
    integracion_user: str
    integracion_pass: str
    micorreo_user: str
    micorreo_pass: str
    customer_id: str
    cp_origen: str
    timeout: float


def _env(nombre, default=""):
    return str(os.getenv(nombre, default) or "").strip()


def _env_bool(nombre, default="false"):
    return _env(nombre, default).lower() in {"1", "true", "si", "sí", "yes", "on"}


def cargar_config_desde_env():
    return MicorreoConfig(
        enabled=_env_bool("CORREO_MICORREO_ENABLED", "false"),
        base_url=_env("CORREO_MICORREO_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        integracion_user=_env("CORREO_MICORREO_INTEGRACION_USER"),
        integracion_pass=_env("CORREO_MICORREO_INTEGRACION_PASS"),
        micorreo_user=_env("CORREO_MICORREO_USER"),
        micorreo_pass=_env("CORREO_MICORREO_PASS"),
        customer_id=_env("CORREO_MICORREO_CUSTOMER_ID"),
        cp_origen=_env("CORREO_MICORREO_CP_ORIGEN", "8500"),
        timeout=float(_env("CORREO_MICORREO_TIMEOUT", "20") or 20),
    )


def micorreo_habilitado(config=None):
    cfg = config or cargar_config_desde_env()
    return bool(cfg.enabled)


def obtener_capacidades(config=None):
    """Devuelve capacidades MiCorreo configurables por empresa/entorno.

    APB SaaS:
    - No todas las empresas tienen por qué usar todas las funciones.
    - Lo riesgoso queda apagado por defecto.
    - No se habilitan pago, etiquetas ni importación salvo env explícita.
    """
    cfg = config or cargar_config_desde_env()
    funciones = {}

    for nombre, default in FUNCIONES_MICORREO_DEFAULT.items():
        env_name = FUNCIONES_MICORREO_ENV[nombre]
        funciones[nombre] = _env_bool(env_name, "true" if default else "false")

    if not cfg.enabled:
        funciones = {nombre: False for nombre in funciones}

    return {
        "ok": True,
        "tipo": TIPO_INTEGRACION,
        "enabled": bool(cfg.enabled),
        "base_url": cfg.base_url,
        "funciones": funciones,
    }


def funcion_habilitada(nombre, config=None):
    capacidades = obtener_capacidades(config)
    return bool((capacidades.get("funciones") or {}).get(str(nombre or "").strip(), False))



def _error(mensaje, status=None, **extra):
    data = {
        "ok": False,
        "status": status,
        "error": mensaje,
        "tipo": TIPO_INTEGRACION,
    }
    data.update(extra)
    return data


def _ok(status=200, **extra):
    data = {
        "ok": True,
        "status": status,
        "error": None,
        "tipo": TIPO_INTEGRACION,
    }
    data.update(extra)
    return data


def _parse_json(raw):
    texto = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw or "")
    if not texto.strip():
        return None
    try:
        return json.loads(texto)
    except Exception:
        return {"raw": texto}


def _basic_header(user, password):
    raw = f"{user}:{password}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _request_json(method, path, config, token=None, body=None, query=None, basic_auth=None):
    path = "/" + str(path or "").lstrip("/")
    url = f"{config.base_url}{path}"

    if query:
        url = f"{url}?{urlencode(query, doseq=True)}"

    headers = {"Accept": "application/json"}
    data = None

    if basic_auth:
        headers["Authorization"] = _basic_header(basic_auth[0], basic_auth[1])

    if token:
        headers["Authorization"] = f"Bearer {token}"

    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=data, headers=headers, method=method.upper())

    try:
        with urlopen(req, timeout=config.timeout) as resp:
            return resp.status, _parse_json(resp.read())
    except HTTPError as e:
        return e.code, _parse_json(e.read())
    except URLError as e:
        return None, {"message": str(e)}
    except Exception as e:
        return None, {"message": str(e)}


def obtener_token(config=None):
    cfg = config or cargar_config_desde_env()

    if not cfg.enabled:
        return _error("Integración MiCorreo deshabilitada.", base_url=cfg.base_url)

    if not cfg.integracion_user or not cfg.integracion_pass:
        return _error(
            "Faltan credenciales de integración MiCorreo.",
            base_url=cfg.base_url,
        )

    # MiCorreo responde correctamente cuando POST /token lleva body JSON.
    # Evita timeouts 504 observados con urllib enviando POST sin body.
    status, data = _request_json(
        "POST",
        "/token",
        cfg,
        body={},
        basic_auth=(cfg.integracion_user, cfg.integracion_pass),
    )

    if not (status and 200 <= status < 300):
        return _error(
            "No se pudo obtener token MiCorreo.",
            status=status,
            respuesta=data,
            base_url=cfg.base_url,
        )

    token = data.get("token") if isinstance(data, dict) else None
    expire = data.get("expire") if isinstance(data, dict) else None

    if not token:
        return _error(
            "MiCorreo respondió sin token.",
            status=status,
            respuesta=data,
            base_url=cfg.base_url,
        )

    return _ok(status=status, token=token, expire=expire, base_url=cfg.base_url)


def validar_usuario_micorreo(token, config=None):
    cfg = config or cargar_config_desde_env()

    if not token:
        return _error("Falta token MiCorreo.")

    if not cfg.micorreo_user or not cfg.micorreo_pass:
        return _error("Faltan usuario/contraseña MiCorreo para validar customerId.")

    status, data = _request_json(
        "POST",
        "/users/validate",
        cfg,
        token=token,
        body={
            "email": cfg.micorreo_user,
            "password": cfg.micorreo_pass,
        },
    )

    if not (status and 200 <= status < 300):
        return _error(
            "No se pudo validar usuario MiCorreo.",
            status=status,
            respuesta=data,
        )

    customer_id = data.get("customerId") if isinstance(data, dict) else None

    if not customer_id:
        return _error(
            "MiCorreo validó usuario pero no devolvió customerId.",
            status=status,
            respuesta=data,
        )

    return _ok(status=status, customer_id=str(customer_id))


def obtener_customer_id(config=None, token=None):
    cfg = config or cargar_config_desde_env()

    if cfg.customer_id:
        return _ok(status=200, customer_id=cfg.customer_id, fuente="env")

    token_result = {"token": token} if token else obtener_token(cfg)

    if not token_result.get("token"):
        return _error(
            "No se pudo resolver customerId porque no hay token.",
            respuesta=token_result,
        )

    return validar_usuario_micorreo(token_result["token"], cfg)


def _obtener_token_y_customer_id(config=None, token=None, customer_id=None):
    cfg = config or cargar_config_desde_env()

    token_real = token
    if not token_real:
        token_result = obtener_token(cfg)
        if not token_result.get("ok"):
            return token_result
        token_real = token_result["token"]

    customer_real = str(customer_id or cfg.customer_id or "").strip()
    if not customer_real:
        customer_result = obtener_customer_id(cfg, token=token_real)
        if not customer_result.get("ok"):
            return customer_result
        customer_real = customer_result["customer_id"]

    return _ok(status=200, token=token_real, customer_id=customer_real)


def normalizar_sucursal(raw):
    raw = raw or {}
    loc = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    address = loc.get("address") if isinstance(loc.get("address"), dict) else {}
    geo = loc.get("geolocation") if isinstance(loc.get("geolocation"), dict) else {}
    services = raw.get("services") if isinstance(raw.get("services"), dict) else {}

    def primero(*valores):
        for valor in valores:
            if valor not in (None, ""):
                return valor
        return ""

    calle = primero(
        address.get("street_name"),
        address.get("streetName"),
        address.get("street"),
        loc.get("street_name"),
        loc.get("streetName"),
        raw.get("street_name"),
        raw.get("streetName"),
    )

    altura = primero(
        address.get("street_number"),
        address.get("streetNumber"),
        address.get("number"),
        loc.get("street_number"),
        loc.get("streetNumber"),
        raw.get("street_number"),
        raw.get("streetNumber"),
    )

    return {
        "id": primero(raw.get("code"), raw.get("agency_id"), raw.get("agencyId"), raw.get("id")),
        "codigo": primero(raw.get("code"), raw.get("agency_id"), raw.get("agencyId"), raw.get("id")),
        "nombre": primero(raw.get("name"), raw.get("agency_name"), raw.get("agencyName"), "Sucursal Correo Argentino"),
        "direccion": " ".join([str(calle).strip(), str(altura).strip()]).strip(),
        "localidad": primero(
            loc.get("city_name"),
            loc.get("cityName"),
            address.get("locality"),
            address.get("city"),
            raw.get("city"),
        ),
        "provincia": primero(
            loc.get("state_name"),
            loc.get("stateName"),
            address.get("province"),
            address.get("state"),
            raw.get("province"),
        ),
        "cp": primero(
            loc.get("zip_code"),
            loc.get("zipCode"),
            address.get("postalCode"),
            address.get("zipCode"),
            address.get("zip_code"),
            raw.get("zipCode"),
            raw.get("postalCode"),
        ),
        "lat": primero(
            geo.get("latitude"),
            geo.get("lat"),
            loc.get("latitude"),
            loc.get("lat"),
            raw.get("latitude"),
            raw.get("lat"),
        ),
        "lng": primero(
            geo.get("longitude"),
            geo.get("lng"),
            geo.get("lon"),
            loc.get("longitude"),
            loc.get("lng"),
            loc.get("lon"),
            raw.get("longitude"),
            raw.get("lng"),
            raw.get("lon"),
        ),
        "horario": primero(raw.get("schedule"), raw.get("horario")),
        "telefono": primero(raw.get("phone"), raw.get("telefono")),
        "email": primero(raw.get("email")),
        "pickup_availability": primero(
            raw.get("pickup_availability"),
            raw.get("pickupAvailability"),
            services.get("pickupAvailability"),
            services.get("pickup_availability"),
        ),
        "package_reception": primero(
            raw.get("package_reception"),
            raw.get("packageReception"),
            services.get("packageReception"),
            services.get("package_reception"),
        ),
        "raw": raw,
    }


def consultar_sucursales(province_code=None, customer_id=None, config=None, token=None):
    cfg = config or cargar_config_desde_env()

    if not funcion_habilitada("sucursales", cfg):
        return _error("Función sucursales MiCorreo deshabilitada.")

    contexto = _obtener_token_y_customer_id(cfg, token=token, customer_id=customer_id)

    if not contexto.get("ok"):
        return contexto

    query = {
        "customerId": contexto["customer_id"],
    }

    if province_code:
        query["provinceCode"] = str(province_code).strip().upper()

    status, data = _request_json(
        "GET",
        "/agencies",
        cfg,
        token=contexto["token"],
        query=query,
    )

    if not (status and 200 <= status < 300):
        return _error(
            "No se pudieron consultar sucursales MiCorreo.",
            status=status,
            respuesta=data,
        )

    sucursales_raw = data if isinstance(data, list) else data.get("agencies", []) if isinstance(data, dict) else []

    return _ok(
        status=status,
        customer_id=contexto["customer_id"],
        cantidad=len(sucursales_raw),
        sucursales=[normalizar_sucursal(s) for s in sucursales_raw],
    )


def _normalizar_modalidad(modalidad):
    texto = str(modalidad or "").strip().lower()

    if texto in {"s", "sucursal", "agency", "retiro"}:
        return "S"

    if texto in {"d", "domicilio", "home", "homedelivery", "home_delivery"}:
        return "D"

    return str(modalidad or "D").strip().upper()


def _normalizar_texto_servicio(texto):
    import unicodedata

    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def servicio_preferido():
    """Servicio preferido configurable.

    Fierro usa Clásico / PAQ.AR Clásico.
    En SaaS se puede cambiar por env sin tocar código.
    """
    return _normalizar_texto_servicio(
        _env("CORREO_MICORREO_SERVICIO_PREFERIDO", "clasico")
    )


def normalizar_cotizacion(raw, modalidad):
    raw = raw or {}
    producto = raw.get("productName") or raw.get("name") or raw.get("product") or ""

    return {
        "producto": producto,
        "producto_normalizado": _normalizar_texto_servicio(producto),
        "precio": raw.get("price") or raw.get("amount") or raw.get("total"),
        "plazo_min": raw.get("deliveryTimeMin") or raw.get("delivery_time_min"),
        "plazo_max": raw.get("deliveryTimeMax") or raw.get("delivery_time_max"),
        "modalidad": modalidad,
        "raw": raw,
    }


def ordenar_cotizaciones_por_preferencia(cotizaciones):
    """Ordena cotizaciones dejando primero el servicio preferido.

    No descarta otras opciones: Expreso sigue disponible para gestión manual/SaaS.
    """
    preferido = servicio_preferido()
    cotizaciones = list(cotizaciones or [])

    def key(cotizacion):
        producto = _normalizar_texto_servicio(cotizacion.get("producto"))
        precio = cotizacion.get("precio")
        tiene_precio = precio is not None
        coincide = bool(preferido and preferido in producto)

        return (
            0 if coincide else 1,
            0 if tiene_precio else 1,
            float(precio or 999999999),
        )

    return sorted(cotizaciones, key=key)


def cotizar_envio(
    cp_destino,
    modalidad="D",
    peso_gr=3200,
    alto_cm=5,
    ancho_cm=42,
    largo_cm=36,
    cp_origen=None,
    customer_id=None,
    config=None,
    token=None,
):
    cfg = config or cargar_config_desde_env()

    if not funcion_habilitada("cotizacion", cfg):
        return _error("Función cotización MiCorreo deshabilitada.")

    contexto = _obtener_token_y_customer_id(cfg, token=token, customer_id=customer_id)

    if not contexto.get("ok"):
        return contexto

    modalidad_normalizada = _normalizar_modalidad(modalidad)
    origen = str(cp_origen or cfg.cp_origen or "").strip()
    destino = str(cp_destino or "").strip()

    if not origen:
        return _error("Falta CP de origen para cotizar Correo Argentino.")

    if not destino:
        return _error("Falta CP de destino para cotizar Correo Argentino.")

    body = {
        "customerId": contexto["customer_id"],
        "postalCodeOrigin": origen,
        "postalCodeDestination": destino,
        "deliveredType": modalidad_normalizada,
        "dimensions": {
            "weight": int(peso_gr),
            "height": int(alto_cm),
            "width": int(ancho_cm),
            "length": int(largo_cm),
        },
    }

    status, data = _request_json(
        "POST",
        "/rates",
        cfg,
        token=contexto["token"],
        body=body,
    )

    if not (status and 200 <= status < 300):
        return _error(
            "No se pudo cotizar Correo Argentino.",
            status=status,
            respuesta=data,
            request=body,
        )

    if isinstance(data, dict) and isinstance(data.get("rates"), list):
        rates = data["rates"]
    elif isinstance(data, list):
        rates = data
    else:
        rates = []

    cotizaciones = [
        normalizar_cotizacion(r, modalidad_normalizada)
        for r in rates
    ]

    return _ok(
        status=status,
        customer_id=contexto["customer_id"],
        modalidad=modalidad_normalizada,
        request=body,
        cotizaciones=ordenar_cotizaciones_por_preferencia(cotizaciones),
    )



def normalizar_evento_tracking(raw):
    raw = raw or {}
    return {
        "evento": raw.get("event") or raw.get("status") or "",
        "fecha": raw.get("date") or "",
        "sucursal": raw.get("branch") or "",
        "estado": raw.get("status") or "",
        "firma": raw.get("sign") or "",
        "raw": raw,
    }


def _eventos_desde_tracking_response(data):
    if isinstance(data, list):
        envios = data
    elif isinstance(data, dict) and isinstance(data.get("events"), list):
        envios = [data]
    else:
        envios = []

    eventos = []
    tracking_number = ""

    for envio in envios:
        if not isinstance(envio, dict):
            continue
        tracking_number = tracking_number or str(envio.get("trackingNumber") or "")
        for evento in envio.get("events") or []:
            if isinstance(evento, dict):
                eventos.append(normalizar_evento_tracking(evento))

    return tracking_number, eventos


def consultar_tracking_envio(shipping_id, config=None, token=None):
    """Consulta tracking MiCorreo por shippingId.

    APB:
    - No crea envíos.
    - No paga.
    - No imprime etiquetas.
    - Usa /shipping/tracking, documentado para órdenes importadas a MiCorreo.
    """
    cfg = config or cargar_config_desde_env()

    if not funcion_habilitada("tracking", cfg):
        return _error("Función tracking MiCorreo deshabilitada.")

    shipping = str(shipping_id or "").strip()
    if not shipping:
        return _error("Falta shippingId para consultar tracking MiCorreo.")

    token_real = token
    if not token_real:
        token_result = obtener_token(cfg)
        if not token_result.get("ok"):
            return token_result
        token_real = token_result["token"]

    status, data = _request_json(
        "GET",
        "/shipping/tracking",
        cfg,
        token=token_real,
        body={"shippingId": shipping},
    )

    if not (status and 200 <= status < 300):
        return _error(
            "No se pudo consultar tracking MiCorreo.",
            status=status,
            respuesta=data,
            shipping_id=shipping,
        )

    if isinstance(data, dict) and data.get("error"):
        return _error(
            data.get("error") or "MiCorreo no devolvió tracking válido.",
            status=status,
            respuesta=data,
            shipping_id=shipping,
        )

    tracking_number, eventos = _eventos_desde_tracking_response(data)
    ultimo_evento = eventos[0] if eventos else {}
    estado = ultimo_evento.get("evento") or ultimo_evento.get("estado") or ""

    return _ok(
        status=status,
        shipping_id=shipping,
        tracking_number=tracking_number or shipping,
        estado=estado,
        ultimo_evento=ultimo_evento,
        eventos=eventos,
        respuesta=data,
    )



def _accion_no_ejecutada(nombre, mensaje, config=None):
    cfg = config or cargar_config_desde_env()
    return _error(
        mensaje,
        accion=nombre,
        ejecutado=False,
        accion_peligrosa=True,
        capacidades=obtener_capacidades(cfg).get("funciones", {}),
    )


def importar_envio(payload=None, config=None, token=None):
    """Placeholder seguro para /shipping/import.

    APB:
    - No crea envíos desde Sistema Fierro.
    - No ejecuta llamadas externas.
    - Queda bloqueado hasta confirmar flujo, impacto operativo y ambiente seguro.
    """
    cfg = config or cargar_config_desde_env()

    if not funcion_habilitada("importacion_envios", cfg):
        return _accion_no_ejecutada(
            "importacion_envios",
            "Importación de envíos MiCorreo deshabilitada.",
            config=cfg,
        )

    return _accion_no_ejecutada(
        "importacion_envios",
        "Importación de envíos MiCorreo no implementada por seguridad.",
        config=cfg,
    )


def obtener_etiqueta_envio(shipping_id=None, config=None, token=None):
    """Placeholder seguro para etiquetas.

    La integración básica queda sin impresión de etiquetas desde el sistema.
    """
    cfg = config or cargar_config_desde_env()

    if not funcion_habilitada("etiquetas", cfg):
        return _accion_no_ejecutada(
            "etiquetas",
            "Etiquetas MiCorreo deshabilitadas.",
            config=cfg,
        )

    return _accion_no_ejecutada(
        "etiquetas",
        "Etiquetas MiCorreo no implementadas por seguridad.",
        config=cfg,
    )


def pagar_envio(shipping_id=None, config=None, token=None):
    """Placeholder seguro para pago.

    La integración básica no debe intentar pagar envíos desde el sistema.
    """
    cfg = config or cargar_config_desde_env()

    if not funcion_habilitada("pago", cfg):
        return _accion_no_ejecutada(
            "pago",
            "Pago MiCorreo deshabilitado.",
            config=cfg,
        )

    return _accion_no_ejecutada(
        "pago",
        "Pago MiCorreo no implementado por seguridad.",
        config=cfg,
    )
