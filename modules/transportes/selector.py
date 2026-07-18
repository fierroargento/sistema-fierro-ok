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
from services.logistica_catalogo import calcular_logistica_pedido_desde_catalogo
from services.transporte_revision import (
    TIPO_ERROR_AUTENTICACION,
    TIPO_ERROR_DATOS,
    TIPO_ERROR_DATOS_LOGISTICOS,
    TIPO_ERROR_INTEGRACION,
    TIPO_ERROR_PRODUCTO_NO_PERMITE_CORREO,
    TIPO_ERROR_REVISION,
    TIPO_ERROR_SIN_COBERTURA,
)


def correo_pp6040_habilitado():
    """
    Feature flag operativo para integración Correo PP6040.

    APB:
    - Si está apagado, no cotiza, no busca sucursales y no ensucia resumen.
    - Se habilita por env CORREO_PP6040_ENABLED=true cuando la integración esté validada.
    """
    try:
        from modules.whatsapp.config import CORREO_PP6040_ENABLED
        return bool(CORREO_PP6040_ENABLED)
    except Exception:
        return False


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
    """
    Detecta familia PP6040 usando solo SKU.

    APB:
    - La regla se centraliza en domain/productos.py.
    - No mira descripción ni observaciones.
    - PA9060H no entra como PP6040.
    """
    from domain.productos import pedido_tiene_pp6040
    return pedido_tiene_pp6040(pedido)


def _error_logistica_correo(cp, logistica):
    faltantes = logistica.get("faltantes") or []
    detalle = " ".join(faltantes[:3]).strip()

    return {
        "ok": False,
        "cp_destino": cp,
        "sucursal": {},
        "domicilio": {},
        "error": (
            "Datos logísticos incompletos para cotizar Correo."
            + (f" {detalle}" if detalle else "")
        ),
        "motivo": logistica.get("motivo") or "datos_logisticos_incompletos",
        "tipo_error": TIPO_ERROR_DATOS_LOGISTICOS,
        "requiere_operador": True,
        "logistica": logistica,
    }


def cotizar_correo_pp6040(pedido):
    """Cotiza sucursal y domicilio por Correo usando logística del catálogo."""
    cp = str(getattr(pedido, "codigo_postal", "") or "").strip()
    if not cp or not re.fullmatch(r"\d{4,8}", cp):
        return {
            "ok": False,
            "error": "CP destino inválido o faltante",
            "motivo": "cp_destino_invalido",
            "tipo_error": TIPO_ERROR_DATOS,
            "requiere_operador": True,
        }

    logistica = calcular_logistica_pedido_desde_catalogo(pedido)

    if not logistica.get("ok"):
        return _error_logistica_correo(cp, logistica)

    if not logistica.get("permite_correo"):
        return {
            "ok": False,
            "cp_destino": cp,
            "sucursal": {},
            "domicilio": {},
            "error": "El catálogo indica que este pedido no permite Correo Argentino.",
            "motivo": "producto_no_permite_correo",
            "tipo_error": TIPO_ERROR_PRODUCTO_NO_PERMITE_CORREO,
            "requiere_operador": True,
            "logistica": logistica,
        }

    dimensiones = {
        "peso_gr": logistica.get("peso_gr"),
        "alto_cm": logistica.get("alto_cm"),
        "ancho_cm": logistica.get("ancho_cm"),
        "largo_cm": logistica.get("largo_cm"),
    }

    try:
        sucursal = cotizar_correo(cp, tipo_entrega="S", **dimensiones)
        domicilio = cotizar_correo(cp, tipo_entrega="D", **dimensiones)
    except (Exception, SystemExit) as e:
        return {
            "ok": False,
            "cp_destino": cp,
            "sucursal": {},
            "domicilio": {},
            "error": f"No se pudo cotizar Correo para CP {cp}: {e}",
            "motivo": "error_integracion_correo",
            "tipo_error": TIPO_ERROR_INTEGRACION,
            "requiere_operador": True,
            "logistica": logistica,
        }

    error = None
    tipo_error = None

    if not (sucursal.get("disponible") or domicilio.get("disponible")):
        error_suc = (sucursal or {}).get("error") or ""
        error_dom = (domicilio or {}).get("error") or ""
        texto_error = f"{error_suc} {error_dom}".lower()

        if "autentic" in texto_error or "credencial" in texto_error:
            tipo_error = TIPO_ERROR_AUTENTICACION
            error = "No se pudo autenticar con Correo Argentino. Revisar credenciales en Render."
        elif "sin cobertura" in texto_error or "no hay cobertura" in texto_error:
            tipo_error = TIPO_ERROR_SIN_COBERTURA
            error = f"Sin cobertura Correo para CP {cp}."
        elif error_suc or error_dom:
            tipo_error = TIPO_ERROR_INTEGRACION
            error = f"No se pudo cotizar Correo para CP {cp}. Revisar respuesta de la integración."
        else:
            tipo_error = TIPO_ERROR_REVISION
            error = f"Sin opciones Correo disponibles para CP {cp}."

    return {
        "ok": bool(sucursal.get("disponible") or domicilio.get("disponible")),
        "cp_destino": cp,
        "sucursal": sucursal,
        "domicilio": domicilio,
        "error": error,
        "tipo_error": tipo_error,
        "logistica": logistica,
        "dimensiones": dimensiones,
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
        cot["tipo_error"] = cot.get("tipo_error") or TIPO_ERROR_REVISION
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
    if not correo_pp6040_habilitado():
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
        from services.correo_argentino_operacion import (
            aplicar_resumen_cotizacion_a_pedido,
            extraer_resumen_cotizacion,
        )

        resumen_correo = extraer_resumen_cotizacion(resultado)
        ok_aplicar, mensaje_aplicar = aplicar_resumen_cotizacion_a_pedido(
            pedido,
            resumen_correo,
        )

        if not ok_aplicar:
            _marcar_escalado(
                pedido,
                mensaje_aplicar or "Cotización Correo no aplicable",
            )
            return False, mensaje_aplicar or "Cotización Correo no aplicable"

        db.session.commit()
        return True, f"Correo Argentino asignado ({pedido.tipo_entrega})"
    except Exception as e:
        try:
            from app import db
            db.session.rollback()
        except Exception:
            pass
        return False, f"Error asignando Correo: {e}"


def sugerir_sucursales_correo_pedido(pedido, canal_origen="ml"):
    """Genera mensaje con puntos Correo cercanos.

    canal_origen:
    - "ml": las opciones se van a enviar por Mercado Libre. No activa WhatsApp.
    - "wa": las opciones se van a enviar por WhatsApp. Activa estado WA.
    """
    canal_origen = str(canal_origen or "ml").strip().lower()

    if not correo_pp6040_habilitado():
        print("[CORREO SELECTOR] PP6040 deshabilitado por feature flag. No se buscan sucursales.")
        return None

    # PP6040 / plegables:
    # Antes de ofrecer sucursales Correo al cliente, validamos costo.
    # Si Correo sucursal supera el umbral configurado, no ofrecemos opciones
    # y dejamos la decisión al operador, porque Andreani puede estar más barato.
    if pedido_contiene_pp6040(pedido):
        try:
            from services.correo_argentino_operacion import evaluar_oferta_sucursales_correo_pp6040

            cotizacion_pp6040 = cotizar_correo_pp6040(pedido)
            decision_sucursal = evaluar_oferta_sucursales_correo_pp6040(
                (cotizacion_pp6040 or {}).get("sucursal"),
                resultado_cotizacion=cotizacion_pp6040,
            )

            if not decision_sucursal.get("ofrecer_sucursales"):
                motivo = decision_sucursal.get("motivo") or "Correo sucursal PP6040 requiere revisión operador."
                precio = decision_sucursal.get("precio")
                umbral = decision_sucursal.get("umbral")

                _marcar_escalado(
                    pedido,
                    f"{motivo} Precio Correo sucursal: {precio}. Umbral: {umbral}."
                )
                return None

        except Exception as e:
            _marcar_escalado(
                pedido,
                f"No se pudo validar costo Correo sucursal PP6040: {e}"
            )
            return None

    try:
        sucursales = obtener_sucursales_correo_por_pedido(pedido)
    except Exception as e:
        print("[CORREO SELECTOR] Error obteniendo sucursales:", e)
        sucursales = []

    if not sucursales:
        _marcar_escalado(pedido, "No se pudieron obtener sucursales Correo cercanas")
        return None

    try:
        from services.correo_argentino_operacion import obtener_preferencias_operativas_correo
        preferencias_correo = obtener_preferencias_operativas_correo()
        limite_sucursales = int(preferencias_correo.get("cantidad_sucursales_cliente") or 3)
    except Exception:
        limite_sucursales = 3

    from services.workflow_correo_sucursal_oferta import (
        aplicar_oferta_sucursales_correo_al_pedido,
        preparar_oferta_sucursales_correo,
    )

    oferta_correo = preparar_oferta_sucursales_correo(
        sucursales,
        limite=limite_sucursales,
    )

    if not oferta_correo:
        _marcar_escalado(pedido, "No se pudieron preparar sucursales Correo cercanas")
        return None

    # Compatibilidad: se guarda la sucursal raw como antes para no romper el detector existente.
    sucs = sucursales[:limite_sucursales]
    try:
        from app import db
        if not aplicar_oferta_sucursales_correo_al_pedido(
            pedido,
            sucs,
            oferta_correo.ids,
            canal_origen=canal_origen,
        ):
            _marcar_escalado(pedido, "No se pudieron aplicar sucursales Correo cercanas")
            return None

        db.session.commit()
    except Exception as e:
        print("[CORREO SELECTOR] Error guardando sucursales ofrecidas:", e)
        try:
            db.session.rollback()
        except Exception:
            pass
        return None

    return oferta_correo.mensaje


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
