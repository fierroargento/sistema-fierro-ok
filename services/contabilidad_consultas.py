"""Consultas tenant del modulo contable preparatorio."""

def obtener_panel(organizacion_id,unidad_negocio_id,*,modelos):
    Cuenta=modelos["CuentaContable"];Asiento=modelos["AsientoContableBorrador"]
    cuentas=Cuenta.query.filter_by(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id).order_by(Cuenta.codigo.asc()).all()
    asientos=Asiento.query.filter_by(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id).order_by(Asiento.fecha.desc(),Asiento.id.desc()).all()
    return {"cuentas_contables":cuentas,"asientos_borrador":asientos,"resumen_contable":{"cuentas":len(cuentas),
        "borradores":sum(x.estado=="borrador" for x in asientos),"contabilizados":sum(bool(x.contabilizado) for x in asientos)}}
