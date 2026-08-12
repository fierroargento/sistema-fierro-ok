"""Control de vencimientos, saldos y pagos de costos indirectos."""

from datetime import date, timedelta


def ultimo_dia_mes(periodo):
    siguiente = date(periodo.year + (periodo.month == 12), 1 if periodo.month == 12 else periodo.month + 1, 1)
    return siguiente - timedelta(days=1)


def saldo_obligacion(obligacion):
    pagado = sum(int(p.importe_centavos) for p in obligacion.pagos)
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
                   referencia, observacion, usuario_id,
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
        observacion=str(observacion or "").strip() or None,
        creado_por_usuario_id=usuario_id,
    )
    db_session.add(pago)
    db_session.flush()
    actualizar_estado(obligacion)
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
