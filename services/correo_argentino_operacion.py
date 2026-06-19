"""
services/correo_argentino_operacion.py

Capa operativa para usar resultados de MiCorreo/Correo dentro del pedido.

No consulta APIs.
No crea envíos.
No paga.
No imprime etiquetas.

Solo normaliza decisiones para que el sistema pueda guardar/mostrar:
- modalidad elegida
- costo sucursal
- costo domicilio
- servicio
- motivo
"""

TRANSPORTE_CORREO = "Correo Argentino"

PREFERENCIAS_CORREO_DEFAULT = {
    "modalidad_preferida": "sucursal",
    "domicilio_permitido": True,
    "servicio_preferido": "clasico",
    "cantidad_sucursales_cliente": 3,
    "mostrar_costos_cliente": False,
    "requiere_operador_para_pago_etiqueta": True,
    "priorizar_correo_sucursal_acordas": True,
    "max_costo_correo_sucursal_acordas": 0,
}

PREFERENCIAS_CORREO_ENV = {
    "modalidad_preferida": "CORREO_MODALIDAD_PREFERIDA",
    "domicilio_permitido": "CORREO_DOMICILIO_PERMITIDO",
    "servicio_preferido": "CORREO_MICORREO_SERVICIO_PREFERIDO",
    "cantidad_sucursales_cliente": "CORREO_CANTIDAD_SUCURSALES_CLIENTE",
    "mostrar_costos_cliente": "CORREO_MOSTRAR_COSTOS_CLIENTE",
    "requiere_operador_para_pago_etiqueta": "CORREO_REQUIERE_OPERADOR_PAGO_ETIQUETA",
    "priorizar_correo_sucursal_acordas": "CORREO_PRIORIZAR_SUCURSAL_ACORDAS",
    "max_costo_correo_sucursal_acordas": "CORREO_MAX_COSTO_SUCURSAL_ACORDAS",
}


def _to_float(valor, default=0.0):
    try:
        if valor is None or valor == "":
            return default
        return float(valor)
    except Exception:
        return default


def _cotizacion_disponible(cotizacion):
    cotizacion = cotizacion or {}
    return bool(cotizacion.get("disponible") and cotizacion.get("precio") is not None)


def extraer_resumen_cotizacion(resultado):
    """Extrae datos útiles del resultado de selector.evaluar_decision_correo_pp6040()."""
    resultado = resultado or {}
    sucursal = resultado.get("sucursal") or {}
    domicilio = resultado.get("domicilio") or {}
    decision = str(resultado.get("decision") or "").strip().lower()

    precio_sucursal = _to_float(sucursal.get("precio"))
    precio_domicilio = _to_float(domicilio.get("precio"))

    if decision == "domicilio":
        precio_elegido = precio_domicilio
        tipo_entrega = "Domicilio"
        servicio = domicilio.get("servicio") or domicilio.get("tipo") or ""
    elif decision == "sucursal":
        precio_elegido = precio_sucursal
        tipo_entrega = "Sucursal"
        servicio = sucursal.get("servicio") or sucursal.get("tipo") or ""
    else:
        precio_elegido = 0.0
        tipo_entrega = ""
        servicio = ""

    return {
        "ok": decision in {"sucursal", "domicilio"},
        "transporte": TRANSPORTE_CORREO,
        "decision": decision,
        "tipo_entrega": tipo_entrega,
        "precio_elegido": precio_elegido,
        "precio_sucursal": precio_sucursal,
        "precio_domicilio": precio_domicilio,
        "sucursal_disponible": _cotizacion_disponible(sucursal),
        "domicilio_disponible": _cotizacion_disponible(domicilio),
        "servicio": servicio,
        "motivo": resultado.get("motivo") or resultado.get("error") or "",
        "cp_destino": resultado.get("cp_destino") or "",
        "raw": resultado,
    }


def aplicar_resumen_cotizacion_a_pedido(pedido, resumen):
    """Aplica el resumen a un objeto pedido compatible.

    No hace commit. La transacción queda a cargo del llamador.
    """
    resumen = resumen or {}

    if not resumen.get("ok"):
        return False, resumen.get("motivo") or "Cotización Correo no aplicable"

    pedido.empresa_envio = TRANSPORTE_CORREO
    pedido.tipo_entrega = resumen.get("tipo_entrega") or ""

    if hasattr(pedido, "costo_envio"):
        pedido.costo_envio = _to_float(resumen.get("precio_elegido"))

    if hasattr(pedido, "costo_envio_sucursal"):
        pedido.costo_envio_sucursal = _to_float(resumen.get("precio_sucursal"))

    if hasattr(pedido, "costo_envio_domicilio"):
        pedido.costo_envio_domicilio = _to_float(resumen.get("precio_domicilio"))

    if hasattr(pedido, "ia_resumen"):
        anterior = (getattr(pedido, "ia_resumen", "") or "").strip()
        detalle = (
            f"Correo Argentino evaluado: {resumen.get('tipo_entrega')}. "
            f"{resumen.get('motivo') or ''}"
        ).strip()
        pedido.ia_resumen = f"{anterior} | {detalle}".strip(" |")

    return True, f"Correo Argentino aplicado ({pedido.tipo_entrega})"


def armar_lineas_cotizacion_cliente(resumen):
    """Arma líneas internas para operador. No incluye promesa comercial al cliente."""
    resumen = resumen or {}
    lineas = []

    if resumen.get("precio_sucursal"):
        lineas.append(
            f"Sucursal: ${resumen['precio_sucursal']:.0f}"
        )

    if resumen.get("precio_domicilio"):
        lineas.append(
            f"Domicilio: ${resumen['precio_domicilio']:.0f}"
        )

    if resumen.get("servicio"):
        lineas.append(f"Servicio elegido: {resumen['servicio']}")

    if resumen.get("motivo"):
        lineas.append(f"Motivo: {resumen['motivo']}")

    return lineas



def _env(nombre, default=""):
    import os
    return str(os.getenv(nombre, default) or "").strip()


def _env_bool(nombre, default="false"):
    return _env(nombre, default).lower() in {"1", "true", "si", "sí", "yes", "on"}


def _env_int(nombre, default):
    try:
        return int(_env(nombre, str(default)))
    except Exception:
        return int(default)


def obtener_preferencias_operativas_correo():
    """Preferencias SaaS para gestión automática/manual de Correo.

    Fierro por defecto:
    - Prioridad sucursal.
    - Domicilio permitido como alternativa.
    - Servicio preferido clásico.
    - No mostrar costos al cliente.
    - Tras elección, pasa a operador para pago/etiqueta en MiCorreo.
    """
    modalidad = _env(
        PREFERENCIAS_CORREO_ENV["modalidad_preferida"],
        PREFERENCIAS_CORREO_DEFAULT["modalidad_preferida"],
    ).lower()

    if modalidad not in {"sucursal", "domicilio"}:
        modalidad = PREFERENCIAS_CORREO_DEFAULT["modalidad_preferida"]

    cantidad = _env_int(
        PREFERENCIAS_CORREO_ENV["cantidad_sucursales_cliente"],
        PREFERENCIAS_CORREO_DEFAULT["cantidad_sucursales_cliente"],
    )

    if cantidad < 1:
        cantidad = 1
    if cantidad > 5:
        cantidad = 5

    return {
        "transporte": TRANSPORTE_CORREO,
        "modalidad_preferida": modalidad,
        "domicilio_permitido": _env_bool(
            PREFERENCIAS_CORREO_ENV["domicilio_permitido"],
            "true" if PREFERENCIAS_CORREO_DEFAULT["domicilio_permitido"] else "false",
        ),
        "servicio_preferido": _env(
            PREFERENCIAS_CORREO_ENV["servicio_preferido"],
            PREFERENCIAS_CORREO_DEFAULT["servicio_preferido"],
        ).lower(),
        "cantidad_sucursales_cliente": cantidad,
        "mostrar_costos_cliente": _env_bool(
            PREFERENCIAS_CORREO_ENV["mostrar_costos_cliente"],
            "true" if PREFERENCIAS_CORREO_DEFAULT["mostrar_costos_cliente"] else "false",
        ),
        "requiere_operador_para_pago_etiqueta": _env_bool(
            PREFERENCIAS_CORREO_ENV["requiere_operador_para_pago_etiqueta"],
            "true" if PREFERENCIAS_CORREO_DEFAULT["requiere_operador_para_pago_etiqueta"] else "false",
        ),
        "priorizar_correo_sucursal_acordas": _env_bool(
            PREFERENCIAS_CORREO_ENV["priorizar_correo_sucursal_acordas"],
            "true" if PREFERENCIAS_CORREO_DEFAULT["priorizar_correo_sucursal_acordas"] else "false",
        ),
        "max_costo_correo_sucursal_acordas": _to_float(
            _env(
                PREFERENCIAS_CORREO_ENV["max_costo_correo_sucursal_acordas"],
                str(PREFERENCIAS_CORREO_DEFAULT["max_costo_correo_sucursal_acordas"]),
            )
        ),
    }



def evaluar_prioridad_correo_sucursal_acordas(
    cotizacion_sucursal,
    es_acordas=True,
    es_pp6040=False,
    preferencias=None,
):
    """Evalúa si un pedido Acordás no PP6040 debe priorizar Correo sucursal.

    Regla:
    - Solo aplica a ML/Acordás.
    - No aplica a PP6040 porque PP6040 ya tiene regla propia.
    - Solo aplica si Correo sucursal está disponible.
    - Si el costo de Correo sucursal es menor o igual al umbral configurado,
      se prioriza Correo. Si no, sigue el flujo normal de Vía Cargo.

    El umbral se configura con:
    CORREO_MAX_COSTO_SUCURSAL_ACORDAS

    Si el umbral es 0, la regla queda apagada.
    """
    prefs = preferencias or obtener_preferencias_operativas_correo()

    if not es_acordas:
        return {
            "usar_correo": False,
            "motivo": "No aplica: no es Acordás.",
            "precio": 0.0,
            "umbral": _to_float(prefs.get("max_costo_correo_sucursal_acordas")),
        }

    if es_pp6040:
        return {
            "usar_correo": False,
            "motivo": "No aplica: PP6040 usa regla Correo propia.",
            "precio": 0.0,
            "umbral": _to_float(prefs.get("max_costo_correo_sucursal_acordas")),
        }

    if not prefs.get("priorizar_correo_sucursal_acordas"):
        return {
            "usar_correo": False,
            "motivo": "Regla Correo sucursal Acordás deshabilitada.",
            "precio": 0.0,
            "umbral": _to_float(prefs.get("max_costo_correo_sucursal_acordas")),
        }

    umbral = _to_float(prefs.get("max_costo_correo_sucursal_acordas"))
    if umbral <= 0:
        return {
            "usar_correo": False,
            "motivo": "Regla Correo sucursal Acordás sin umbral configurado.",
            "precio": 0.0,
            "umbral": umbral,
        }

    cot = cotizacion_sucursal or {}
    if not _cotizacion_disponible(cot):
        return {
            "usar_correo": False,
            "motivo": "Correo sucursal no disponible.",
            "precio": _to_float(cot.get("precio")),
            "umbral": umbral,
        }

    precio = _to_float(cot.get("precio"))
    if precio <= umbral:
        return {
            "usar_correo": True,
            "motivo": f"Correo sucursal priorizado por costo (${precio:.0f} <= ${umbral:.0f}).",
            "precio": precio,
            "umbral": umbral,
        }

    return {
        "usar_correo": False,
        "motivo": f"Correo sucursal supera umbral (${precio:.0f} > ${umbral:.0f}).",
        "precio": precio,
        "umbral": umbral,
    }
