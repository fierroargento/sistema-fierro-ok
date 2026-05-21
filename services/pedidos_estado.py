from domain.estados import Estado, ESTADOS_POST_DESPACHO


# TODO APB ENCODING:
# Este archivo todavia tiene comparaciones con textos mojibakeados.
# Pendiente normalizar textos operativos para comparar correctamente valores como:
# - Via Cargo / Via Cargo con tilde / texto mojibakeado
# - Acordas la Entrega / Acordas con tilde / texto mojibakeado
# Hacerlo en tarea separada, con tests, porque afecta reglas de flujo.
# APB ESTADOS:
# Estados posteriores al despacho. Se centralizan para evitar listas repetidas
# e inconsistencias entre tracking, reclamos, inicio, detalle y permisos.


# Estados que trabaja el rol Despacho antes de despachar.
ESTADOS_DESPACHO_OPERATIVO = [
    Estado.ETIQUETA_LISTA,
    Estado.ETIQUETA_IMPRESA,
    Estado.EMBALADO,
]


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


# APB WORKFLOW:
# Este es el mapa canonico de transiciones simples de estado.
# Esta funcion NO debe validar permisos, bloqueos, ownership,
# reclamos, tracking ni reglas operativas complejas.
#
# Las validaciones deben hacerse antes, desde guards operativos
# como puede_avanzar_pedido().
#
# Esta funcion solo define:
# estado_actual -> siguiente_estado_operativo
#
# Mantener simple, deterministico y facil de testear.
# IMPORTANTE:
# Algunos estados reales del flujo no salen de este mapa directamente,
# sino de automatizaciones, tracking, reclamos o reglas operativas.
# Ejemplos:
# - Verificar llegada a destino
# - Listo para retirar
# - Con demora de entrega
# - Con reclamo en transporte
#
# Este mapa representa solamente el avance manual base del operador.
def siguiente_estado(estado):
    flujo = {
        Estado.CARGANDO: Estado.ETIQUETA_LISTA,
        Estado.ETIQUETA_LISTA: Estado.ETIQUETA_IMPRESA,
        Estado.ETIQUETA_IMPRESA: Estado.EMBALADO,
        Estado.EMBALADO: Estado.DESPACHADO,
        Estado.DESPACHADO: Estado.ENTREGADO,
        Estado.DEMORA: Estado.ENTREGADO,
        Estado.RECLAMO: Estado.ENTREGADO,
        Estado.VERIFICAR_DESTINO: Estado.ENTREGADO,
        Estado.LISTO_RETIRAR: Estado.ENTREGADO,
    }
    return flujo.get(estado)