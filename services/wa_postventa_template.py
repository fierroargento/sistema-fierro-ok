import re


SKU_PARRILLA_CONTIENE = [
    "PP6040",
    "PF",
    "PA",
    "B5030",
    "B4030",
    "KBP",
    "KITPACH",
    "KPADES",
    "BPPC",
]

SKU_GENERICO_CONTIENE = [
    "C-MDF",
    "R-MDF",
    "MS-MDF",
    "PC-MDF",
    "PPH",
]

PALABRAS_FALLBACK_PARRILLA = [
    "parrilla",
    "parrillero",
    "brasero",
    "asador",
    "asado",
    "fogon",
    "fogón",
    "achuras",
    "atizador",
    "chulengo",
]


def _normalizar_sku(sku):
    return str(sku or "").upper().strip()


def _skus_pedido_postventa(pedido):
    skus = [_normalizar_sku(getattr(pedido, "sku", ""))]

    for item in getattr(pedido, "items", []) or []:
        skus.append(_normalizar_sku(getattr(item, "sku", "")))

        if isinstance(item, dict):
            skus.append(_normalizar_sku(item.get("sku", "")))

    return [sku for sku in skus if sku]


def _sku_es_parrilla(sku):
    sku = _normalizar_sku(sku)
    return any(marca in sku for marca in SKU_PARRILLA_CONTIENE)


def _sku_es_generico(sku):
    sku = _normalizar_sku(sku)
    return any(marca in sku for marca in SKU_GENERICO_CONTIENE)


def _texto_pedido_postventa(pedido):
    partes = [
        getattr(pedido, "producto", ""),
        getattr(pedido, "descripcion", ""),
    ]

    for item in getattr(pedido, "items", []) or []:
        partes.extend([
            getattr(item, "descripcion", ""),
            getattr(item, "nombre", ""),
            getattr(item, "producto", ""),
        ])

        if isinstance(item, dict):
            partes.extend([
                item.get("descripcion", ""),
                item.get("nombre", ""),
                item.get("producto", ""),
            ])

    return " ".join(str(p or "") for p in partes).lower()


def _contiene_palabra_completa(texto, palabra):
    tokens = re.findall(r"[a-záéíóúñ0-9]+", str(texto or "").lower())
    return palabra.lower() in tokens


def pedido_es_postventa_parrilla(pedido):
    skus = _skus_pedido_postventa(pedido)

    if any(_sku_es_parrilla(sku) for sku in skus):
        return True

    if skus and any(_sku_es_generico(sku) for sku in skus):
        return False

    texto = _texto_pedido_postventa(pedido)
    return any(
        _contiene_palabra_completa(texto, palabra)
        for palabra in PALABRAS_FALLBACK_PARRILLA
    )


def template_postventa_para_pedido(
    pedido,
    template_parrilla="postventa_parrilla",
    template_generico="postventa_generica",
):
    if pedido_es_postventa_parrilla(pedido):
        return template_parrilla

    return template_generico
