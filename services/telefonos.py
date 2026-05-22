import re


def normalizar_telefono_service(raw):
    telefono = "" if raw is None else str(raw).strip()

    if not telefono:
        return ""

    telefono = telefono.replace("+", "")
    solo_digitos = re.sub(r"\D", "", telefono)

    if solo_digitos.startswith("549"):
        return solo_digitos

    if solo_digitos.startswith("54"):
        resto = solo_digitos[2:]
        if resto.startswith("9"):
            return "54" + resto
        return "549" + resto

    if solo_digitos.startswith("15"):
        solo_digitos = solo_digitos[2:]

    return "549" + solo_digitos