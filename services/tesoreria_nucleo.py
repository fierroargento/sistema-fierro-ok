"""Nucleo preparatorio de tesoreria, sin cobros o pagos reales."""

import hashlib
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _centavos(valor):
    try: numero=Decimal(str(valor).replace(".","").replace(",","."))
    except (InvalidOperation,ValueError): raise ValueError("El importe no es válido.")
    if not numero.is_finite() or numero<=0: raise ValueError("El importe debe ser mayor que cero.")
    return int((numero*100).quantize(Decimal("1"),rounding=ROUND_HALF_UP))


def crear_cuenta(datos,*,organizacion_id,unidad_negocio_id,CuentaTesoreria,db_session,usuario_id=None):
    codigo=str(datos.get("codigo") or "").strip();nombre=str(datos.get("nombre") or "").strip()
    tipo=str(datos.get("tipo") or "").strip()
    if not codigo or not nombre: raise ValueError("Código y nombre son obligatorios.")
    if tipo not in {"caja","banco","billetera_virtual","compensacion"}: raise ValueError("El tipo de cuenta no es válido.")
    cuenta=CuentaTesoreria(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,
        codigo=codigo,nombre=nombre,tipo=tipo,moneda="ARS",saldo_inicial_centavos=0,
        activa=False,conexion_externa=False,observacion=str(datos.get("observacion") or "").strip() or None,
        creado_por_usuario_id=usuario_id)
    db_session.add(cuenta);db_session.commit();return cuenta


def crear_proyeccion(datos,*,cuenta,organizacion_id,unidad_negocio_id,Movimiento,db_session,usuario_id=None):
    if int(cuenta.organizacion_id)!=int(organizacion_id) or int(cuenta.unidad_negocio_id)!=int(unidad_negocio_id):
        raise ValueError("La cuenta no pertenece al contexto activo.")
    tipo=str(datos.get("tipo") or "").strip()
    if tipo not in {"ingreso","egreso"}: raise ValueError("El tipo de movimiento no es válido.")
    concepto=str(datos.get("concepto") or "").strip()
    if not concepto: raise ValueError("El concepto es obligatorio.")
    try: fecha=date.fromisoformat(str(datos.get("fecha_prevista") or ""))
    except ValueError: raise ValueError("La fecha prevista no es válida.")
    importe=_centavos(datos.get("importe"))
    referencia=str(datos.get("referencia") or "").strip()
    base=f"{organizacion_id}:{unidad_negocio_id}:{cuenta.id}:{tipo}:{fecha.isoformat()}:{importe}:{referencia}:{concepto}"
    clave=hashlib.sha256(base.encode("utf-8")).hexdigest()
    movimiento=Movimiento(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,
        cuenta_tesoreria_id=cuenta.id,tipo=tipo,concepto=concepto,origen="manual",
        referencia=referencia or None,importe_centavos=importe,fecha_prevista=fecha,
        clave_idempotencia=clave,estado="proyectado",confirmado=False,afecta_saldo=False,
        observacion=str(datos.get("observacion") or "").strip() or None,creado_por_usuario_id=usuario_id)
    db_session.add(movimiento);db_session.commit();return movimiento
