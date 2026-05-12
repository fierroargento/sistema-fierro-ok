"""
modules/transportes/selector.py
────────────────────────────────
Selector APB de transporte para PP6040.

Decisión actual validada:
- En esta etapa SOLO se cotiza Correo Argentino.
- Andreani queda en standby hasta tener credenciales reales.
- El cliente NUNCA ve costos: para el comprador es envío sin cargo.
- Preferencia operativa: punto/sucursal Correo.
- Domicilio solo se acepta automático si no supera en más de 20% a sucursal
  y no supera el tope máximo configurable.
"""

import json
import re
from datetime import datetime

from .correo_argentino import cotizar_correo, obtener_sucursales_correo_por_pedido


def _cfg_float(clave, default):
    """Lee configuración desde DB si existe; si no, usa default seguro."""
    try:
        from app import ConfiguracionSistema
        obj = ConfiguracionSistema.query.filter_by(clave=clave).first()
        if obj and str(obj.valor or "").strip() != "":
            return float(str(obj.valor).replace(",", "."))
    except Exception:
        pass
    return float(default or 0)


def pedido_contiene_pp6040(pedido):
    """Detecta cualquier SKU/descrición que contenga PP6040."""
    try:
        items = list(getattr(pedido, "items", []) or [])
    except Exception:
        items = []
    textos = []
    for item in items:
        textos.append(str(getattr(item, "sku", "") or ""))
        textos.append(str(getattr(item, "descripcion", "") or ""))
    textos.append(str(getattr(pedido, "observaciones", "") or ""))
    blob = " ".join(textos).upper()
    return "PP6040" in blob


def cotizar_correo_pp6040(pedido):
    """Cotiza sucursal y domicilio por Correo para un pedido PP6040."""
    cp = str(getattr(pedido, "codigo_postal", "") or "").strip()
    if not cp or not re.fullmatch(r"\d{4,8}", cp):
        return {
            "ok": False,
            "error": "CP destino inválido o faltante",
            "requiere_operador": True,
        }

    sucursal = cotizar_correo(cp, tipo_entrega="S")
    domicilio = cotizar_correo(cp, tipo_entrega="D")

    error = None

    if not (sucursal.get("disponible") or domicilio.get("disponible")):
        error_suc = (sucursal or {}).get("error") or ""
        error_dom = (domicilio or {}).get("error") or ""

        if (
            "autentic" in error_suc.lower()
            or "autentic" in error_dom.lower()
        ):
            error = "No se pudo autenticar con Correo Argentino. Revisar credenciales en Render."
        else:
            error = f"No se pudo cotizar Correo para CP {cp}. Revisar respuesta de la integración."

    return {
        "ok": bool(sucursal.get("disponible") or domicilio.get("disponible")),
        "cp_destino": cp,
        "sucursal": sucursal,
        "domicilio": domicilio,
        "error": error,
    }


def evaluar_decision_correo_pp6040(pedido, preferencia_cliente="sucursal"):
    """Evalúa si se puede decidir automático o debe escalar.

    preferencia_cliente:
    - "sucursal": flujo preferido.
    - "domicilio": cliente insiste domicilio.
    """
    from modules.whatsapp.config import MAX_COSTO_ENVIO_DEFAULT, MAX_PORCENTAJE_DOMICILIO_DEFAULT

    cot = cotizar_correo_pp6040(pedido)
    if not cot.get("ok"):
        cot["decision"] = "escalar"
        cot["motivo"] = cot.get("error") or "No se pudo cotizar Correo"
        return cot

    max_costo = _cfg_float("MAX_COSTO_ENVIO", MAX_COSTO_ENVIO_DEFAULT)
    max_porcentaje_dom = _cfg_float("MAX_PORCENTAJE_DOMICILIO", MAX_PORCENTAJE_DOMICILIO_DEFAULT)

    suc = cot.get("sucursal") or {}
    dom = cot.get("domicilio") or {}
    suc_ok = bool(suc.get("disponible"))
    dom_ok = bool(dom.get("disponible"))
    precio_suc = float(suc.get("precio") or 0)
    precio_dom = float(dom.get("precio") or 0)

    # Tope máximo general. 0 significa sin tope cargado todavía.
    precio_control = precio_suc if preferencia_cliente != "domicilio" else precio_dom
    if max_costo > 0 and precio_control > max_costo:
        cot.update({
            "decision": "escalar",
            "motivo": f"Cotización supera tope admin (${precio_control:.0f} > ${max_costo:.0f})",
            "max_costo": max_costo,
        })
        return cot

    if preferencia_cliente == "domicilio":
        if not dom_ok:
            cot.update({"decision": "escalar", "motivo": "Cliente pidió domicilio pero Correo no devolvió cotización domicilio"})
            return cot
        if suc_ok and precio_suc > 0:
            limite = precio_suc * (1 + max_porcentaje_dom / 100.0)
            if precio_dom > limite:
                cot.update({
                    "decision": "escalar",
                    "motivo": f"Domicilio supera +{max_porcentaje_dom:.0f}% contra sucursal",
                    "limite_domicilio": limite,
                })
                return cot
        cot.update({"decision": "domicilio", "motivo": "Domicilio aceptado por regla automática"})
        return cot

    # Preferencia base: sucursal/punto Correo.
    if suc_ok:
        cot.update({"decision": "sucursal", "motivo": "Sucursal/Punto Correo preferido"})
    elif dom_ok:
        cot.update({"decision": "escalar", "motivo": "No hay sucursal disponible; solo domicilio"})
    else:
        cot.update({"decision": "escalar", "motivo": "Sin opciones Correo disponibles"})
    return cot


def asignar_transporte_pedido(pedido, preferencia_cliente="sucursal"):
    """Cotiza y asigna Correo al pedido PP6040, sin informar costos al cliente.

    APB: deshabilitado hasta confirmar credenciales Correo Argentino en Render.
    Reactivar eliminando el return de abajo cuando estén las credenciales.
    """
    # APB: cotización Correo deshabilitada hasta tener credenciales configuradas.
    # Quitar este return cuando CORREO_USER y CORREO_PASS estén en Render.
    return False, "Cotización Correo temporalmente deshabilitada"

    if not pedido_contiene_pp6040(pedido):
        return False, "El pedido no contiene PP6040"

    resultado = evaluar_decision_correo_pp6040(pedido, preferencia_cliente=preferencia_cliente)
    decision = resultado.get("decision")

    if decision == "escalar":
        _marcar_escalado(pedido, resultado.get("motivo") or "Revisión manual transporte Correo")
        return False, resultado.get("motivo") or "Revisión manual transporte Correo"

    try:
        from app import db
        pedido.empresa_envio = "Correo Argentino"
        pedido.tipo_entrega = "Domicilio" if decision == "domicilio" else "Sucursal"

        if hasattr(pedido, "costo_envio"):
            cot_sel = resultado.get("domicilio") if decision == "domicilio" else resultado.get("sucursal")
            pedido.costo_envio = float((cot_sel or {}).get("precio") or 0)
        if hasattr(pedido, "costo_envio_sucursal"):
            pedido.costo_envio_sucursal = float((resultado.get("sucursal") or {}).get("precio") or 0)
        if hasattr(pedido, "costo_envio_domicilio"):
            pedido.costo_envio_domicilio = float((resultado.get("domicilio") or {}).get("precio") or 0)

        resumen = (getattr(pedido, "ia_resumen", "") or "").strip()
        pedido.ia_resumen = f"{resumen} | Correo PP6040 evaluado: {decision}. {resultado.get('motivo','')}".strip(" |")
        db.session.commit()
        return True, f"Correo Argentino asignado ({pedido.tipo_entrega})"
    except Exception as e:
        try:
            from app import db
            db.session.rollback()
        except Exception:
            pass
        return False, f"Error asignando Correo: {e}"


def sugerir_sucursales_correo_pedido(pedido):
    """Genera mensaje con 3 puntos Correo cercanos usando la misma lógica geográfica validada para Via Cargo."""
    try:
        sucursales = obtener_sucursales_correo_por_pedido(pedido)
    except Exception as e:
        print("[CORREO SELECTOR] Error obteniendo sucursales:", e)
        sucursales = []

    if not sucursales:
        _marcar_escalado(pedido, "No se pudieron obtener sucursales Correo cercanas")
        return None

    sucs = sucursales[:3]
    try:
        from app import db
        ids = [s.get("id") or s.get("agencyId") or s.get("codigo") or str(i + 1) for i, s in enumerate(sucs)]
        if hasattr(pedido, "correo_sucursales_ofrecidas"):
            pedido.correo_sucursales_ofrecidas = json.dumps(sucs, ensure_ascii=False)
        else:
            pedido.ia_sucursales_ofrecidas = json.dumps(ids, ensure_ascii=False)
        pedido.empresa_envio = "Correo Argentino"
        pedido.tipo_entrega = "Sucursal"
        pedido.wa_estado = "falta_elegir_transporte"
        pedido.wa_ultimo_contacto = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        print("[CORREO SELECTOR] Error guardando sucursales ofrecidas:", e)

    lista = ""
    for i, s in enumerate(sucs, 1):
        nombre = s.get("nombre") or s.get("name") or s.get("descripcion") or "Punto Correo"
        direccion = s.get("direccion") or s.get("address") or s.get("domicilio") or ""
        localidad = s.get("localidad") or s.get("city") or ""
        lista += f"{i}) {nombre}\n{direccion}{(' - ' + localidad) if localidad else ''}\n\n"

    return (
        "Genial, ya tenemos los datos para avanzar con el despacho.\n\n"
        "Siempre recomendamos retiro en sucursal o punto Correo porque suele ser más ordenado "
        "y evita posibles demoras por visitas fallidas en domicilio.\n\n"
        "Te paso las opciones más cercanas:\n\n"
        f"{lista}"
        "Decime cuál preferís y seguimos con el despacho."
    )


def _marcar_escalado(pedido, motivo):
    try:
        from app import db
        pedido.ia_requiere_operador = True
        pedido.ml_mensajes_pendientes = True
        pedido.wa_estado = "requiere_operador"
        resumen = (pedido.ia_resumen or "").strip()
        pedido.ia_resumen = f"{resumen} | TRANSPORTE: {motivo}".strip(" |")
        db.session.commit()
    except Exception as e:
        print("[SELECTOR] Error escalando:", e)
