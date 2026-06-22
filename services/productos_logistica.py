"""
Cálculo logístico por pedido.

Usa el catálogo de productos para calcular peso y dimensiones internas
sin pedirle datos al operador de Carga.
"""

import math


CAMPOS_DIMENSIONES = ("peso_gr", "alto_cm", "ancho_cm", "largo_cm")


def _cantidad_item(item):
    try:
        cantidad = int(float(str(getattr(item, "cantidad", 1) or 1).replace(",", ".")))
    except Exception:
        cantidad = 1

    return max(cantidad, 1)


def _sku_item(item):
    return str(getattr(item, "sku", "") or "").strip().upper()


def _descripcion_item(item):
    return str(getattr(item, "descripcion", "") or "").strip()


def _numero_positivo(valor):
    try:
        numero = float(valor)
    except Exception:
        return None

    if not math.isfinite(numero) or numero <= 0:
        return None

    return numero


def _bool_catalogo(valor, default=True):
    if valor is None:
        return default

    return bool(valor)


def producto_tiene_logistica_completa(producto):
    if not producto:
        return False

    for campo in CAMPOS_DIMENSIONES:
        if _numero_positivo(getattr(producto, campo, None)) is None:
            return False

    return True


def calcular_logistica_pedido(pedido, buscar_producto_por_sku):
    """
    Calcula peso y paquete consolidado del pedido.

    Regla de paquete inicial:
    - peso total = suma de peso_gr * cantidad
    - alto total = suma de alto_cm * cantidad
    - ancho = mayor ancho_cm encontrado
    - largo = mayor largo_cm encontrado

    Esta regla es conservadora para parrillas apiladas.
    """

    items_pedido = list(getattr(pedido, "items", None) or [])

    if not items_pedido:
        return {
            "ok": False,
            "motivo": "sin_items",
            "peso_gr": None,
            "alto_cm": None,
            "ancho_cm": None,
            "largo_cm": None,
            "permite_correo": False,
            "permite_via_cargo": False,
            "requiere_revision_logistica": True,
            "faltantes": ["El pedido no tiene items."],
            "items": [],
        }

    peso_total = 0.0
    alto_total = 0.0
    ancho_max = 0.0
    largo_max = 0.0

    permite_correo = True
    permite_via_cargo = True
    requiere_revision = False
    faltantes = []
    detalle_items = []

    for item in items_pedido:
        sku = _sku_item(item)
        descripcion = _descripcion_item(item)
        cantidad = _cantidad_item(item)

        producto = buscar_producto_por_sku(sku) if sku else None

        detalle = {
            "sku": sku,
            "descripcion": descripcion,
            "cantidad": cantidad,
            "en_catalogo": bool(producto),
            "peso_gr": None,
            "alto_cm": None,
            "ancho_cm": None,
            "largo_cm": None,
            "permite_correo": False,
            "permite_via_cargo": False,
            "requiere_revision_logistica": True,
        }

        if not producto:
            requiere_revision = True
            faltantes.append(f"SKU {sku or descripcion or 'sin SKU'} no encontrado en catálogo.")
            detalle_items.append(detalle)
            continue

        peso_gr = _numero_positivo(getattr(producto, "peso_gr", None))
        alto_cm = _numero_positivo(getattr(producto, "alto_cm", None))
        ancho_cm = _numero_positivo(getattr(producto, "ancho_cm", None))
        largo_cm = _numero_positivo(getattr(producto, "largo_cm", None))

        detalle["peso_gr"] = peso_gr
        detalle["alto_cm"] = alto_cm
        detalle["ancho_cm"] = ancho_cm
        detalle["largo_cm"] = largo_cm

        producto_permite_correo = _bool_catalogo(getattr(producto, "permite_correo", True), default=True)
        producto_permite_via_cargo = _bool_catalogo(getattr(producto, "permite_via_cargo", True), default=True)
        producto_revision = bool(getattr(producto, "requiere_revision_logistica", False))

        detalle["permite_correo"] = producto_permite_correo
        detalle["permite_via_cargo"] = producto_permite_via_cargo
        detalle["requiere_revision_logistica"] = producto_revision

        if not producto_permite_correo:
            permite_correo = False

        if not producto_permite_via_cargo:
            permite_via_cargo = False

        if producto_revision:
            requiere_revision = True

        campos_faltantes = []
        for campo, valor in {
            "peso_gr": peso_gr,
            "alto_cm": alto_cm,
            "ancho_cm": ancho_cm,
            "largo_cm": largo_cm,
        }.items():
            if valor is None:
                campos_faltantes.append(campo)

        if campos_faltantes:
            requiere_revision = True
            faltantes.append(f"SKU {sku} sin datos logísticos completos: {', '.join(campos_faltantes)}.")
            detalle_items.append(detalle)
            continue

        peso_total += peso_gr * cantidad
        alto_total += alto_cm * cantidad
        ancho_max = max(ancho_max, ancho_cm)
        largo_max = max(largo_max, largo_cm)

        detalle_items.append(detalle)

    ok = bool(
        not faltantes
        and peso_total > 0
        and alto_total > 0
        and ancho_max > 0
        and largo_max > 0
    )

    return {
        "ok": ok,
        "motivo": "" if ok else "datos_logisticos_incompletos",
        "peso_gr": peso_total if peso_total > 0 else None,
        "alto_cm": alto_total if alto_total > 0 else None,
        "ancho_cm": ancho_max if ancho_max > 0 else None,
        "largo_cm": largo_max if largo_max > 0 else None,
        "permite_correo": permite_correo and ok,
        "permite_via_cargo": permite_via_cargo and ok,
        "requiere_revision_logistica": requiere_revision or not ok,
        "faltantes": faltantes,
        "items": detalle_items,
        "origen": "catalogo_productos",
    }
