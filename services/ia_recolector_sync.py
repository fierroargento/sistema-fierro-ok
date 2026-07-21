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


def resolver_requiere_operador_final_recolector(pedido=None, requiere_operador=False):
    """
    Mantiene persistente el lock operativo de operador.

    APB:
    - La IA puede marcar requiere_operador=True ante una consulta/corrección.
    - Una respuesta posterior del cliente no debe limpiar ese lock automáticamente.
    - Solo una acción explícita del operador o un flujo específico debe reencauzar.
    """
    estado_actual = str(
        getattr(pedido, "ia_recolector_estado", "") or ""
    ).strip().lower()

    operador_pendiente_previo = bool(
        getattr(pedido, "ia_requiere_operador", False)
        or estado_actual == "requiere_operador"
    )

    return bool(requiere_operador or operador_pendiente_previo)

def json_loads_seguro_recolector(texto):
    """
    Lee JSON persistido por el recolector IA de forma tolerante.

    APB:
    - Si viene vacío, devuelve {}.
    - Si viene JSON válido, lo devuelve.
    - Si viene texto con un JSON embebido, intenta extraer el primer objeto.
    - Si falla, devuelve {}.
    """
    import json

    texto = str(texto or "").strip()
    if not texto:
        return {}

    try:
        return json.loads(texto)
    except Exception:
        pass

    ini = texto.find("{")
    fin = texto.rfind("}")

    if ini >= 0 and fin > ini:
        try:
            return json.loads(texto[ini:fin + 1])
        except Exception:
            return {}

    return {}


def datos_detectados_pedido_recolector(pedido):
    """
    Devuelve ia_datos_detectados como dict seguro.
    """
    if not pedido or not getattr(pedido, "ia_datos_detectados", None):
        return {}

    data = json_loads_seguro_recolector(pedido.ia_datos_detectados)

    return data if isinstance(data, dict) else {}


def faltantes_pedido_recolector(pedido):
    """
    Devuelve ia_faltantes como list segura.
    """
    if not pedido or not getattr(pedido, "ia_faltantes", None):
        return []

    data = json_loads_seguro_recolector(pedido.ia_faltantes)

    return data if isinstance(data, list) else []


def marcar_recolector_datos_completos(pedido):
    """
    Marca el recolector IA como completo.

    No evalua si el despacho esta completo.
    No hace commit.
    No envia mensajes.
    """

    if not pedido:
        return False

    pedido.ia_faltantes = "[]"
    pedido.ia_recolector_estado = "datos_completos"
    pedido.ia_ultimo_timeout_operador = None

    return True


def datos_previos_pedido_recolector(
    pedido,
    *,
    parece_nickname_fn,
):
    """
    Construye los datos previos del recolector.

    Prioridades:
    - Conserva datos ya detectados.
    - Completa desde el pedido real sin pisarlos.
    - No usa como nombre un nickname de Mercado Libre.
    - No importa app.py ni conoce sesiones o canales.
    """

    if not pedido:
        return {}

    datos = datos_detectados_pedido_recolector(
        pedido
    )

    cliente = _texto(
        getattr(pedido, "cliente", "")
    )
    nickname = _texto(
        getattr(pedido, "ml_buyer_nickname", "")
    )

    if (
        cliente
        and not parece_nickname_fn(
            cliente,
            nickname,
        )
    ):
        partes = cliente.split()
        if partes:
            datos.setdefault(
                "nombre",
                partes[0],
            )
        if len(partes) > 1:
            datos.setdefault(
                "apellido",
                " ".join(partes[1:]),
            )

    mapeo = {
        "dni": "dni",
        "telefono": "telefono",
        "direccion": "direccion",
        "localidad": "localidad",
        "codigo_postal": "codigo_postal",
    }

    for campo_dato, atributo in mapeo.items():
        valor = _texto(
            getattr(pedido, atributo, "")
        )
        if valor:
            datos.setdefault(
                campo_dato,
                valor,
            )

    return datos
