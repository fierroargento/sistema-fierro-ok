"""Configuracion historica del costo laboral general por unidad."""

from decimal import Decimal, InvalidOperation

from sqlalchemy import func

from services.fechas import ahora_utc_naive
from services.fuentes_costo_productivo import registrar_costo_empleado
from services.recursos_productivos import recalcular_recursos_del_empleado


def validar_porcentaje(valor):
    try:
        porcentaje = Decimal(str(valor or "0").replace(",", ".").strip())
    except (InvalidOperation, ValueError, AttributeError) as error:
        raise ValueError("El porcentaje general no es válido.") from error
    if not porcentaje.is_finite() or porcentaje < 0 or porcentaje > 100:
        raise ValueError("El porcentaje general debe estar entre 0 y 100.")
    return porcentaje


def configuracion_vigente(organizacion_id, unidad_negocio_id, *, Modelo):
    return Modelo.query.filter_by(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        vigente=True,
    ).first()


def registrar_configuracion(
    *, organizacion_id, unidad_negocio_id, porcentaje, observacion,
    usuario_id, Modelo, db_session,
):
    valor = validar_porcentaje(porcentaje)
    momento = ahora_utc_naive()
    anteriores = Modelo.query.filter_by(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        vigente=True,
    ).all()
    numero = (
        db_session.query(func.max(Modelo.numero_version))
        .filter(Modelo.unidad_negocio_id == unidad_negocio_id)
        .scalar() or 0
    ) + 1
    for anterior in anteriores:
        anterior.vigente = False
        anterior.vigente_hasta = momento
    version = Modelo(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        numero_version=numero,
        porcentaje_cargas=valor,
        vigente=True,
        vigente_desde=momento,
        observacion=str(observacion or "").strip() or None,
        creado_por_usuario_id=usuario_id,
    )
    db_session.add(version)
    db_session.commit()
    return version


def recalcular_empleados_generales(
    empleados, porcentaje, *, EmpleadoCostoVersion, db_session, usuario_id,
):
    recalculados = 0
    for empleado in empleados:
        vigente = next((v for v in empleado.versiones_costo if v.vigente), None)
        if vigente is None or not vigente.usa_porcentaje_general:
            continue
        registrar_costo_empleado(
            empleado,
            moneda=vigente.moneda,
            sueldo_base_centavos=vigente.sueldo_base_centavos,
            porcentaje_cargas=porcentaje,
            usa_porcentaje_general=True,
            adicionales_centavos=vigente.adicionales_centavos,
            otros_costos_centavos=vigente.otros_costos_centavos,
            horas_mensuales=vigente.horas_mensuales,
            horas_productivas=vigente.horas_productivas,
            ubicacion_trabajo=getattr(vigente, "ubicacion_trabajo", "Sin definir"),
            tipo_funcion=getattr(vigente, "tipo_funcion", "directa"),
            porcentaje_productivo=getattr(vigente, "porcentaje_productivo", 100),
            observacion="Recalculado por cambio del porcentaje general.",
            creado_por_usuario_id=usuario_id,
            EmpleadoCostoVersion=EmpleadoCostoVersion,
            db_session=db_session,
        )
        recalcular_recursos_del_empleado(
            empleado, EmpleadoCostoVersion=EmpleadoCostoVersion,
            db_session=db_session, usuario_id=usuario_id,
        )
        recalculados += 1
    return recalculados
