"""Altas preparatorias contables sin registracion oficial."""

import hashlib
from datetime import date
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP

def _centavos(valor):
    try:numero=Decimal(str(valor).replace(".","").replace(",","."))
    except (InvalidOperation,ValueError):raise ValueError("El importe no es valido.")
    if numero<=0:raise ValueError("El importe debe ser mayor que cero.")
    return int((numero*100).quantize(Decimal("1"),rounding=ROUND_HALF_UP))

def crear_cuenta(datos,*,organizacion_id,unidad_negocio_id,Cuenta,db_session,usuario_id=None):
    codigo=str(datos.get("codigo") or "").strip();nombre=str(datos.get("nombre") or "").strip();naturaleza=str(datos.get("naturaleza") or "").strip()
    if not codigo or not nombre:raise ValueError("Codigo y nombre son obligatorios.")
    if naturaleza not in {"activo","pasivo","patrimonio","ingreso","egreso","orden"}:raise ValueError("Naturaleza contable invalida.")
    cuenta=Cuenta(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,codigo=codigo,nombre=nombre,
        naturaleza=naturaleza,imputable=True,activa=False,creado_por_usuario_id=usuario_id)
    db_session.add(cuenta);db_session.commit();return cuenta

def crear_borrador(datos,*,cuenta_debe,cuenta_haber,organizacion_id,unidad_negocio_id,Asiento,db_session,usuario_id=None):
    for cuenta in (cuenta_debe,cuenta_haber):
        if int(cuenta.organizacion_id)!=int(organizacion_id) or int(cuenta.unidad_negocio_id)!=int(unidad_negocio_id):raise ValueError("La cuenta no pertenece al contexto activo.")
        if not cuenta.imputable:raise ValueError("La cuenta debe ser imputable.")
    if int(cuenta_debe.id)==int(cuenta_haber.id):raise ValueError("Debe y Haber requieren cuentas diferentes.")
    concepto=str(datos.get("concepto") or "").strip();referencia=str(datos.get("referencia") or "").strip()
    if not concepto:raise ValueError("El concepto es obligatorio.")
    try:fecha=date.fromisoformat(str(datos.get("fecha") or ""))
    except ValueError:raise ValueError("La fecha no es valida.")
    importe=_centavos(datos.get("importe"));base=f"{organizacion_id}:{unidad_negocio_id}:{fecha}:{cuenta_debe.id}:{cuenta_haber.id}:{importe}:{referencia}:{concepto}"
    asiento=Asiento(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,fecha=fecha,concepto=concepto,
        cuenta_debe_id=cuenta_debe.id,cuenta_haber_id=cuenta_haber.id,total_debe_centavos=importe,total_haber_centavos=importe,
        referencia=referencia or None,clave_idempotencia=hashlib.sha256(base.encode()).hexdigest(),estado="borrador",
        contabilizado=False,afecta_saldos=False,creado_por_usuario_id=usuario_id)
    db_session.add(asiento);db_session.commit();return asiento
