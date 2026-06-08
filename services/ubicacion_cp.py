"""
services/ubicacion_cp.py

Normalización postal y ubicación de pedidos.

Objetivo SaaS/CRM:
- Mantener la lógica fuera de app.py.
- Permitir varias fuentes:
  1. JSON local propio.
  2. Localidades descargadas de Correo.
  3. Correo CPA puntual con cache.
  4. Fallback Vía Cargo.
- No inventar datos si hay ambigüedad.
- No bloquear el flujo si falla una fuente externa.
"""

import json
import os
import re
import unicodedata


def _normalizar_cp(cp):
    cp = str(cp or "").strip()
    cp = "".join(ch for ch in cp if ch.isdigit())
    return cp if len(cp) == 4 else ""


def _normalizar_texto(valor):
    return str(valor or "").strip()


def _norm(valor):
    valor = str(valor or "").strip().lower()
    valor = unicodedata.normalize("NFD", valor)
    valor = "".join(ch for ch in valor if unicodedata.category(ch) != "Mn")
    valor = re.sub(r"[^a-z0-9\s]", " ", valor)
    return " ".join(valor.split())


def _cargar_json_seguro(path):
    try:
        if not os.path.exists(path):
            return None

        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        return data

    except Exception:
        return None


def _resolver_desde_codigos_postales_ar(cp):
    data = _cargar_json_seguro(os.path.join("data", "codigos_postales_ar.json"))

    if not isinstance(data, list):
        return None

    coincidencias = []

    for item in data:
        if not isinstance(item, dict):
            continue

        item_cp = _normalizar_cp(
            item.get("cp")
            or item.get("codigo_postal")
            or item.get("codigoPostal")
            or item.get("postal_code")
        )

        if item_cp != cp:
            continue

        localidad = _normalizar_texto(
            item.get("localidad")
            or item.get("locality")
            or item.get("ciudad")
            or item.get("city")
        )

        provincia = _normalizar_texto(
            item.get("provincia")
            or item.get("province")
            or item.get("state")
        )

        latitud = item.get("latitud") or item.get("lat") or item.get("latitude")
        longitud = item.get("longitud") or item.get("lng") or item.get("lon") or item.get("longitude")

        if localidad or provincia:
            coincidencias.append({
                "codigo_postal": cp,
                "localidad": localidad,
                "provincia": provincia,
                "latitud": latitud,
                "longitud": longitud,
                "fuente": "codigos_postales_ar",
                "confianza": "media",
            })

    return _resultado_unico_ubicacion(coincidencias)


def _resolver_desde_via_cargo_sucursales(cp):
    """
    Fallback:
    usa via_cargo_sucursales.json si existe.

    Esta fuente representa sucursales, no una base completa de CP argentinos.
    Solo se usa si el CP tiene una única localidad/provincia asociada.
    """
    data = _cargar_json_seguro("via_cargo_sucursales.json")

    if not isinstance(data, list):
        return None

    coincidencias = []

    for item in data:
        if not isinstance(item, dict):
            continue

        item_cp = _normalizar_cp(
            item.get("cp")
            or item.get("codigo_postal")
            or item.get("codigoPostal")
            or item.get("postal_code")
        )

        if item_cp != cp:
            continue

        localidad = _normalizar_texto(
            item.get("localidad")
            or item.get("locality")
            or item.get("ciudad")
            or item.get("city")
        )

        provincia = _normalizar_texto(
            item.get("provincia")
            or item.get("province")
            or item.get("state")
        )

        latitud = item.get("latitud") or item.get("lat") or item.get("latitude")
        longitud = item.get("longitud") or item.get("lng") or item.get("lon") or item.get("longitude")

        if localidad or provincia:
            coincidencias.append({
                "codigo_postal": cp,
                "localidad": localidad,
                "provincia": provincia,
                "latitud": latitud,
                "longitud": longitud,
                "fuente": "via_cargo_sucursales",
                "confianza": "baja",
            })

    return _resultado_unico_ubicacion(coincidencias)


def _resultado_unico_ubicacion(coincidencias):
    if not coincidencias:
        return None

    coincidencias_unicas = []
    vistos = set()

    for item in coincidencias:
        clave = (
            _norm(item.get("localidad")),
            _norm(item.get("provincia")),
            _normalizar_cp(item.get("codigo_postal") or item.get("cp")),
        )

        if clave in vistos:
            continue

        vistos.add(clave)
        coincidencias_unicas.append(item)

    if len(coincidencias_unicas) == 1:
        return coincidencias_unicas[0]

    return None


def resolver_ubicacion_por_cp(cp, provincia="", localidad=""):
    """
    Resuelve localidad/provincia/coordenadas por CP.

    Orden:
    1. JSON local propio.
    2. Localidades Correo descargadas.
    3. Fallback Vía Cargo.
    """
    cp = _normalizar_cp(cp)

    if not cp:
        return None

    resultado = _resolver_desde_codigos_postales_ar(cp)
    if resultado:
        return resultado

    try:
        from services.cpa_correo import resolver_ubicacion_correo

        resultado = resolver_ubicacion_correo(
            provincia=provincia,
            localidad=localidad,
            cp=cp,
        )

        if resultado:
            return resultado

    except Exception as e:
        print(f"[UBICACION CORREO] No se pudo resolver por CP: {e}")

    resultado = _resolver_desde_via_cargo_sucursales(cp)
    if resultado:
        return resultado

    return None

def limpiar_localidad_detectada(localidad, texto_cliente=""):
    """
    APB / Sistema Fierro:
    Valida una localidad detectada por IA o parser clásico antes de guardarla
    en el pedido.

    Motivo:
    En mensajes compactos de ML, la IA o el parser pueden confundir restos de
    dirección/etiquetas con localidad.

    Ejemplo real que NO debe guardarse:
    - "de Mayo 670 Teléfono"

    Regla:
    - Esta función solo valida localidades detectadas desde texto libre.
    - No se usa para localidades confiables provenientes de fuentes estructuradas
      como Correo, Vía Cargo o sucursales ya elegidas.
    - app.py debe usar esta función como compuerta antes de asignar
      pedido.localidad desde datos detectados.
    """
    localidad = _normalizar_texto(localidad)

    if not localidad:
        return ""

    localidad_norm = _norm(localidad)

    if not localidad_norm:
        return ""

    # Etiquetas/campos que indican que el texto no es una localidad sino
    # un resto del mensaje del cliente.
    if re.search(
        r"\b("
        r"tel|telefono|telefonos|teléfono|teléfonos|cel|celular|whatsapp|"
        r"dni|documento|doc|cuit|cuil|"
        r"cp|codigo postal|código postal|postal|"
        r"direccion|dirección|dir|calle|altura|"
        r"mail|email|correo"
        r")\b",
        localidad_norm,
        flags=re.IGNORECASE,
    ):
        return ""

    # Si contiene un número de 3 o más cifras, muy probablemente es resto
    # de dirección o teléfono, no localidad.
    # Permite localidades reales como "25 de Mayo" o "9 de Julio".
    if re.search(r"\b\d{3,}\b", localidad_norm):
        return ""

    # Si es demasiado larga para localidad detectada desde IA/parser,
    # preferimos no guardar antes que contaminar el pedido.
    if len(localidad_norm) > 60:
        return ""

    # Si contiene muchas palabras, suele ser texto arrastrado del mensaje.
    # Localidades compuestas existen, pero más de 5 palabras desde texto libre
    # es riesgoso.
    if len(localidad_norm.split()) > 5:
        return ""

    return localidad


def extraer_calle_altura(direccion):
    """
    Intenta separar calle y altura desde una dirección textual.

    - "French 123" -> ("French", "123")
    - "Av. San Martín 1450" -> ("Av. San Martín", "1450")
    - "French s/n" -> ("French", "")
    - "Ruta 3 km 960" -> ("Ruta 3 km 960", "")
    """
    texto = str(direccion or "").strip()

    if not texto:
        return "", ""

    texto = " ".join(texto.split())

    if re.search(r"\b(s/n|sn|sin numero|sin número)\b", texto, flags=re.IGNORECASE):
        calle = re.sub(
            r"\b(s/n|sn|sin numero|sin número)\b",
            "",
            texto,
            flags=re.IGNORECASE,
        ).strip(" ,.-")
        return calle, ""

    if re.search(r"\b(ruta|km|kilometro|kilómetro)\b", texto, flags=re.IGNORECASE):
        return texto, ""

    candidatos = list(re.finditer(r"\b\d{1,5}\b", texto))

    if not candidatos:
        return texto, ""

    ultimo = candidatos[-1]
    altura = ultimo.group(0)

    calle = texto[:ultimo.start()].strip(" ,.-")
    resto = texto[ultimo.end():].strip(" ,.-")

    if resto and len(resto.split()) > 3:
        return texto, ""

    if not calle:
        return texto, ""

    return calle, altura


def _resolver_cpa_desde_json_local(provincia, localidad, calle, altura):
    """
    Fuente local futura:
    data/cpa_ar.json
    """
    provincia_n = _norm(provincia)
    localidad_n = _norm(localidad)
    calle_n = _norm(calle)

    try:
        altura_int = int(str(altura or "").strip())
    except Exception:
        altura_int = None

    if not provincia_n or not localidad_n or not calle_n or altura_int is None:
        return None

    data = _cargar_json_seguro(os.path.join("data", "cpa_ar.json"))

    if not isinstance(data, list):
        return None

    coincidencias = []

    for item in data:
        if not isinstance(item, dict):
            continue

        if _norm(item.get("provincia")) != provincia_n:
            continue

        if _norm(item.get("localidad")) != localidad_n:
            continue

        if _norm(item.get("calle")) != calle_n:
            continue

        try:
            desde = int(item.get("desde") or 0)
            hasta = int(item.get("hasta") or 999999)
        except Exception:
            continue

        if not (desde <= altura_int <= hasta):
            continue

        paridad = _norm(item.get("paridad") or "ambos")

        if paridad in ("par", "pares") and altura_int % 2 != 0:
            continue

        if paridad in ("impar", "impares") and altura_int % 2 == 0:
            continue

        cpa = str(item.get("cpa") or "").strip().upper()

        if cpa:
            coincidencias.append({
                "cpa": cpa,
                "fuente": "cpa_ar_json",
                "confianza": "alta",
            })

    cpas = []
    vistos = set()

    for item in coincidencias:
        cpa = item["cpa"]
        if cpa in vistos:
            continue
        vistos.add(cpa)
        cpas.append(item)

    if len(cpas) == 1:
        return cpas[0]

    return None


def resolver_cpa_por_direccion(provincia, localidad, calle, altura, cp=""):
    """
    Resuelve CPA alfanumérico.

    Orden:
    1. JSON local.
    2. Correo Argentino puntual con cache.
    """
    provincia = _normalizar_texto(provincia)
    localidad = _normalizar_texto(localidad)
    calle = _normalizar_texto(calle)
    altura = _normalizar_texto(altura)
    cp = _normalizar_cp(cp)

    if not provincia or not localidad or not calle or not altura:
        return None

    resultado = _resolver_cpa_desde_json_local(
        provincia=provincia,
        localidad=localidad,
        calle=calle,
        altura=altura,
    )

    if resultado:
        return resultado

    try:
        from services.cpa_correo import resolver_cpa_correo

        resultado = resolver_cpa_correo(
            provincia=provincia,
            localidad=localidad,
            calle=calle,
            altura=altura,
            cp=cp,
        )

        if resultado:
            return resultado

    except Exception as e:
        print(f"[CPA CORREO] No se pudo resolver CPA: {e}")

    return None


def _aplicar_ubicacion_a_pedido(pedido, ubicacion):
    completados = []

    if not pedido or not ubicacion:
        return completados

    localidad = _normalizar_texto(ubicacion.get("localidad"))
    provincia = _normalizar_texto(ubicacion.get("provincia"))
    codigo_postal = _normalizar_cp(ubicacion.get("codigo_postal") or ubicacion.get("cp"))

    latitud = ubicacion.get("latitud")
    longitud = ubicacion.get("longitud")
    fuente = _normalizar_texto(ubicacion.get("fuente"))
    confianza = _normalizar_texto(ubicacion.get("confianza"))

    if codigo_postal and not _normalizar_cp(getattr(pedido, "codigo_postal", "")):
        pedido.codigo_postal = codigo_postal[:10]
        completados.append("codigo_postal")

    if localidad and not _normalizar_texto(getattr(pedido, "localidad", "")):
        pedido.localidad = localidad[:100]
        completados.append("localidad")

    if provincia and not _normalizar_texto(getattr(pedido, "provincia", "")):
        pedido.provincia = provincia[:100]
        completados.append("provincia")

    if latitud and hasattr(pedido, "latitud_cliente"):
        try:
            if getattr(pedido, "latitud_cliente", None) in (None, ""):
                pedido.latitud_cliente = float(latitud)
                completados.append("latitud_cliente")
        except Exception:
            pass

    if longitud and hasattr(pedido, "longitud_cliente"):
        try:
            if getattr(pedido, "longitud_cliente", None) in (None, ""):
                pedido.longitud_cliente = float(longitud)
                completados.append("longitud_cliente")
        except Exception:
            pass

    if fuente and hasattr(pedido, "ubicacion_fuente"):
        try:
            if not _normalizar_texto(getattr(pedido, "ubicacion_fuente", "")):
                pedido.ubicacion_fuente = fuente[:50]
        except Exception:
            pass

    if confianza and hasattr(pedido, "ubicacion_confianza"):
        try:
            if not _normalizar_texto(getattr(pedido, "ubicacion_confianza", "")):
                pedido.ubicacion_confianza = confianza[:30]
        except Exception:
            pass

    return completados


def normalizar_ubicacion_pedido(pedido):
    """
    Normaliza ubicación del pedido de forma no destructiva.

    Hace:
    1. Si hay CP, intenta completar localidad/provincia/coordenadas.
    2. Si hay dirección + localidad + provincia + altura, intenta CPA.
    3. No bloquea si falla.
    """
    resultado = {
        "completados": [],
        "cpa": "",
        "fuente": "",
        "confianza": "",
    }

    if not pedido:
        return resultado

    cp = _normalizar_cp(getattr(pedido, "codigo_postal", ""))
    localidad = _normalizar_texto(getattr(pedido, "localidad", ""))
    provincia = _normalizar_texto(getattr(pedido, "provincia", ""))

    if cp:
        ubicacion = resolver_ubicacion_por_cp(
            cp=cp,
            provincia=provincia,
            localidad=localidad,
        )

        completados = _aplicar_ubicacion_a_pedido(pedido, ubicacion)

        for campo in completados:
            if campo not in resultado["completados"]:
                resultado["completados"].append(campo)

    direccion = _normalizar_texto(getattr(pedido, "direccion", ""))
    localidad = _normalizar_texto(getattr(pedido, "localidad", ""))
    provincia = _normalizar_texto(getattr(pedido, "provincia", ""))
    cp = _normalizar_cp(getattr(pedido, "codigo_postal", ""))

    calle, altura = extraer_calle_altura(direccion)

    cpa_resultado = resolver_cpa_por_direccion(
        provincia=provincia,
        localidad=localidad,
        calle=calle,
        altura=altura,
        cp=cp,
    )

    if cpa_resultado:
        cpa = str(cpa_resultado.get("cpa") or "").strip().upper()

        if cpa and hasattr(pedido, "cpa"):
            actual = _normalizar_texto(getattr(pedido, "cpa", ""))
            if not actual:
                try:
                    pedido.cpa = cpa[:20]
                    resultado["completados"].append("cpa")
                except Exception:
                    pass

        fuente = _normalizar_texto(cpa_resultado.get("fuente"))
        confianza = _normalizar_texto(cpa_resultado.get("confianza"))

        if fuente and hasattr(pedido, "ubicacion_fuente"):
            try:
                pedido.ubicacion_fuente = fuente[:50]
            except Exception:
                pass

        if confianza and hasattr(pedido, "ubicacion_confianza"):
            try:
                pedido.ubicacion_confianza = confianza[:30]
            except Exception:
                pass

        resultado["cpa"] = cpa
        resultado["fuente"] = fuente
        resultado["confianza"] = confianza

    return resultado


def autocompletar_pedido_por_cp(pedido):
    """
    Compatibilidad hacia atrás.
    """
    resultado = normalizar_ubicacion_pedido(pedido)
    return resultado.get("completados", [])