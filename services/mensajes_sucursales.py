"""
services/mensajes_sucursales.py
────────────────────────────────
Mensajes y utilidades conversacionales para elección de sucursales.

APB:
- No asignar una sucursal por inferencia débil.
- Si hay una sola sucursal ofrecida, un afirmativo del cliente cuenta como
  confirmación explícita de esa única opción.
- Si hay varias sucursales, un afirmativo sin número no alcanza: hay que pedir
  que indique número/opción para no equivocarse.
"""


def _texto(valor):
    return str(valor or "").strip()


def _formatear_sucursal(sucursal, numero=None):
    if not isinstance(sucursal, dict):
        sucursal = {}

    nombre = _texto(
        sucursal.get("nombre")
        or sucursal.get("name")
        or sucursal.get("agency_name")
    )

    direccion = _texto(
        sucursal.get("direccion")
        or sucursal.get("address")
    )

    if not nombre:
        nombre = "Sucursal"

    encabezado = f"{numero}) {nombre}" if numero is not None else nombre

    if direccion:
        return f"{encabezado}\n{direccion}"

    return encabezado


def armar_mensaje_sucursales(sucursales, transporte="Vía Cargo"):
    """
    Arma mensaje de sucursales según cantidad disponible.

    - 0 sucursales: None.
    - 1 sucursal: pide confirmación.
    - 2 o más: pide elección por número.
    """
    sucursales = list(sucursales or [])
    transporte = _texto(transporte) or "transporte"

    if not sucursales:
        return None

    if len(sucursales) == 1:
        sucursal = _formatear_sucursal(sucursales[0])

        return (
            "Genial 👍\n\n"
            f"Encontré esta sucursal disponible de {transporte} para el despacho:\n\n"
            f"{sucursal}\n\n"
            "Confirmame si te queda bien y avanzamos con el despacho 🚀"
        )

    lista = ""

    for i, sucursal in enumerate(sucursales, 1):
        lista += f"{_formatear_sucursal(sucursal, i)}\n\n"

    return (
        "Genial 👍\n\n"
        f"Te paso sucursales cercanas de {transporte} para que elijas:\n\n"
        f"{lista}"
        "Decime el número de la sucursal que preferís y despachamos 🚀"
    )


def texto_pide_opcion_numerica_sucursal():
    return (
        "Perfecto 👍\n\n"
        "Para no equivocarnos, decime el número de la sucursal que preferís."
    )



def normalizar_numero_opcion_sucursal(texto):
    """Devuelve índice 0-based de sucursal elegida o None.

    APB:
    - Números 1/2/3 se aceptan como elección.
    - Palabras como "uno", "dos", "tres" solo se aceptan si son el mensaje completo
      o si vienen con contexto explícito: "opción tres", "la tercera".
    - No debe confundir localidades como "Tres Arroyos" con opción 3.
    """
    import re
    import unicodedata

    t = str(texto or "").strip().lower()
    if not t:
        return None

    normalizado = unicodedata.normalize("NFD", t)
    normalizado = "".join(ch for ch in normalizado if unicodedata.category(ch) != "Mn")
    normalizado = re.sub(r"[^a-z0-9\s]", " ", normalizado)
    normalizado = " ".join(normalizado.split())

    match_numero = re.fullmatch(
        r"(?:opcion|op|sucursal|numero|nro|la|el)?\s*([1-3])",
        normalizado,
    )
    if match_numero:
        return int(match_numero.group(1)) - 1

    equivalencias = {
        "uno": 0,
        "una": 0,
        "primera": 0,
        "primer": 0,
        "dos": 1,
        "segunda": 1,
        "segundo": 1,
        "tres": 2,
        "tercera": 2,
        "tercero": 2,
    }

    if normalizado in equivalencias:
        return equivalencias[normalizado]

    match_palabra = re.fullmatch(
        r"(?:opcion|op|sucursal|numero|nro|la|el)\s+"
        r"(uno|una|primera|primer|dos|segunda|segundo|tres|tercera|tercero)",
        normalizado,
    )
    if match_palabra:
        return equivalencias.get(match_palabra.group(1))

    return None


def extraer_opcion_sucursal_explicita(texto, cantidad_opciones=0):
    """Detecta una elección explícita de sucursal dentro de un texto.

    APB:
    - Acepta números 1/2/3 aun en mensajes mixtos.
    - Acepta palabras ("tres", "tercera") solo si son el mensaje completo
      o si están acompañadas por contexto explícito.
    - No interpreta localidades como "Tres Arroyos" como opción 3.
    - Devuelve índice 0-based o None.
    """
    import re
    import unicodedata

    texto = str(texto or "").strip().lower()
    if not texto:
        return None

    normalizado = unicodedata.normalize("NFD", texto)
    normalizado = "".join(ch for ch in normalizado if unicodedata.category(ch) != "Mn")
    normalizado = re.sub(r"[^a-z0-9\s]", " ", normalizado)
    normalizado = " ".join(normalizado.split())

    candidatos = []

    patrones_numero = [
        (r"\b(?:opcion|op|sucursal|numero|nro|la|el)?\s*1\b", 0),
        (r"\b(?:opcion|op|sucursal|numero|nro|la|el)?\s*2\b", 1),
        (r"\b(?:opcion|op|sucursal|numero|nro|la|el)?\s*3\b", 2),
    ]

    for patron, indice in patrones_numero:
        if re.search(patron, normalizado):
            candidatos.append(indice)

    indice_palabra = normalizar_numero_opcion_sucursal(normalizado)
    if indice_palabra is not None:
        candidatos.append(indice_palabra)

    candidatos_unicos = sorted(set(candidatos))

    if cantidad_opciones:
        candidatos_unicos = [
            indice for indice in candidatos_unicos
            if 0 <= indice < int(cantidad_opciones)
        ]

    if len(candidatos_unicos) != 1:
        return None

    return candidatos_unicos[0]
