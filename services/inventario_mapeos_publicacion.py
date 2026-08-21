"""Diagnóstico puro de identidades externas; no consulta ni persiste datos."""


ESTADOS = (
    "preparado_sin_conexion",
    "incompleto",
    "duplicado",
    "cruzado",
    "invalido",
)


def normalizar_canal(canal):
    valor = str(canal or "").strip().lower().replace("_", "").replace("-", "")
    alias = {
        "ml": "mercadolibre",
        "mercadolibre": "mercadolibre",
        "tn": "tiendanube",
        "tiendanube": "tiendanube",
    }
    if valor not in alias:
        raise ValueError("Canal externo no admitido.")
    return alias[valor]


def diagnosticar_mapeo(
    mapeo, *, organizacion_id, productos_por_id, vinculos_por_id,
    productos_vistos=None, identidades_vistas=None,
):
    productos_vistos = productos_vistos if productos_vistos is not None else set()
    identidades_vistas = identidades_vistas if identidades_vistas is not None else set()
    bloqueos = []
    advertencias = []
    try:
        canal = normalizar_canal(getattr(mapeo, "canal", ""))
    except ValueError as error:
        canal = ""
        bloqueos.append(str(error))

    vinculo_id = int(getattr(mapeo, "vinculo_canal_comercial_id", 0) or 0)
    producto_id = int(getattr(mapeo, "catalogo_producto_id", 0) or 0)
    vinculo = vinculos_por_id.get(vinculo_id)
    producto = productos_por_id.get(producto_id)
    if int(getattr(mapeo, "organizacion_id", 0) or 0) != int(organizacion_id):
        bloqueos.append("El mapeo pertenece a otra organización")
    if vinculo is None or int(getattr(vinculo, "organizacion_id", 0) or 0) != int(organizacion_id):
        bloqueos.append("La cuenta exacta no pertenece al tenant")
    if producto is None:
        bloqueos.append("El producto de catálogo no pertenece al tenant")
    elif int(getattr(getattr(producto, "catalogo", None), "organizacion_id", 0) or 0) != int(organizacion_id):
        bloqueos.append("El catálogo del producto pertenece a otro tenant")
    if vinculo is not None and canal and canal != normalizar_canal(getattr(vinculo, "canal", "")):
        bloqueos.append("El canal no coincide con la cuenta exacta")
    if producto is not None and vinculo is not None:
        if int(getattr(producto, "catalogo_id", 0) or 0) != int(getattr(vinculo, "catalogo_id", 0) or 0):
            bloqueos.append("Producto y cuenta pertenecen a catálogos diferentes")

    publicacion = str(getattr(mapeo, "publicacion_externa_id", "") or "").strip()
    variante = str(getattr(mapeo, "variante_externa_id", "") or "").strip()
    sku = str(getattr(mapeo, "sku_externo", "") or "").strip()
    if not publicacion:
        bloqueos.append("Falta el identificador de publicación externa")
    if not sku:
        advertencias.append("Falta SKU externo verificable")

    clave_producto = (vinculo_id, producto_id)
    clave_externa = (vinculo_id, publicacion, variante)
    if clave_producto in productos_vistos or (publicacion and clave_externa in identidades_vistas):
        estado = "duplicado"
        bloqueos.append("Producto o identidad externa repetidos dentro de la cuenta")
    elif any("otra" in texto or "diferentes" in texto or "no coincide" in texto for texto in bloqueos):
        estado = "cruzado"
    elif bloqueos:
        estado = "invalido"
    elif advertencias:
        estado = "incompleto"
    else:
        estado = "preparado_sin_conexion"

    productos_vistos.add(clave_producto)
    if publicacion:
        identidades_vistas.add(clave_externa)
    return {
        "estado": estado,
        "bloqueos": bloqueos,
        "advertencias": advertencias,
        "identidad_verificada": False,
        "permite_sincronizar": False,
    }


def diagnosticar_mapeos(mapeos, *, organizacion_id, productos, vinculos):
    productos_por_id = {int(p.id): p for p in productos}
    vinculos_por_id = {int(v.id): v for v in vinculos}
    productos_vistos, identidades_vistas = set(), set()
    diagnosticos = {}
    resumen = {estado: 0 for estado in ESTADOS}
    for mapeo in mapeos:
        diagnostico = diagnosticar_mapeo(
            mapeo,
            organizacion_id=organizacion_id,
            productos_por_id=productos_por_id,
            vinculos_por_id=vinculos_por_id,
            productos_vistos=productos_vistos,
            identidades_vistas=identidades_vistas,
        )
        diagnosticos[getattr(mapeo, "id", None)] = diagnostico
        resumen[diagnostico["estado"]] += 1
    return diagnosticos, resumen


def construir_candidato(**datos):
    """Contrato de importación futura que explícitamente no se guarda."""
    return {
        "canal": normalizar_canal(datos.get("canal")),
        "organizacion_id": int(datos.get("organizacion_id") or 0),
        "vinculo_canal_comercial_id": int(datos.get("vinculo_canal_comercial_id") or 0),
        "catalogo_producto_id": int(datos.get("catalogo_producto_id") or 0),
        "publicacion_externa_id": str(datos.get("publicacion_externa_id") or "").strip(),
        "variante_externa_id": str(datos.get("variante_externa_id") or "").strip(),
        "sku_externo": str(datos.get("sku_externo") or "").strip(),
        "identidad_verificada": False,
        "permite_sincronizar": False,
        "persistir": False,
    }
