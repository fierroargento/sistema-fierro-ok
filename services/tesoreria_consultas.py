"""Consultas y flujo proyectado de tesoreria tenant."""

import hashlib,io,json


def obtener_panel(organizacion_id,unidad_negocio_id,*,modelos):
    Cuenta=modelos["CuentaTesoreria"];Movimiento=modelos["MovimientoTesoreriaProyectado"]
    cuentas=Cuenta.query.filter_by(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id).order_by(Cuenta.id.asc()).all()
    movimientos=Movimiento.query.filter_by(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id).order_by(Movimiento.fecha_prevista.asc(),Movimiento.id.asc()).all()
    return {"cuentas_tesoreria":cuentas,"movimientos_tesoreria":movimientos,
            "resumen_tesoreria":{"cuentas":len(cuentas),"proyectados":sum(x.estado=="proyectado" for x in movimientos),
            "ingresos_centavos":sum(x.importe_centavos for x in movimientos if x.estado=="proyectado" and x.tipo=="ingreso"),
            "egresos_centavos":sum(x.importe_centavos for x in movimientos if x.estado=="proyectado" and x.tipo=="egreso")}}


def exportar_flujo(*,organizacion_id,unidad_negocio_id,cuentas,movimientos):
    saldos={int(c.id):int(c.saldo_inicial_centavos) for c in cuentas if int(c.organizacion_id)==int(organizacion_id) and int(c.unidad_negocio_id)==int(unidad_negocio_id)}
    filas=[];hallazgos=[]
    for mov in sorted(movimientos,key=lambda x:(x.fecha_prevista,int(x.id))):
        if int(mov.organizacion_id)!=int(organizacion_id) or int(mov.unidad_negocio_id)!=int(unidad_negocio_id):
            hallazgos.append({"codigo":"movimiento_fuera_contexto","movimiento_id":mov.id});continue
        if int(mov.cuenta_tesoreria_id) not in saldos:
            hallazgos.append({"codigo":"cuenta_no_disponible","movimiento_id":mov.id});continue
        if mov.estado!="proyectado":continue
        signo=1 if mov.tipo=="ingreso" else -1;saldos[int(mov.cuenta_tesoreria_id)]+=signo*int(mov.importe_centavos)
        filas.append({"movimiento_id":mov.id,"cuenta_id":mov.cuenta_tesoreria_id,"fecha":mov.fecha_prevista.isoformat(),
                      "tipo":mov.tipo,"concepto":mov.concepto,"importe_centavos":mov.importe_centavos,
                      "saldo_proyectado_centavos":saldos[int(mov.cuenta_tesoreria_id)],"confirmado":False})
    resultado={"organizacion_id":organizacion_id,"unidad_negocio_id":unidad_negocio_id,"modo":"flujo_proyectado_no_contable",
               "filas":filas,"saldos_finales":saldos,"hallazgos":hallazgos,
               "controles":{"persistencia_exportacion":False,"cobros_reales":0,"pagos_reales":0,"asientos":0,"conexiones_externas":0}}
    resultado["huella_flujo"]=hashlib.sha256(json.dumps(resultado,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
    return resultado


def archivo_flujo(resultado): return io.BytesIO(json.dumps(resultado,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8"))
