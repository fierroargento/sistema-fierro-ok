"""
services/ia_recolector_sync.py
──────────────────────────────
Sincronización APB entre datos reales del pedido y estado del recolector IA.

Problema que resuelve:
- La IA puede detectar datos parciales.
- Luego el sistema autocompleta CP/localidad/provincia en el pedido.
- Si ia_datos_detectados no se consolida con el pedido real, el panel IA queda viejo
  y el flujo puede seguir como si faltaran datos.
- Si la IA detecta teléfono pero todavía no quedó persistido en pedido.telefono,
  el recolector puede marcar datos completos, pero WhatsApp no puede iniciar handoff.
"""

from services.telefonos import normalizar_telefono_service


def _texto(valor):
    return str(valor or "").strip()


def consolidar_datos_recolector_con_pedido(pedido, datos_detectados=None):
    """
    Devuelve datos del recolector consolidados con el pedido real.

    APB:
    - El pedido ya persistido/autocompletado manda sobre lo que detectó la IA.
    - No inventa datos.
    - No pisa nombre/apellido si ya fueron detectados.
    """
    datos = dict(datos_detectados or {})

    if not pedido:
        return datos

    cliente = _texto(getattr(pedido, "cliente", ""))
    if cliente:
        partes = cliente.split()
        if partes and not _texto(datos.get("nombre")):
            datos["nombre"] = partes[0]
        if len(partes) > 1 and not _texto(datos.get("apellido")):
            datos["apellido"] = " ".join(partes[1:])

    mapeo = {
        "dni": "dni",
        "telefono": "telefono",
        "direccion": "direccion",
        "localidad": "localidad",
        "provincia": "provincia",
        "codigo_postal": "codigo_postal",
        "autorizado_nombre": "autorizado_nombre",
        "autorizado_dni": "autorizado_dni",
        "autorizado_telefono": "autorizado_telefono",
    }

    for campo_dato, attr_pedido in mapeo.items():
        valor = _texto(getattr(pedido, attr_pedido, ""))
        if valor:
            datos[campo_dato] = valor

    return datos


def persistir_telefono_detectado_recolector(pedido, datos_detectados=None):
    """
    Persiste en pedido.telefono un teléfono detectado por el recolector IA.

    APB ML -> WA:
    ia_calcular_faltantes_reales_pedido() puede considerar completo un teléfono
    si viene en datos_detectados, pero el handoff a WhatsApp necesita que el dato
    exista realmente en pedido.telefono.

    Devuelve:
    - ["telefono"] si completó el campo.
    - [] si no modificó nada.
    """
    if not pedido:
        return []

    if not isinstance(datos_detectados, dict):
        return []

    if _texto(getattr(pedido, "telefono", "")):
        return []

    telefono_detectado = normalizar_telefono_service(
        datos_detectados.get("telefono")
    )

    if not telefono_detectado:
        return []

    pedido.telefono = telefono_detectado
    datos_detectados["telefono"] = telefono_detectado

    return ["telefono"]
