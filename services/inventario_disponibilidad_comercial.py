"""Vista previa de stock publicable; no llama APIs ni cambia existencias."""


def _entero(valor, predeterminado=0):
    try:
        return int(valor if valor is not None else predeterminado)
    except (TypeError, ValueError):
        return int(predeterminado)


def calcular_cantidad_publicable(*, politica, existencia, item, vinculo=None):
    """Calcula una propuesta conservadora y explica cada bloqueo."""
    motivos = []
    actual = _entero(getattr(existencia, "stock_actual", 0))
    reservado = _entero(getattr(existencia, "stock_reservado", 0))
    bloqueado = _entero(getattr(existencia, "stock_bloqueado", 0))
    disponible_fisico = max(actual - reservado - bloqueado, 0)
    umbral = max(_entero(getattr(politica, "umbral_publicacion", 0)), 0)
    cantidad = max(disponible_fisico - umbral, 0)
    maximo = getattr(politica, "maximo_publicable", None)
    if maximo is not None:
        cantidad = min(cantidad, max(_entero(maximo), 0))

    if not bool(getattr(politica, "activa", False)):
        motivos.append("Politica desactivada")
    if item is None or not bool(getattr(item, "activo", False)):
        motivos.append("SKU no preparado o desactivado")
    if existencia is None or not bool(getattr(existencia, "control_activo", False)):
        motivos.append("Control de existencia desactivado")
    if vinculo is None:
        motivos.append("Sin canal empresarial vinculado")
    elif str(getattr(vinculo, "estado", "")) != "activo":
        motivos.append("Vinculo de canal desactivado")
    if disponible_fisico <= umbral:
        motivos.append("Disponible dentro del umbral de seguridad")

    cantidad_propuesta = 0 if motivos else cantidad
    return {
        "actual": actual,
        "reservado": reservado,
        "bloqueado": bloqueado,
        "disponible_fisico": disponible_fisico,
        "umbral": umbral,
        "maximo_publicable": maximo,
        "cantidad_propuesta": cantidad_propuesta,
        "permite_sin_stock": bool(
            getattr(politica, "permite_sin_stock", False)
        ),
        "estado": "publicable" if not motivos else "bloqueado",
        "motivos": motivos,
        "puede_publicar": False,
        "modo": "vista_previa",
    }


def construir_vista_previa_disponibilidad(
    politicas, *, items_inventario, existencias, vinculos
):
    """Expande cada politica por su canal exacto, siempre sin publicar."""
    items_por_catalogo = {
        _entero(getattr(item, "catalogo_producto_id", 0)): item
        for item in items_inventario
        if getattr(item, "catalogo_producto_id", None) is not None
    }
    existencias_por_par = {
        (
            _entero(getattr(existencia, "sucursal_operativa_id", 0)),
            _entero(getattr(existencia, "item_inventario_id", 0)),
        ): existencia
        for existencia in existencias
    }
    filas = []
    for politica in politicas:
        inclusion = getattr(politica, "catalogo_producto", None)
        catalogo = getattr(inclusion, "catalogo", None)
        item = items_por_catalogo.get(
            _entero(getattr(politica, "catalogo_producto_id", 0))
        )
        existencia = existencias_por_par.get((
            _entero(getattr(politica, "sucursal_operativa_id", 0)),
            _entero(getattr(item, "id", 0)),
        ))
        vinculo_exacto_id = getattr(
            politica,
            "vinculo_canal_comercial_id",
            None,
        )
        candidatos = [
            vinculo for vinculo in vinculos
            if vinculo_exacto_id is not None
            and _entero(getattr(vinculo, "id", 0))
            == _entero(vinculo_exacto_id)
            if _entero(getattr(vinculo, "organizacion_id", 0))
            == _entero(getattr(politica, "organizacion_id", 0))
            and _entero(getattr(vinculo, "catalogo_id", 0))
            == _entero(getattr(catalogo, "id", 0))
        ] or [None]
        for vinculo in candidatos:
            calculo = calcular_cantidad_publicable(
                politica=politica,
                existencia=existencia,
                item=item,
                vinculo=vinculo,
            )
            filas.append({
                "politica": politica,
                "item": item,
                "existencia": existencia,
                "vinculo": vinculo,
                "canal": str(getattr(vinculo, "canal", "") or "Sin canal"),
                "cuenta": str(getattr(vinculo, "nombre", "") or "-"),
                **calculo,
            })
    return filas
