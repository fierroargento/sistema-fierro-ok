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


def ia_cp_valido_recolector(valor):
    """
    Valida CP para el recolector IA.

    APB:
    - Acepta CP numérico argentino.
    - Acepta formatos alfanuméricos simples.
    - No intenta normalizar ni inventar CP.
    """
    limpio = _texto(valor)
    return limpio if 3 <= len(limpio) <= 12 else ""


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


def calcular_faltantes_reales_recolector(pedido, datos_detectados=None):
    """
    Calcula faltantes reales del recolector contra el pedido actualizado.

    APB:
    - Prioriza el valor real del pedido.
    - Si el pedido no tiene el dato, permite considerar datos_detectados.
    - No pide localidad si ya hay CP válido: localidad/provincia pueden resolverse internamente.
    - No pide DNI si existe ml_billing_documento.
    """
    datos = datos_detectados if isinstance(datos_detectados, dict) else {}

    def valor(campo):
        v = getattr(pedido, campo, "") if pedido else ""
        if _texto(v):
            return _texto(v)
        return _texto(datos.get(campo))

    faltantes = []

    if not valor("nombre") and not valor("cliente"):
        if not _texto(getattr(pedido, "cliente", "")):
            faltantes.append("nombre")

    if not valor("dni") and not _texto(getattr(pedido, "ml_billing_documento", "")):
        faltantes.append("dni")

    if not normalizar_telefono_service(valor("telefono")):
        faltantes.append("telefono")

    if not valor("direccion"):
        faltantes.append("direccion")

    codigo_postal_valido = ia_cp_valido_recolector(valor("codigo_postal"))

    if not codigo_postal_valido and not valor("localidad"):
        faltantes.append("localidad")

    if not codigo_postal_valido:
        faltantes.append("codigo_postal")

    return faltantes

def decidir_estado_recolector(faltantes=None, requiere_operador=False):
    """
    Decide el estado del recolector IA a partir de faltantes reales.

    APB:
    - Si requiere operador, manda sobre cualquier otro estado.
    - Si no hay faltantes, los datos están completos.
    - Si hay faltantes, sigue juntando datos.
    """
    if requiere_operador:
        return "requiere_operador"

    if not faltantes:
        return "datos_completos"

    return "juntando_datos"
