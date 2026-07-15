import re


def _quitar_15_movil_argentino(numero_nacional):
    """
    Recibe numero argentino sin 54/549 y sin 0 de larga distancia.
    Si viene con 15 despues del codigo de area, lo quita.
    """

    numero = str(numero_nacional or "")

    # Caso historico: "15..." sin codigo de area claro.
    if numero.startswith("15"):
        return numero[2:]

    # 011 15 5734 7193 -> 11 5734 7193
    # 02920 15 123456 -> 2920 123456
    for largo_area in (2, 3, 4):
        if len(numero) <= largo_area + 2:
            continue

        if numero[largo_area:largo_area + 2] != "15":
            continue

        candidato = numero[:largo_area] + numero[largo_area + 2:]

        # WhatsApp Argentina: 549 + 10 digitos nacionales.
        if len(candidato) == 10:
            return candidato

    return numero


def normalizar_telefono_service(raw):
    telefono = "" if raw is None else str(raw).strip()

    if not telefono:
        return ""

    solo_digitos = re.sub(r"\D", "", telefono)

    if not solo_digitos:
        return ""

    # 00549... / 0054...
    if solo_digitos.startswith("00"):
        solo_digitos = solo_digitos[2:]

    if solo_digitos.startswith("549"):
        numero_nacional = solo_digitos[3:]
    elif solo_digitos.startswith("54"):
        numero_nacional = solo_digitos[2:]
        if numero_nacional.startswith("9"):
            numero_nacional = numero_nacional[1:]
    else:
        numero_nacional = solo_digitos

    # En Argentina el 0 de larga distancia no va despues de +549.
    # 54901157347193 -> 5491157347193
    # 01157347193 -> 5491157347193
    while numero_nacional.startswith("0"):
        numero_nacional = numero_nacional[1:]

    numero_nacional = _quitar_15_movil_argentino(numero_nacional)

    if not numero_nacional:
        return ""

    return "549" + numero_nacional
