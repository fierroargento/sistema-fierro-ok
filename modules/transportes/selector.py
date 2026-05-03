"""
modules/transportes/selector.py
────────────────────────────────
Lógica de selección automática del transporte más conveniente
para pedidos PP6040 (plegable) que van por Andreani o Correo Argentino.

Criterio de selección:
    1. Disponibilidad en destino
    2. Precio más bajo entre los disponibles
    3. Si empatan en precio → menor plazo de entrega
"""

from .correo_argentino import cotizar_correo
from .andreani import cotizar_andreani


def cotizar_ambos(cp_destino):
    """
    Cotiza con Correo Argentino y Andreani en paralelo.
    Devuelve dict con los resultados de ambos.

    {
        "correo_argentino": { "disponible": True, "precio": 12500, ... },
        "andreani":         { "disponible": False, "error": "...", ... },
    }
    """
    correo  = cotizar_correo(cp_destino)
    andreani = cotizar_andreani(cp_destino)

    return {
        "correo_argentino": correo,
        "andreani":         andreani,
    }


def elegir_transporte(cp_destino):
    """
    Elige automáticamente el transporte más conveniente.

    Devuelve dict con el ganador:
    {
        "tipo":        "correo_argentino" | "andreani",
        "disponible":  True,
        "precio":      12500.0,
        "plazo_dias":  3,
        "servicio":    "Envío Clásico",
        "cp_origen":   "8500",   # solo Correo Argentino
        "alternativa": { ... }   # el otro transporte si está disponible
    }

    O si ninguno está disponible:
    {
        "tipo":       None,
        "disponible": False,
        "error":      "Sin cobertura en ambos transportes para CP XXXX"
    }
    """
    cotizaciones = cotizar_ambos(cp_destino)
    correo   = cotizaciones["correo_argentino"]
    andreani = cotizaciones["andreani"]

    disponibles = [t for t in [correo, andreani] if t.get("disponible")]

    if not disponibles:
        print(f"[SELECTOR] Sin cobertura para CP {cp_destino}")
        return {
            "tipo":       None,
            "disponible": False,
            "error":      f"Sin cobertura en ambos transportes para CP {cp_destino}",
            "cotizaciones": cotizaciones,
        }

    # Ordenar por precio, luego por plazo
    disponibles.sort(key=lambda t: (
        float(t.get("precio") or 99999999),
        int(t.get("plazo_dias") or 99),
    ))

    ganador = disponibles[0]
    alternativa = disponibles[1] if len(disponibles) > 1 else None

    resultado = dict(ganador)
    resultado["alternativa"] = alternativa
    resultado["cotizaciones"] = cotizaciones

    print(
        f"[SELECTOR] CP {cp_destino} → {ganador['tipo']} "
        f"${ganador.get('precio')} / {ganador.get('plazo_dias')} días"
    )

    return resultado


def asignar_transporte_pedido(pedido):
    """
    Cotiza y asigna automáticamente el transporte al pedido PP6040.
    Guarda empresa_envio, tipo_entrega y costo_envio en el pedido.

    Devuelve (ok, mensaje)
    """
    cp_destino = str(pedido.codigo_postal or "").strip()
    if not cp_destino:
        return False, "El pedido no tiene CP destino"

    resultado = elegir_transporte(cp_destino)

    if not resultado.get("disponible"):
        return False, resultado.get("error", "Sin cobertura")

    try:
        from app import db

        nombres = {
            "correo_argentino": "Correo Argentino",
            "andreani":         "Andreani",
        }

        pedido.empresa_envio  = nombres.get(resultado["tipo"], resultado["tipo"])
        pedido.tipo_entrega   = "Domicilio"
        pedido.costo_envio    = resultado.get("precio")

        db.session.commit()

        msg = (
            f"Transporte asignado: {pedido.empresa_envio} "
            f"— ${resultado.get('precio'):,.0f} "
            f"— {resultado.get('plazo_dias')} días hábiles"
        )
        print(f"[SELECTOR] Pedido #{pedido.id}: {msg}")
        return True, msg

    except Exception as e:
        print(f"[SELECTOR] Error guardando transporte en pedido #{pedido.id}:", e)
        return False, f"Error guardando: {e}"
