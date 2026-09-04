"""Registro interno de promociones observadas, sin operar sobre el canal."""

from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def calcular_descuento_pct(precio_base_centavos, precio_promocional_centavos):
    base = int(precio_base_centavos)
    promocional = int(precio_promocional_centavos)
    if base <= 0: raise ValueError("El precio base debe ser mayor a cero.")
    if promocional < 0 or promocional > base:
        raise ValueError("El precio promocional debe estar entre cero y el precio base.")
    return ((Decimal(base - promocional) * 100) / Decimal(base)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP,
    )


def registrar_observacion(*, organizacion_id, unidad_negocio_id, lista_precio_id,
                          catalogo_producto_id, referencia_externa, nombre,
                          precio_base_centavos, precio_promocional_centavos,
                          estado_observado, origen, observacion, usuario,
                          PromocionCanalObservacion, db_session, commit=True,
                          cuenta_codigo=None):
    estado = str(estado_observado or "").strip().lower()
    fuente = str(origen or "manual").strip().lower()
    if estado not in {"activa", "inactiva"}: raise ValueError("El estado observado no es válido.")
    if fuente not in {"manual", "importacion", "canal"}: raise ValueError("El origen no es válido.")
    try:
        base = int(precio_base_centavos); promocional = int(precio_promocional_centavos)
    except (TypeError, ValueError, InvalidOperation) as error:
        raise ValueError("Los precios observados no son válidos.") from error
    registro = PromocionCanalObservacion(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        lista_precio_id=lista_precio_id, catalogo_producto_id=catalogo_producto_id,
        referencia_externa=str(referencia_externa or "").strip() or None,
        nombre=str(nombre or "").strip() or None,
        precio_base_centavos=base, precio_promocional_centavos=promocional,
        descuento_pct=calcular_descuento_pct(base, promocional),
        estado_observado=estado, origen=fuente,
        observacion=str(observacion or "").strip() or None,
        cuenta_codigo=str(cuenta_codigo or "").strip() or None,
        creado_por_usuario_id=getattr(usuario, "id", None),
        creado_por_username=getattr(usuario, "username", None),
    )
    db_session.add(registro)
    if commit: db_session.commit()
    return registro


def observaciones_actuales(observaciones):
    """Devuelve la observación más reciente por producto/lista."""
    actuales = {}
    for registro in observaciones:
        clave = (registro.lista_precio_id, registro.catalogo_producto_id)
        anterior = actuales.get(clave)
        fecha = getattr(registro, "fecha_observacion", None) or datetime.min
        fecha_anterior = (getattr(anterior, "fecha_observacion", None) or datetime.min) if anterior else datetime.min
        if anterior is None or fecha >= fecha_anterior: actuales[clave] = registro
    return actuales
