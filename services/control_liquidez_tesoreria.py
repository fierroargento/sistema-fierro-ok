"""Escenarios de liquidez sobre proyecciones internas, sin movimientos reales."""

import hashlib,io,json
from datetime import timedelta


def _escenario(nombre,cuentas,movimientos,atraso_ingresos=0,adelanto_egresos=0):
    saldos={int(c.id):int(c.saldo_inicial_centavos) for c in cuentas}
    eventos=[]
    for m in movimientos:
        if m.estado!="proyectado":continue
        fecha=m.fecha_prevista
        if m.tipo=="ingreso":fecha=fecha+timedelta(days=atraso_ingresos)
        else:fecha=fecha-timedelta(days=adelanto_egresos)
        eventos.append((fecha,int(m.id),m))
    filas=[];minimo=sum(saldos.values());primera_negativa=None
    for fecha,_id,m in sorted(eventos,key=lambda x:(x[0],x[1])):
        saldos[int(m.cuenta_tesoreria_id)]+=(1 if m.tipo=="ingreso" else -1)*int(m.importe_centavos)
        consolidado=sum(saldos.values());minimo=min(minimo,consolidado)
        if consolidado<0 and primera_negativa is None:primera_negativa=fecha.isoformat()
        filas.append({"fecha":fecha.isoformat(),"movimiento_id":m.id,"tipo":m.tipo,
                      "importe_centavos":m.importe_centavos,"saldo_consolidado_centavos":consolidado})
    return {"nombre":nombre,"atraso_ingresos_dias":atraso_ingresos,"adelanto_egresos_dias":adelanto_egresos,
            "saldo_final_centavos":sum(saldos.values()),"saldo_minimo_centavos":minimo,
            "primera_fecha_negativa":primera_negativa,"eventos":filas}


def controlar_liquidez(*,organizacion_id,unidad_negocio_id,cuentas,movimientos):
    hallazgos=[];cuentas_validas=[];ids=set()
    for c in cuentas:
        if int(c.organizacion_id)!=int(organizacion_id) or int(c.unidad_negocio_id)!=int(unidad_negocio_id):
            hallazgos.append({"codigo":"cuenta_fuera_contexto","cuenta_id":c.id});continue
        cuentas_validas.append(c);ids.add(int(c.id))
    movimientos_validos=[]
    for m in movimientos:
        if int(m.organizacion_id)!=int(organizacion_id) or int(m.unidad_negocio_id)!=int(unidad_negocio_id):
            hallazgos.append({"codigo":"proyeccion_fuera_contexto","movimiento_id":m.id});continue
        if int(m.cuenta_tesoreria_id) not in ids:
            hallazgos.append({"codigo":"cuenta_inexistente","movimiento_id":m.id});continue
        if m.confirmado or m.afecta_saldo:
            hallazgos.append({"codigo":"proyeccion_con_impacto","movimiento_id":m.id});continue
        movimientos_validos.append(m)
    escenarios=[_escenario("base",cuentas_validas,movimientos_validos),
                _escenario("tension_moderada",cuentas_validas,movimientos_validos,7,3),
                _escenario("tension_alta",cuentas_validas,movimientos_validos,15,7)]
    resultado={"organizacion_id":organizacion_id,"unidad_negocio_id":unidad_negocio_id,
        "modo":"liquidez_proyectada","aprobado":not hallazgos and all(x["primera_fecha_negativa"] is None for x in escenarios),
        "escenarios":escenarios,"hallazgos":hallazgos,
        "controles":{"persistencia":False,"saldos_reales_modificados":0,"pagos":0,"cobros":0,"conexiones_externas":0}}
    resultado["huella_liquidez"]=hashlib.sha256(json.dumps(resultado,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
    return resultado


def exportar_liquidez(resultado):return io.BytesIO(json.dumps(resultado,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8"))
