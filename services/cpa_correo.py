"""
services/cpa_correo.py

Integración APB con el endpoint usado por la web de Correo Argentino
para localidades y CPA.

Estrategia:
- Usar localidades descargadas localmente cuando existan.
- Consultar Correo solo si está habilitado por env.
- Consultar CPA solo de forma puntual.
- Cachear CPA consultados.
- No bloquear el flujo si falla.
"""

import json
import os
import re
import unicodedata
from functools import lru_cache
from html import unescape
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


CORREO_CPA_ENDPOINT = (
    "https://www.correoargentino.com.ar/sites/all/modules/custom/ca_forms/api/wsFacade.php"
)

DATA_DIR = Path("data")
LOCALIDADES_DIR = DATA_DIR / "correo_localidades"
CPA_CACHE_PATH = DATA_DIR / "cpa_cache_correo.json"

CORREO_TIMEOUT = float(os.getenv("CORREO_CPA_TIMEOUT", "4") or 4)


PROVINCIA_CODIGO_CORREO = {
    "buenos aires": "B",
    "provincia de buenos aires": "B",
    "caba": "C",
    "capital federal": "C",
    "ciudad autonoma de buenos aires": "C",
    "ciudad autónoma de buenos aires": "C",
    "catamarca": "K",
    "chaco": "H",
    "chubut": "U",
    "cordoba": "X",
    "córdoba": "X",
    "corrientes": "W",
    "entre rios": "E",
    "entre ríos": "E",
    "formosa": "P",
    "jujuy": "Y",
    "la pampa": "L",
    "la rioja": "F",
    "mendoza": "M",
    "misiones": "N",
    "neuquen": "Q",
    "neuquén": "Q",
    "rio negro": "R",
    "río negro": "R",
    "salta": "A",
    "san juan": "J",
    "san luis": "D",
    "santa cruz": "Z",
    "santa fe": "S",
    "santiago del estero": "G",
    "tierra del fuego": "V",
    "tucuman": "T",
    "tucumán": "T",
}


PROVINCIA_NOMBRE_POR_CODIGO = {
    "B": "Buenos Aires",
    "C": "CABA",
    "K": "Catamarca",
    "H": "Chaco",
    "U": "Chubut",
    "X": "Córdoba",
    "W": "Corrientes",
    "E": "Entre Ríos",
    "P": "Formosa",
    "Y": "Jujuy",
    "L": "La Pampa",
    "F": "La Rioja",
    "M": "Mendoza",
    "N": "Misiones",
    "Q": "Neuquén",
    "R": "Río Negro",
    "A": "Salta",
    "J": "San Juan",
    "D": "San Luis",
    "Z": "Santa Cruz",
    "S": "Santa Fe",
    "G": "Santiago del Estero",
    "V": "Tierra del Fuego",
    "T": "Tucumán",
}


def correo_cpa_habilitado():
    """
    Habilita llamadas en vivo al endpoint de Correo.

    APB:
    Por defecto está apagado. El sistema debe funcionar con cache/base local.
    """
    return str(os.getenv("CORREO_CPA_ENABLED", "false")).strip().lower() in (
        "1",
        "true",
        "yes",
        "si",
        "sí",
    )


def normalizar_texto(valor):
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(ch for ch in texto if unicodedata.category(ch) != "Mn")
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    texto = " ".join(texto.split())
    return texto


def normalizar_cp(cp):
    cp = "".join(ch for ch in str(cp or "") if ch.isdigit())
    return cp if len(cp) == 4 else ""


def codigo_provincia_correo(provincia):
    prov_norm = normalizar_texto(provincia)
    return PROVINCIA_CODIGO_CORREO.get(prov_norm, "")


def _post_correo(payload, accept="application/json, text/javascript, */*; q=0.01"):
    data = urlencode(payload).encode("utf-8")

    req = Request(
        CORREO_CPA_ENDPOINT,
        data=data,
        headers={
            "accept": accept,
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://www.correoargentino.com.ar",
            "referer": "https://www.correoargentino.com.ar/",
            "x-requested-with": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 SistemaFierro/1.0",
        },
        method="POST",
    )

    with urlopen(req, timeout=CORREO_TIMEOUT) as resp:
        raw = resp.read()

    return raw.decode("utf-8-sig", errors="replace")


def _normalizar_localidad_item(item, provincia_codigo=""):
    if not isinstance(item, dict):
        return None

    cp = normalizar_cp(item.get("cp"))

    salida = {
        "id": item.get("id"),
        "nombre": str(item.get("nombre") or "").strip(),
        "partido": str(item.get("partido") or "").strip(),
        "municipio": str(item.get("municipio") or "").strip(),
        "cp": cp,
        "latitud": item.get("latitud"),
        "longitud": item.get("longitud"),
        "provincia_codigo": str(provincia_codigo or "").strip().upper(),
        "provincia": PROVINCIA_NOMBRE_POR_CODIGO.get(
            str(provincia_codigo or "").strip().upper(),
            "",
        ),
    }

    if not salida["nombre"]:
        return None

    return salida


def _path_localidades(provincia_codigo):
    provincia_codigo = str(provincia_codigo or "").strip().upper()
    return LOCALIDADES_DIR / f"{provincia_codigo}.json"


def _leer_json(path, default):
    try:
        if not Path(path).exists():
            return default

        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    except Exception:
        return default


def _escribir_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@lru_cache(maxsize=64)
def listar_localidades_locales(provincia_codigo):
    """
    Lee localidades previamente descargadas:
    data/correo_localidades/H.json
    """
    provincia_codigo = str(provincia_codigo or "").strip().upper()

    if not provincia_codigo:
        return []

    data = _leer_json(_path_localidades(provincia_codigo), [])

    if not isinstance(data, list):
        return []

    salida = []

    for item in data:
        normalizado = _normalizar_localidad_item(item, provincia_codigo)
        if normalizado:
            salida.append(normalizado)

    return salida


def descargar_localidades_correo(provincia_codigo):
    """
    Consulta Correo en vivo y devuelve localidades.

    No depende de cookies.
    """
    provincia_codigo = str(provincia_codigo or "").strip().upper()

    if not provincia_codigo:
        return []

    texto = _post_correo({
        "action": "localidades",
        "localidad": "none",
        "calle": "",
        "altura": "",
        "provincia": provincia_codigo,
    })

    try:
        data = json.loads(texto)
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    salida = []

    for item in data:
        normalizado = _normalizar_localidad_item(item, provincia_codigo)
        if normalizado:
            salida.append(normalizado)

    return salida


def guardar_localidades_correo(provincia_codigo, localidades):
    provincia_codigo = str(provincia_codigo or "").strip().upper()

    if not provincia_codigo:
        return False

    _escribir_json(_path_localidades(provincia_codigo), localidades or [])
    listar_localidades_locales.cache_clear()
    listar_localidades_correo.cache_clear()
    return True


@lru_cache(maxsize=64)
def listar_localidades_correo(provincia_codigo):
    """
    Fuente principal:
    1. Local descargado.
    2. Si no hay local y CORREO_CPA_ENABLED=true, consulta en vivo.
    """
    provincia_codigo = str(provincia_codigo or "").strip().upper()

    if not provincia_codigo:
        return []

    locales = listar_localidades_locales(provincia_codigo)

    if locales:
        return locales

    if not correo_cpa_habilitado():
        return []

    try:
        en_vivo = descargar_localidades_correo(provincia_codigo)

        if en_vivo:
            guardar_localidades_correo(provincia_codigo, en_vivo)
            return en_vivo

    except Exception as e:
        print(f"[CPA CORREO] No se pudieron descargar localidades {provincia_codigo}: {e}")

    return []


def buscar_localidad_correo(provincia, localidad="", cp=""):
    """
    Busca localidad de forma conservadora.

    Reglas:
    - si hay localidad textual, prefiere coincidencia exacta normalizada;
    - si hay CP, filtra por CP;
    - si queda una sola, devuelve;
    - si hay varias, no inventa.
    """
    provincia_codigo = codigo_provincia_correo(provincia)

    if not provincia_codigo:
        return None

    localidades = listar_localidades_correo(provincia_codigo)

    if not localidades:
        return None

    loc_norm = normalizar_texto(localidad)
    cp_norm = normalizar_cp(cp)

    candidatas = localidades

    if loc_norm:
        exactas = [
            item for item in candidatas
            if normalizar_texto(item.get("nombre")) == loc_norm
        ]

        if exactas:
            candidatas = exactas
        else:
            contiene = [
                item for item in candidatas
                if loc_norm in normalizar_texto(item.get("nombre"))
                or normalizar_texto(item.get("nombre")) in loc_norm
            ]

            if contiene:
                candidatas = contiene

    if cp_norm:
        por_cp = [
            item for item in candidatas
            if normalizar_cp(item.get("cp")) == cp_norm
        ]

        if por_cp:
            candidatas = por_cp

    unicas = []
    vistos = set()

    for item in candidatas:
        item_id = str(item.get("id") or "")
        if not item_id:
            continue

        if item_id in vistos:
            continue

        vistos.add(item_id)
        unicas.append(item)

    if len(unicas) == 1:
        item = dict(unicas[0])
        item["fuente"] = "correo_localidades"
        item["confianza"] = "alta"
        return item

    return None


def buscar_localidad_correo_por_cp(provincia, cp):
    """
    Busca por provincia + CP.

    Solo devuelve si hay una coincidencia única.
    """
    provincia_codigo = codigo_provincia_correo(provincia)

    if not provincia_codigo:
        return None

    cp_norm = normalizar_cp(cp)

    if not cp_norm:
        return None

    localidades = listar_localidades_correo(provincia_codigo)

    candidatas = [
        item for item in localidades
        if normalizar_cp(item.get("cp")) == cp_norm
    ]

    unicas = []
    vistos = set()

    for item in candidatas:
        clave = (
            str(item.get("id") or ""),
            normalizar_texto(item.get("nombre")),
            normalizar_cp(item.get("cp")),
        )

        if clave in vistos:
            continue

        vistos.add(clave)
        unicas.append(item)

    if len(unicas) == 1:
        item = dict(unicas[0])
        item["fuente"] = "correo_localidades"
        item["confianza"] = "alta"
        return item

    return None


def _leer_cache_cpa():
    data = _leer_json(CPA_CACHE_PATH, {})

    if isinstance(data, dict):
        return data

    return {}


def _guardar_cache_cpa(data):
    if not isinstance(data, dict):
        data = {}

    _escribir_json(CPA_CACHE_PATH, data)


def _clave_cache_cpa(provincia_codigo, localidad_id, calle, altura):
    return "|".join([
        str(provincia_codigo or "").strip().upper(),
        str(localidad_id or "").strip(),
        normalizar_texto(calle),
        str(altura or "").strip(),
    ])


def consultar_cpa_correo_por_id(provincia_codigo, localidad_id, calle, altura):
    """
    Consulta CPA usando localidad_id de Correo.

    Respuesta esperada:
    <h1>CALLE JULIO ACERBONI 4672<span id="ncpa"> B1666ANT</span></h1>
    """
    provincia_codigo = str(provincia_codigo or "").strip().upper()
    localidad_id = str(localidad_id or "").strip()
    calle = str(calle or "").strip()
    altura = str(altura or "").strip()

    if not provincia_codigo or not localidad_id or not calle or not altura:
        return None

    cache = _leer_cache_cpa()
    clave = _clave_cache_cpa(provincia_codigo, localidad_id, calle, altura)

    if clave in cache and isinstance(cache[clave], dict):
        item = dict(cache[clave])
        item["fuente"] = item.get("fuente") or "correo_cpa_cache"
        item["confianza"] = item.get("confianza") or "alta"
        return item

    if not correo_cpa_habilitado():
        return None

    texto = _post_correo(
        {
            "action": "cpa",
            "localidad": localidad_id,
            "calle": calle,
            "altura": altura,
            "provincia": provincia_codigo,
        },
        accept="text/html, */*; q=0.01",
    )

    texto = unescape(texto or "")

    m = re.search(
        r'id=["\']ncpa["\'][^>]*>\s*([^<]+)\s*<',
        texto,
        flags=re.IGNORECASE,
    )

    if not m:
        return None

    cpa = str(m.group(1) or "").strip().upper()

    if not re.fullmatch(r"[A-Z]\d{4}[A-Z]{3}", cpa):
        return None

    normalizada = re.sub(r"<[^>]+>", " ", texto)
    normalizada = " ".join(unescape(normalizada).split())

    resultado = {
        "cpa": cpa,
        "direccion_normalizada": normalizada[:300],
        "fuente": "correo_cpa",
        "confianza": "alta",
    }

    cache[clave] = resultado
    _guardar_cache_cpa(cache)

    return dict(resultado)


def resolver_cpa_correo(provincia, localidad, calle, altura, cp=""):
    """
    Resuelve CPA completo a partir de datos del pedido.
    """
    loc = buscar_localidad_correo(
        provincia=provincia,
        localidad=localidad,
        cp=cp,
    )

    if not loc:
        return None

    resultado = consultar_cpa_correo_por_id(
        provincia_codigo=loc.get("provincia_codigo"),
        localidad_id=loc.get("id"),
        calle=calle,
        altura=altura,
    )

    if not resultado:
        return None

    resultado["localidad_id"] = loc.get("id")
    resultado["localidad"] = loc.get("nombre")
    resultado["cp"] = loc.get("cp")
    resultado["latitud"] = loc.get("latitud")
    resultado["longitud"] = loc.get("longitud")

    return resultado


def resolver_ubicacion_correo(provincia, localidad="", cp=""):
    """
    Resuelve localidad/CP/coordenadas desde base local Correo.

    No requiere consultar CPA.
    """
    loc = buscar_localidad_correo(
        provincia=provincia,
        localidad=localidad,
        cp=cp,
    )

    if not loc and cp:
        loc = buscar_localidad_correo_por_cp(
            provincia=provincia,
            cp=cp,
        )

    if not loc:
        return None

    return {
        "codigo_postal": loc.get("cp") or normalizar_cp(cp),
        "localidad": loc.get("nombre") or localidad,
        "provincia": loc.get("provincia") or str(provincia or "").strip(),
        "latitud": loc.get("latitud"),
        "longitud": loc.get("longitud"),
        "fuente": "correo_localidades",
        "confianza": loc.get("confianza") or "alta",
        "localidad_id": loc.get("id"),
    }