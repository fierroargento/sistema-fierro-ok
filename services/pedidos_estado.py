def es_via_cargo(valor):
    if not valor:
        return False

    texto = str(valor).strip().lower()
    texto = texto.replace("í", "i")
    return texto == "via cargo"


def es_ml_acordas_entrega(pedido):
    return (
        getattr(pedido, "canal", "") == "Mercado Libre"
        and getattr(pedido, "ml_tipo", "") == "Acordás la Entrega"
    )


def es_tnube_via_cargo(pedido):
    return (
        getattr(pedido, "canal", "") == "Tienda Nube"
        and es_via_cargo(getattr(pedido, "empresa_envio", ""))
    )


def es_mayorista_via_cargo(pedido):
    return (
        getattr(pedido, "canal", "") not in ["Mercado Libre", "Tienda Nube"]
        and es_via_cargo(getattr(pedido, "empresa_envio", ""))
    )


def usa_flujo_acordas_entrega(pedido):
    return (
        es_ml_acordas_entrega(pedido)
        or es_tnube_via_cargo(pedido)
        or es_mayorista_via_cargo(pedido)
    )


def hay_autorizado(pedido):
    return bool(
        getattr(pedido, "autorizado_nombre", "")
        or getattr(pedido, "autorizado_dni", "")
        or getattr(pedido, "autorizado_telefono", "")
    )


def despacho_completo(pedido):
    tipo = str(getattr(pedido, "tipo_entrega", "") or "").strip()

    if (
        not tipo
        and usa_flujo_acordas_entrega(pedido)
        and str(getattr(pedido, "empresa_envio", "") or "").strip()
    ):
        tipo = "Sucursal"

    if not getattr(pedido, "empresa_envio", "") or not tipo:
        return False

    if tipo == "Domicilio":
        return bool(
            getattr(pedido, "direccion", "")
            and getattr(pedido, "codigo_postal", "")
            and getattr(pedido, "localidad", "")
            and getattr(pedido, "provincia", "")
        )

    if tipo == "Sucursal":
        if not (
            getattr(pedido, "sucursal_nombre", "")
            and getattr(pedido, "direccion", "")
            and getattr(pedido, "localidad", "")
            and getattr(pedido, "provincia", "")
        ):
            return False

        if hay_autorizado(pedido):
            return bool(
                getattr(pedido, "autorizado_nombre", "")
                and getattr(pedido, "autorizado_dni", "")
                and getattr(pedido, "autorizado_telefono", "")
            )

        return True

    return False


def requiere_contacto_cliente(pedido):
    return bool(
        usa_flujo_acordas_entrega(pedido)
        and not despacho_completo(pedido)
    )


def siguiente_estado(estado):
    flujo = {
        "Cargando Pedido": "Etiqueta Lista",
        "Etiqueta Lista": "Etiqueta Impresa",
        "Etiqueta Impresa": "Embalado",
        "Embalado": "Despachado",
        "Despachado": "Entregado",
        "Con demora de entrega": "Entregado",
        "Con reclamo en transporte": "Entregado",
        "Verificar llegada a destino": "Entregado",
        "Listo para retirar": "Entregado",
    }
    return flujo.get(estado)