"""
modules.bot_ml.billing
----------------------
Extraccion y normalizacion de datos de facturacion/comprador de Mercado Libre.

APB / SaaS:
- No hace llamadas HTTP.
- No escribe DB.
- No depende de Flask ni app.py.
- Recibe diccionarios de ML y devuelve datos normalizados.
"""

import re

from services.telefonos import normalizar_telefono_service


def buscar_valor_recursivo(data, claves):
    if not isinstance(claves, (list, tuple, set)):
        claves = [claves]

    claves_normalizadas = {str(c).lower().strip() for c in claves}

    if isinstance(data, dict):
        for key, value in data.items():
            if str(key).lower().strip() in claves_normalizadas and value not in [None, ""]:
                return value

        for value in data.values():
            encontrado = buscar_valor_recursivo(value, claves_normalizadas)
            if encontrado not in [None, ""]:
                return encontrado

    if isinstance(data, list):
        for item in data:
            encontrado = buscar_valor_recursivo(item, claves_normalizadas)
            if encontrado not in [None, ""]:
                return encontrado

    return ""


def ml_billing_base(billing_info):
    """Devuelve el bloque real buyer.billing_info cuando ML responde V2."""
    if not isinstance(billing_info, dict):
        return {}

    buyer = billing_info.get("buyer") or {}
    if isinstance(buyer, dict):
        info = buyer.get("billing_info") or {}
        if isinstance(info, dict) and info:
            return info

    info = billing_info.get("billing_info") or {}
    if isinstance(info, dict) and info:
        return info

    return billing_info


def ml_billing_additional_info_map(billing_info):
    info = ml_billing_base(billing_info)
    adicionales = info.get("additional_info") or billing_info.get("additional_info") or []
    salida = {}

    if isinstance(adicionales, list):
        for item in adicionales:
            if not isinstance(item, dict):
                continue

            tipo = str(
                item.get("type") or item.get("key") or item.get("name") or ""
            ).lower().strip()
            valor = item.get("value")

            if tipo and valor not in [None, ""]:
                salida[tipo] = valor

    return salida


def ml_extraer_documento_billing(billing_info):
    info = ml_billing_base(billing_info)
    adicionales = ml_billing_additional_info_map(billing_info)

    identificacion = info.get("identification") or {}
    atributos = info.get("attributes") or {}

    candidatos = [
        identificacion.get("number") if isinstance(identificacion, dict) else "",
        adicionales.get("doc_number"),
        adicionales.get("secondary_doc_number"),
        atributos.get("doc_type_number") if isinstance(atributos, dict) else "",
        info.get("doc_number"),
        info.get("document_number"),
        info.get("dni"),
        info.get("cuit"),
        buscar_valor_recursivo(info.get("identification") or {}, ["number"]),
    ]

    for candidato in candidatos:
        valor = re.sub(r"\D", "", str(candidato or ""))
        if valor and valor not in [
            "0",
            "00",
            "00000000",
            "000000000",
            "0000000000",
            "00000000000",
        ]:
            return valor

    return ""


def ml_extraer_nombre_billing(billing_info):
    info = ml_billing_base(billing_info)
    adicionales = ml_billing_additional_info_map(billing_info)

    business_name = str(
        info.get("business_name") or adicionales.get("business_name") or ""
    ).strip()
    if business_name:
        return business_name

    nombre = str(info.get("name") or adicionales.get("first_name") or "").strip()
    apellido = str(info.get("last_name") or adicionales.get("last_name") or "").strip()

    nombre_completo = f"{nombre} {apellido}".strip()
    if nombre_completo and not nombre_completo.isdigit():
        return nombre_completo

    for clave in ["full_name", "legal_name"]:
        valor = str(info.get(clave) or adicionales.get(clave) or "").strip()
        if valor and not valor.isdigit():
            return valor

    return ""


def ml_extraer_direccion_billing(billing_info):
    info = ml_billing_base(billing_info)
    adicionales = ml_billing_additional_info_map(billing_info)

    address = info.get("address") or {}
    if not isinstance(address, dict):
        address = {}

    estado = address.get("state") or {}
    if not isinstance(estado, dict):
        estado = {}

    calle = str(address.get("street_name") or adicionales.get("street_name") or "").strip()
    numero = str(address.get("street_number") or adicionales.get("street_number") or "").strip()
    comentario = str(address.get("comment") or adicionales.get("comment") or "").strip()
    ciudad = str(address.get("city_name") or adicionales.get("city_name") or "").strip()
    provincia = str(
        estado.get("name") or address.get("state_name") or adicionales.get("state_name") or ""
    ).strip()
    cp = str(address.get("zip_code") or adicionales.get("zip_code") or "").strip()

    direccion = ""
    if calle and numero:
        direccion = f"{calle} {numero}".strip()
    elif calle:
        direccion = calle

    partes = [direccion, comentario, ciudad, provincia, cp]
    salida = []

    for valor in partes:
        valor = str(valor or "").strip()
        if valor and valor not in salida:
            salida.append(valor)

    return ", ".join(salida).strip()


def ml_extraer_telefono(order, shipment):
    buyer = order.get("buyer") or {}
    phone = buyer.get("phone") or {}
    receiver_address = (shipment or {}).get("receiver_address") or {}

    candidatos = []

    area = str(phone.get("area_code") or "").strip()
    number = str(phone.get("number") or "").strip()
    if area or number:
        candidatos.append(f"{area}{number}")

    candidatos.extend([
        phone.get("extension"),
        receiver_address.get("receiver_phone"),
        receiver_address.get("phone"),
        shipment.get("receiver_phone") if isinstance(shipment, dict) else "",
    ])

    for candidato in candidatos:
        normalizado = normalizar_telefono_service(candidato)
        digitos = re.sub(r"\D", "", normalizado or "")

        if (
            digitos
            and digitos not in ["5490", "54900", "54900000000", "5490000000000"]
            and len(digitos) >= 10
        ):
            return normalizado

    return ""


def ml_buyer_tiene_nombre_real(order):
    buyer = order.get("buyer") or {}
    first = str(buyer.get("first_name") or "").strip()
    last = str(buyer.get("last_name") or "").strip()

    return bool(first and last)


def parece_nickname_ml(nombre, nickname=""):
    nombre = str(nombre or "").strip()
    nickname = str(nickname or "").strip()

    if not nombre:
        return True

    if nombre.lower() in ["cliente mercado libre", "cliente ml", "mercado libre"]:
        return True

    if nickname and nombre.lower() == nickname.lower():
        return True

    if " " not in nombre and re.search(r"\d", nombre):
        return True

    if " " not in nombre and nombre.upper() == nombre and len(nombre) >= 5:
        return True

    return False