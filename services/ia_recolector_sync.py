"""
services/ia_recolector_sync.py
──────────────────────────────
Sincronización APB entre datos reales del pedido y estado del recolector IA.

Problema que resuelve:
- La IA puede detectar datos parciales.
- Luego el sistema autocompleta CP/localidad/provincia en el pedido.
- Si ia_datos_detectados no se consolida con el pedido real, el panel IA queda viejo
  y el flujo puede seguir como si faltaran datos.
"""


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
