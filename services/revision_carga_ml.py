"""
Reglas de revisión operativa de Carga por mensajes de Mercado Libre.

Objetivo:
- Detectar pedidos donde el comprador pide una modificación, agregado
  o condición especial antes de preparar/despachar.
- No responder automáticamente como si fuera un dato logístico.
- Marcar el pedido para que Carga lo revise y Despacho no avance
  hasta que Carga lo habilite.
"""

PALABRAS_ACCION_REVISION_CARGA = [
    "agregar",
    "agregale",
    "agreguen",
    "poner",
    "ponele",
    "pongan",
    "colocar",
    "colocale",
    "hacer",
    "hacerle",
    "modificar",
    "cambiar",
    "sumar",
    "añadir",
    "anadir",
    "necesito que",
    "quiero que",
    "podrian",
    "podrían",
    "se puede",
    "me gustaria",
    "me gustaría",
]

PALABRAS_OBJETO_REVISION_CARGA = [
    "manija",
    "manijas",
    "mango",
    "mangos",
    "pata",
    "patas",
    "rueda",
    "ruedas",
    "altura",
    "medida",
    "medidas",
    "tamaño",
    "tamano",
    "parrilla",
    "brasero",
    "pintura",
    "pintado",
    "sin pintar",
    "refuerzo",
    "reforzado",
    "gancho",
    "ganchos",
    "personalizado",
    "personalizada",
    "a medida",
]


def normalizar_texto_revision_carga_ml(texto):
    return (
        str(texto or "")
        .strip()
        .lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
    )


def detectar_revision_carga_por_mensaje_ml(texto):
    """
    Devuelve True si el mensaje del comprador ML parece pedir
    una modificación/agregado operativo que debe revisar Carga.

    No detecta datos logísticos simples como CP, DNI, dirección o teléfono.
    """
    texto_norm = normalizar_texto_revision_carga_ml(texto)

    if not texto_norm:
        return False

    tiene_accion = any(
        palabra in texto_norm
        for palabra in PALABRAS_ACCION_REVISION_CARGA
    )

    tiene_objeto = any(
        palabra in texto_norm
        for palabra in PALABRAS_OBJETO_REVISION_CARGA
    )

    return bool(tiene_accion and tiene_objeto)


def marcar_revision_carga_por_mensaje_ml(
    pedido,
    texto,
    usuario="sistema",
    registrar_evento=None,
):
    """
    Marca el pedido para revisión de Carga usando el flag operativo existente.

    Reutiliza agregado_pendiente_revision porque ya bloquea preparación/despacho
    y ya tiene flujo de resolución por Carga/Admin.
    """
    if not pedido:
        return False

    if not detectar_revision_carga_por_mensaje_ml(texto):
        return False

    pedido.agregado_pendiente_revision = True
    pedido.agregado_revision_fecha = None
    pedido.agregado_revision_usuario = None

    pedido.ml_mensajes_pendientes = True
    pedido.ml_mensajes_pendientes_count = max(
        int(getattr(pedido, "ml_mensajes_pendientes_count", 0) or 0),
        1,
    )

    pedido.ia_requiere_operador = True

    resumen = str(getattr(pedido, "ia_resumen", "") or "").strip()
    marca = f"ML requiere revisión de Carga: {str(texto or '')[:150]}"

    if marca not in resumen:
        pedido.ia_resumen = f"{resumen} | {marca}".strip(" |")[:1000]

    if registrar_evento:
        registrar_evento(
            pedido=pedido,
            tipo_evento="ml_revision_carga_pendiente",
            origen=usuario or "sistema",
            canal="ml",
            owner="carga",
            payload={
                "texto": str(texto or "")[:500],
                "agregado_pendiente_revision": True,
            },
            resultado="pendiente_revision_carga",
            detalle="Mensaje ML requiere revisión de Carga antes de despacho.",
            procesado=True,
        )

    return True
