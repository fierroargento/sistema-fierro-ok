"""Resolucion estricta de la pertenencia tenant de una cuenta externa."""


class ContextoCanalError(ValueError):
    pass


def resolver_contexto_cuenta(cuenta, *, canal, VinculoCanalComercial):
    cuenta_id = getattr(cuenta, "id", None)
    if cuenta_id is None:
        raise ContextoCanalError("La cuenta externa no es valida.")

    filtros = {"canal": str(canal or "").strip().lower(), "estado": "activo"}
    if filtros["canal"] == "mercadolibre":
        filtros["mercado_libre_cuenta_id"] = cuenta_id
    elif filtros["canal"] == "tiendanube":
        filtros["tienda_nube_cuenta_id"] = cuenta_id
    else:
        raise ContextoCanalError("El canal externo no es valido.")

    vinculos = list(VinculoCanalComercial.query.filter_by(**filtros).all() or [])
    if len(vinculos) != 1:
        raise ContextoCanalError(
            "La cuenta externa debe tener exactamente un vinculo tenant activo."
        )
    vinculo = vinculos[0]
    if not getattr(vinculo, "organizacion_id", None) or not getattr(vinculo, "unidad_negocio_id", None):
        raise ContextoCanalError("El vinculo externo no tiene organizacion y unidad validas.")
    return vinculo


def validar_pedido_en_contexto(pedido, vinculo):
    if pedido is None:
        return True
    if getattr(pedido, "organizacion_id", None) != getattr(vinculo, "organizacion_id", None):
        raise ContextoCanalError("El pedido pertenece a otra organizacion.")
    if getattr(pedido, "unidad_negocio_id", None) != getattr(vinculo, "unidad_negocio_id", None):
        raise ContextoCanalError("El pedido pertenece a otra unidad de negocio.")
    return True
