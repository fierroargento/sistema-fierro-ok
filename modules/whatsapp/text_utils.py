import re


def es_afirmativo(texto):
    texto = texto.lower().strip()
    return any(x in texto for x in [
        "si", "sí", "ok", "dale", "confirmo", "confirmado", "correcto",
        "exacto", "perfecto", "claro", "obvio", "de una", "va", "bueno",
        "está bien", "esta bien", "todo bien", "listo", "por supuesto",
    ])




def es_agradecimiento_simple(texto):
    texto = (texto or "").lower().strip()

    if not texto:
        return False

    texto_limpio = re.sub(r"[^a-záéíóúñü\s]", " ", texto)
    texto_limpio = re.sub(r"\s+", " ", texto_limpio).strip()

    agradecimientos = [
        "gracias",
        "muchas gracias",
        "ok gracias",
        "dale gracias",
        "perfecto gracias",
        "listo gracias",
        "genial gracias",
        "buenisimo gracias",
        "buenísimo gracias",
        "joya gracias",
    ]

    return texto_limpio in agradecimientos

def es_negativo(texto):
    texto = texto.lower().strip()
    return any(x in texto for x in [
        "no", "nope", "negativo", "no gracias", "no me interesa", "no quiero",
        "paso", "por ahora no", "solo domicilio", "prefiero domicilio", "a domicilio",
    ])


def pregunta_precio(texto):
    texto = texto.lower().strip()
    return any(x in texto for x in ["cuanto", "cuánto", "precio", "sale", "cuesta", "valor", "costo", "plata"])


def pregunta_cantidad(texto):
    numeros = re.findall(r"\b([1-9][0-9]?)\b", texto)
    return int(numeros[0]) if numeros else None


def es_queja_o_problema(texto):
    texto = texto.lower()
    return any(x in texto for x in [
        "reclamo", "queja", "problema", "no llegó", "no llego", "no recibi",
        "no recibí", "cancelar", "cancelación", "devolucion", "devolución",
        "estafa", "mentira", "mal", "roto", "defecto", "incompleto",
        "no funciona", "tarde", "demora", "donde esta", "dónde está",
    ])


def es_consulta_factura(texto):
    t = texto.lower()
    return any(x in t for x in ["factura", "facturacion", "facturación", "factura a", "factura b"])


def requiere_factura_distinta(texto):
    t = texto.lower()
    return any(x in t for x in [
        "otros datos", "otro dato", "otra razon", "otra razón", "razon social", "razón social",
        "otro cuit", "cuit distinto", "a nombre de", "datos distintos", "cambiar datos",
        "no son esos", "con estos datos", "te paso los datos",
    ])
