from services.telefonos import es_telefono_whatsapp_argentina_valido_service


def evaluar_precondiciones_wa_auto_ml(
    pedido,
    flag_wa_auto_desde_ml,
    es_ml_acordas_entrega_fn,
    puede_hacer_handoff_fn,
    normalizar_telefono_fn,
):
    """
    Evalua precondiciones para iniciar WhatsApp automaticamente desde ML/Acordas.

    Devuelve:
    - {"ok": False, "motivo": "..."} si debe frenar.
    - {"ok": True, "tel": "...", "motivo_handoff": "..."} si puede seguir.
    """
    if not pedido or not es_ml_acordas_entrega_fn(pedido):
        return {
            "ok": False,
            "motivo": "no_aplica",
        }

    flag = str(flag_wa_auto_desde_ml or "1").strip().lower()
    if flag in ["0", "false", "no", "off"]:
        return {
            "ok": False,
            "motivo": "apagado",
        }

    if not getattr(pedido, "contacto_iniciado", False):
        return {
            "ok": False,
            "motivo": "ml_no_iniciado",
        }

    permitido_handoff, motivo_handoff = puede_hacer_handoff_fn(pedido)

    if not permitido_handoff:
        return {
            "ok": False,
            "motivo": motivo_handoff,
        }

    tel = normalizar_telefono_fn(getattr(pedido, "telefono", ""))
    if not es_telefono_whatsapp_argentina_valido_service(tel):
        return {
            "ok": False,
            "motivo": "sin_telefono_valido",
        }

    return {
        "ok": True,
        "tel": tel,
        "motivo_handoff": motivo_handoff,
    }
