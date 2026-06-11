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
    """
    Convierte respuestas humanas simples en índice 0-based.

    Acepta:
    - 1, 2, 3
    - uno, una, primera
    - dos, segunda
    - tres, tercera
    """
    texto = str(texto or "").strip().lower()

    equivalencias = {
        "1": 0,
        "uno": 0,
        "una": 0,
        "primera": 0,
        "primer": 0,
        "opcion 1": 0,
        "opción 1": 0,
        "la 1": 0,
        "la uno": 0,
        "2": 1,
        "dos": 1,
        "segunda": 1,
        "segundo": 1,
        "opcion 2": 1,
        "opción 2": 1,
        "la 2": 1,
        "la dos": 1,
        "3": 2,
        "tres": 2,
        "tercera": 2,
        "tercero": 2,
        "opcion 3": 2,
        "opción 3": 2,
        "la 3": 2,
        "la tres": 2,
    }

    if texto in equivalencias:
        return equivalencias[texto]

    palabras = texto.replace(".", " ").replace(",", " ").replace("-", " ").split()

    for palabra in palabras:
        if palabra in equivalencias:
            return equivalencias[palabra]

    return None


def extraer_opcion_sucursal_explicita(texto, cantidad_opciones=0):
    """
    Detecta una elección explícita de sucursal dentro de un texto más largo.

    APB:
    - Permite mensajes mixtos: "sucede 1, llega para el día del padre?"
    - No inventa si hay más de una opción o si está fuera de rango.
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

    patrones = [
        (r"\b(?:opcion|op|sucursal|numero|nro|la|el)?\s*1\b", 0),
        (r"\b(?:opcion|op|sucursal|numero|nro|la|el)?\s*2\b", 1),
        (r"\b(?:opcion|op|sucursal|numero|nro|la|el)?\s*3\b", 2),
        (r"\b(?:uno|una|primera|primer)\b", 0),
        (r"\b(?:dos|segunda|segundo)\b", 1),
        (r"\b(?:tres|tercera|tercero)\b", 2),
    ]

    for patron, indice in patrones:
        if re.search(patron, normalizado):
            candidatos.append(indice)

    candidatos_unicos = sorted(set(candidatos))

    if len(candidatos_unicos) != 1:
        return None

    indice = candidatos_unicos[0]

    try:
        cantidad_opciones = int(cantidad_opciones or 0)
    except Exception:
        cantidad_opciones = 0

    if cantidad_opciones and indice >= cantidad_opciones:
        return None

    return indice
