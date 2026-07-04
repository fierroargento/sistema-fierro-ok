import re


def es_afirmativo(texto):
    texto = texto.lower().strip()
    return any(x in texto for x in [
        "si", "sí", "ok", "dale", "confirmo", "confirmado", "correcto",
        "exacto", "perfecto", "claro", "obvio", "de una", "va", "bueno",
        "está bien", "esta bien", "todo bien", "listo", "por supuesto",
        "me queda bien", "le queda bien", "queda bien",
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


def _normalizar_cierre_simple_wa(texto):
    import unicodedata

    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9ñ\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def es_cierre_simple_retiro_post_aviso(texto):
    """
    Detecta respuestas simples luego del aviso de listo para retirar.

    Ejemplos:
    - "Bueno gracias, ahí voy a buscarlo"
    - "Ok gracias, paso a retirar"
    - "Dale gracias, lo retiro mañana"

    No aplica si hay problema, reclamo o consulta.
    """
    texto_norm = _normalizar_cierre_simple_wa(texto)

    if not texto_norm:
        return False

    palabras_problema = [
        "pero",
        "problema",
        "reclamo",
        "queja",
        "no puedo",
        "no llego",
        "no esta",
        "no aparece",
        "demora",
        "cancelar",
        "devolucion",
        "roto",
        "mal",
        "equivocado",
        "equivocada",
        "me cobran",
        "cobrar",
        "direccion",
        "cambiar",
        "cambio",
    ]

    if any(palabra in texto_norm for palabra in palabras_problema):
        return False

    cierres = [
        "gracias",
        "ok",
        "dale",
        "bueno",
        "perfecto",
        "genial",
        "joya",
        "listo",
        "buenisimo",
    ]

    retiro = [
        "ahi voy",
        "voy a buscar",
        "voy a retir",
        "paso a buscar",
        "paso a retir",
        "lo busco",
        "lo retiro",
        "voy manana",
        "manana paso",
        "paso manana",
        "retiro manana",
    ]

    if any(cierre in texto_norm for cierre in cierres) and any(frase in texto_norm for frase in retiro):
        return True

    # También permitimos agradecimientos puros y cortos en este estado.
    if es_agradecimiento_simple(texto_norm):
        return True

    return False
