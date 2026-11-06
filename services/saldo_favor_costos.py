"""Cuenta por concepto: pagos reales y excedentes trasladados sin duplicarlos."""


def calcular_cuenta(obligaciones):
    """Distribuye sólo excedentes hacia períodos posteriores del mismo concepto.

    No escribe pagos sintéticos ni modifica importes de obligaciones. Al anular
    un pago o ajustar una obligación se obtiene nuevamente el saldo correcto.
    """
    grupos={};resultado={}
    for ob in obligaciones:
        clave=(ob.organizacion_id,ob.costo_fijo_id)
        grupos.setdefault(clave,[]).append(ob)
    for filas in grupos.values():
        credito=0
        for ob in sorted(filas,key=lambda r:(r.periodo,r.id or 0)):
            pagado=sum(int(p.importe_centavos) for p in ob.pagos if not getattr(p,'anulado',False))
            if ob.estado=='anulada':
                resultado[ob.id]=dict(pagado_directo=pagado,credito_aplicado=0,a_favor_generado=0,a_favor_trasladado=credito,saldo=0)
                continue
            importe=int(ob.importe_centavos)
            pendiente=max(0,importe-pagado)
            aplicado=min(credito,pendiente)
            excedente=max(0,pagado-importe)
            credito=credito-aplicado+excedente
            resultado[ob.id]=dict(pagado_directo=pagado,credito_aplicado=aplicado,
                a_favor_generado=excedente,a_favor_trasladado=credito,saldo=pendiente-aplicado)
    return resultado


def obligaciones_concepto(obligacion, *, bloquear=False):
    # Los DTO de pruebas no requieren SQLAlchemy ni una sesión.
    if getattr(obligacion,'_sa_instance_state',None) is None:
        return [obligacion]
    from sqlalchemy.orm import object_session, selectinload
    session=object_session(obligacion)
    if session is None:return [obligacion]
    Modelo=type(obligacion)
    consulta=session.query(Modelo).options(selectinload(Modelo.pagos)).filter_by(
        organizacion_id=obligacion.organizacion_id,costo_fijo_id=obligacion.costo_fijo_id
    ).order_by(Modelo.periodo,Modelo.id)
    if bloquear:consulta=consulta.populate_existing().with_for_update()
    return consulta.all()


def detalle_saldo(obligacion):
    if not hasattr(obligacion,'costo_fijo_id') or not hasattr(obligacion,'periodo') or getattr(obligacion,'id',None) is None:
        pagado=sum(int(p.importe_centavos) for p in obligacion.pagos if not getattr(p,'anulado',False))
        return dict(pagado_directo=pagado,credito_aplicado=0,a_favor_generado=max(0,pagado-int(obligacion.importe_centavos)),
            a_favor_trasladado=max(0,pagado-int(obligacion.importe_centavos)),saldo=max(0,int(obligacion.importe_centavos)-pagado))
    return calcular_cuenta(obligaciones_concepto(obligacion))[obligacion.id]


def actualizar_cuenta(obligacion):
    from services.cuentas_pagar_productivas import actualizar_estado
    for ob in obligaciones_concepto(obligacion):
        if ob.estado!='anulada':actualizar_estado(ob)
