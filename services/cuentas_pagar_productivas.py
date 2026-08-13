"""Control de vencimientos, saldos y pagos de costos indirectos."""

from datetime import date, timedelta


def primer_dia_mes(valor):
    return date(valor.year, valor.month, 1)


def desplazar_meses(valor, cantidad):
    indice = valor.year * 12 + valor.month - 1 + int(cantidad)
    return date(indice // 12, indice % 12 + 1, 1)


def ultimo_dia_mes(periodo):
    siguiente = date(periodo.year + (periodo.month == 12), 1 if periodo.month == 12 else periodo.month + 1, 1)
    return siguiente - timedelta(days=1)


def fecha_vencimiento_periodo(periodo, dia):
    return date(periodo.year, periodo.month, min(int(dia), ultimo_dia_mes(periodo).day))


def configurar_regla_obligacion(costo, *, organizacion_id, frecuencia_meses,
                                periodo_inicio, dia_vencimiento, meses_anticipacion, activa,
                                observacion, usuario_id,
                                ReglaObligacionCostoProductivo, db_session):
    frecuencia = int(frecuencia_meses)
    dia = int(dia_vencimiento)
    anticipacion = int(meses_anticipacion)
    inicio = primer_dia_mes(date.fromisoformat(str(periodo_inicio) + ("-01" if len(str(periodo_inicio)) == 7 else "")))
    if not 1 <= frecuencia <= 120:
        raise ValueError("La frecuencia debe estar entre 1 y 120 meses.")
    if not 1 <= dia <= 31:
        raise ValueError("El día de vencimiento debe estar entre 1 y 31.")
    if not 0 <= anticipacion <= 24:
        raise ValueError("La anticipación debe estar entre 0 y 24 meses.")
    regla = ReglaObligacionCostoProductivo.query.filter_by(costo_fijo_id=costo.id).first()
    if regla is None:
        regla = ReglaObligacionCostoProductivo(
            organizacion_id=organizacion_id, costo_fijo_id=costo.id,
            creado_por_usuario_id=usuario_id,
        )
        db_session.add(regla)
    regla.frecuencia_meses = frecuencia
    regla.periodo_inicio = inicio
    regla.dia_vencimiento = dia
    regla.meses_anticipacion = anticipacion
    regla.activa = bool(activa)
    regla.observacion = str(observacion or "").strip() or None
    db_session.commit()
    return regla


def asegurar_regla_desde_ajuste(regla_ajuste, *, ReglaObligacionCostoProductivo,
                                db_session, usuario_id=None):
    """Convierte una regla de ajuste en calendario mensual sin duplicarla."""
    regla = ReglaObligacionCostoProductivo.query.filter_by(
        costo_fijo_id=regla_ajuste.costo_fijo_id,
    ).first()
    if regla is None:
        regla = ReglaObligacionCostoProductivo(
            organizacion_id=regla_ajuste.organizacion_id,
            costo_fijo_id=regla_ajuste.costo_fijo_id,
            frecuencia_meses=1,
            periodo_inicio=primer_dia_mes(regla_ajuste.proximo_ajuste),
            dia_vencimiento=1 if regla_ajuste.modalidad_pago == "adelantado" else 28,
            meses_anticipacion=2, activa=True,
            observacion="Calendario creado desde la regla de ajuste.",
            creado_por_usuario_id=usuario_id,
        )
        db_session.add(regla)
        db_session.commit()
    return regla


def generar_obligaciones_recurrentes(regla, *, ObligacionCostoProductivo,
                                      CostoFijoVersion, db_session, hoy=None,
                                      usuario_id=None):
    """Genera períodos faltantes hasta el horizonte, de forma idempotente."""
    if not regla.activa:
        return []
    hoy = hoy or date.today()
    inicio = primer_dia_mes(hoy)
    fin = desplazar_meses(inicio, regla.meses_anticipacion)
    version = CostoFijoVersion.query.filter_by(
        costo_fijo_id=regla.costo_fijo_id, vigente=True,
    ).first()
    if version is None:
        return []
    creadas = []
    periodo = inicio
    while periodo <= fin:
        distancia = (periodo.year - regla.periodo_inicio.year) * 12 + periodo.month - regla.periodo_inicio.month
        if distancia >= 0 and distancia % regla.frecuencia_meses == 0:
            existente = ObligacionCostoProductivo.query.filter_by(
                costo_fijo_id=regla.costo_fijo_id, periodo=periodo,
            ).first()
            if existente is None:
                obligacion = ObligacionCostoProductivo(
                    organizacion_id=regla.organizacion_id,
                    costo_fijo_id=regla.costo_fijo_id,
                    version_costo_id=version.id, periodo=periodo,
                    fecha_vencimiento=fecha_vencimiento_periodo(periodo, regla.dia_vencimiento),
                    importe_centavos=(
                        version.importe_periodo_centavos
                        if getattr(version, "importe_periodo_centavos", 0)
                        else version.importe_mensual_centavos
                    ),
                    estado="pendiente", observacion="Generada automáticamente.",
                    creado_por_usuario_id=usuario_id,
                )
                db_session.add(obligacion)
                creadas.append(obligacion)
        periodo = desplazar_meses(periodo, 1)
    db_session.commit()
    return creadas


def ejecutar_generacion_recurrente(*, ReglaObligacionCostoProductivo,
                                   ObligacionCostoProductivo, CostoFijoVersion,
                                   db_session, hoy=None):
    creadas = []
    for regla in ReglaObligacionCostoProductivo.query.filter_by(activa=True).all():
        creadas.extend(generar_obligaciones_recurrentes(
            regla, ObligacionCostoProductivo=ObligacionCostoProductivo,
            CostoFijoVersion=CostoFijoVersion, db_session=db_session, hoy=hoy,
        ))
    return creadas


def saldo_obligacion(obligacion):
    pagado = sum(
        int(p.importe_centavos) for p in obligacion.pagos
        if not getattr(p, "anulado", False)
    )
    return max(0, int(obligacion.importe_centavos) - pagado)


def actualizar_estado(obligacion):
    saldo = saldo_obligacion(obligacion)
    if saldo == 0:
        obligacion.estado = "pagada"
    elif saldo < int(obligacion.importe_centavos):
        obligacion.estado = "parcial"
    else:
        obligacion.estado = "pendiente"
    return obligacion.estado


def asegurar_obligacion_ajuste(regla, *, ObligacionCostoProductivo,
                               CostoFijoVersion, db_session, usuario_id=None):
    """Crea la obligación provisional sin inventar el IPC aún no publicado."""
    periodo = date(regla.proximo_ajuste.year, regla.proximo_ajuste.month, 1)
    existente = ObligacionCostoProductivo.query.filter_by(
        costo_fijo_id=regla.costo_fijo_id, periodo=periodo,
    ).first()
    if existente is not None:
        if getattr(existente, "regla_ajuste_id", None) is None:
            existente.regla_ajuste_id = regla.id
        return existente, False
    version = CostoFijoVersion.query.filter_by(
        costo_fijo_id=regla.costo_fijo_id, vigente=True,
    ).first()
    if version is None:
        raise ValueError("El costo no tiene una versión vigente.")
    vencimiento = periodo if regla.modalidad_pago == "adelantado" else ultimo_dia_mes(periodo)
    obligacion = ObligacionCostoProductivo(
        organizacion_id=regla.organizacion_id, costo_fijo_id=regla.costo_fijo_id,
        version_costo_id=version.id, regla_ajuste_id=regla.id,
        periodo=periodo, fecha_vencimiento=vencimiento,
        importe_centavos=version.importe_mensual_centavos,
        ajuste_pendiente=True, estado="pendiente",
        observacion="Importe provisorio hasta aprobar el ajuste correspondiente.",
        creado_por_usuario_id=usuario_id,
    )
    db_session.add(obligacion)
    db_session.commit()
    return obligacion, True


def actualizar_obligacion_con_propuesta(propuesta, *, ObligacionCostoProductivo,
                                         CostoFijoVersion, db_session):
    """Reemplaza solo el importe esperado; conserva intactos los pagos realizados."""
    periodo = date(propuesta.vigente_desde.year, propuesta.vigente_desde.month, 1)
    obligacion = ObligacionCostoProductivo.query.filter_by(
        costo_fijo_id=propuesta.regla.costo_fijo_id, periodo=periodo,
    ).first()
    if obligacion is None:
        obligacion, _ = asegurar_obligacion_ajuste(
            propuesta.regla, ObligacionCostoProductivo=ObligacionCostoProductivo,
            CostoFijoVersion=CostoFijoVersion, db_session=db_session,
        )
    version = CostoFijoVersion.query.filter_by(
        costo_fijo_id=propuesta.regla.costo_fijo_id, vigente=True,
    ).first()
    obligacion.importe_centavos = propuesta.importe_propuesto_centavos
    obligacion.version_costo_id = version.id if version else obligacion.version_costo_id
    obligacion.propuesta_ajuste_id = propuesta.id
    obligacion.ajuste_pendiente = False
    obligacion.observacion = (
        f"Importe definitivo por IPC {propuesta.periodo_base:%m/%Y}–"
        f"{propuesta.periodo_final:%m/%Y}."
    )
    actualizar_estado(obligacion)
    futuras = ObligacionCostoProductivo.query.filter(
        ObligacionCostoProductivo.costo_fijo_id == propuesta.regla.costo_fijo_id,
        ObligacionCostoProductivo.periodo > periodo,
        ObligacionCostoProductivo.estado != "anulada",
    ).all()
    for futura in futuras:
        futura.importe_centavos = propuesta.importe_propuesto_centavos
        futura.version_costo_id = version.id if version else futura.version_costo_id
        actualizar_estado(futura)
    db_session.commit()
    return obligacion


def crear_obligacion(costo, *, periodo, fecha_vencimiento, importe_centavos,
                     organizacion_id, usuario_id, observacion,
                     ObligacionCostoProductivo, CostoFijoVersion, db_session):
    periodo_texto = str(periodo)
    if len(periodo_texto) == 7:
        periodo_texto += "-01"
    periodo_fecha = date.fromisoformat(periodo_texto)
    periodo_fecha = date(periodo_fecha.year, periodo_fecha.month, 1)
    vencimiento = date.fromisoformat(str(fecha_vencimiento))
    importe = int(importe_centavos)
    if importe <= 0:
        raise ValueError("El importe de la obligación debe ser positivo.")
    if ObligacionCostoProductivo.query.filter_by(costo_fijo_id=costo.id, periodo=periodo_fecha).first():
        raise ValueError("Ya existe una obligación para ese concepto y período.")
    version = CostoFijoVersion.query.filter_by(costo_fijo_id=costo.id, vigente=True).first()
    if version is None:
        raise ValueError("El costo no tiene una versión vigente.")
    obligacion = ObligacionCostoProductivo(
        organizacion_id=organizacion_id, costo_fijo_id=costo.id,
        version_costo_id=version.id, periodo=periodo_fecha,
        fecha_vencimiento=vencimiento, importe_centavos=importe,
        estado="pendiente", observacion=str(observacion or "").strip() or None,
        creado_por_usuario_id=usuario_id,
    )
    db_session.add(obligacion)
    db_session.commit()
    return obligacion


def registrar_pago(obligacion, *, fecha_pago, importe_centavos, medio_pago,
                   referencia, comprobante, observacion, usuario_id,
                   PagoObligacionCostoProductivo, db_session):
    if obligacion.estado == "anulada":
        raise ValueError("No se puede pagar una obligación anulada.")
    importe = int(importe_centavos)
    saldo = saldo_obligacion(obligacion)
    if importe <= 0 or importe > saldo:
        raise ValueError("El pago debe ser positivo y no superar el saldo pendiente.")
    pago = PagoObligacionCostoProductivo(
        obligacion_id=obligacion.id, fecha_pago=date.fromisoformat(str(fecha_pago)),
        importe_centavos=importe, medio_pago=str(medio_pago or "").strip() or None,
        referencia=str(referencia or "").strip() or None,
        comprobante=str(comprobante or "").strip() or None,
        observacion=str(observacion or "").strip() or None,
        creado_por_usuario_id=usuario_id,
    )
    db_session.add(pago)
    db_session.flush()
    actualizar_estado(obligacion)
    db_session.commit()
    return pago


def anular_pago(pago, *, motivo, usuario_id, db_session, ahora_fn=None):
    """Revierte un movimiento conservando su trazabilidad completa."""
    if pago.anulado:
        raise ValueError("El pago ya se encuentra anulado.")
    motivo_limpio = str(motivo or "").strip()
    if not motivo_limpio:
        raise ValueError("Indicá el motivo de la anulación.")
    if ahora_fn is None:
        from services.fechas import ahora_utc_naive
        ahora_fn = ahora_utc_naive
    pago.anulado = True
    pago.motivo_anulacion = motivo_limpio
    pago.fecha_anulacion = ahora_fn()
    pago.anulado_por_usuario_id = usuario_id
    actualizar_estado(pago.obligacion)
    db_session.commit()
    return pago


def resumen_vencimientos(obligaciones, *, hoy=None, dias_aviso=7):
    hoy = hoy or date.today()
    limite = hoy + timedelta(days=dias_aviso)
    vencidas, proximas = [], []
    for obligacion in obligaciones:
        if obligacion.estado in {"pagada", "anulada"}:
            continue
        if obligacion.fecha_vencimiento < hoy:
            vencidas.append(obligacion)
        elif obligacion.fecha_vencimiento <= limite:
            proximas.append(obligacion)
    return {"vencidas": vencidas, "proximas": proximas}
