"""Control de vencimientos, saldos y pagos de costos indirectos."""

from datetime import date, timedelta


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
