"""Gestion y reportes de asientos borrador sin registracion oficial."""

import hashlib
import io
import json
from collections import defaultdict
from datetime import date


def anular_borrador(asiento,*,organizacion_id,unidad_negocio_id,motivo,db_session):
    if int(asiento.organizacion_id)!=int(organizacion_id) or int(asiento.unidad_negocio_id)!=int(unidad_negocio_id):raise ValueError("El asiento no pertenece al contexto activo.")
    if asiento.estado!="borrador" or asiento.contabilizado or asiento.afecta_saldos:raise ValueError("El asiento no puede anularse desde su estado actual.")
    motivo=str(motivo or "").strip()
    if len(motivo)<5:raise ValueError("El motivo debe tener al menos cinco caracteres.")
    asiento.estado="anulado";asiento.referencia=((asiento.referencia+" | ") if asiento.referencia else "")+f"ANULADO: {motivo}"
    asiento.contabilizado=False;asiento.afecta_saldos=False;db_session.commit();return asiento


def _fecha_limite(valor):
    if not valor:return None
    if isinstance(valor,date):return valor
    try:return date.fromisoformat(str(valor))
    except ValueError:raise ValueError("El periodo contable no es valido.")


def generar_reportes(*,organizacion_id,unidad_negocio_id,cuentas,asientos,lineas,desde=None,hasta=None):
    desde=_fecha_limite(desde);hasta=_fecha_limite(hasta)
    if desde and hasta and desde>hasta:raise ValueError("El inicio del periodo no puede ser posterior al cierre.")
    mapa={int(c.id):c for c in cuentas if int(c.organizacion_id)==int(organizacion_id) and int(c.unidad_negocio_id)==int(unidad_negocio_id)}
    cabeceras={int(a.id):a for a in asientos if int(a.organizacion_id)==int(organizacion_id) and int(a.unidad_negocio_id)==int(unidad_negocio_id)
        and (desde is None or a.fecha>=desde) and (hasta is None or a.fecha<=hasta)}
    diario=[];saldos=defaultdict(lambda:{"debe_centavos":0,"haber_centavos":0,"movimientos":[]});hallazgos=[];por_asiento=defaultdict(list)
    for linea in sorted(lineas,key=lambda x:(int(x.asiento_borrador_id),int(x.renglon))):
        asiento=cabeceras.get(int(linea.asiento_borrador_id));cuenta=mapa.get(int(linea.cuenta_contable_id))
        if asiento is None or cuenta is None:
            hallazgos.append({"codigo":"linea_fuera_contexto","linea_id":linea.id});continue
        if linea.afecta_saldos or asiento.contabilizado or asiento.afecta_saldos:
            hallazgos.append({"codigo":"impacto_no_permitido","linea_id":linea.id});continue
        if asiento.estado!="borrador":continue
        por_asiento[int(asiento.id)].append(linea)
        diario.append({"asiento_id":asiento.id,"referencia":asiento.referencia,"fecha":asiento.fecha.isoformat(),"renglon":linea.renglon,
            "cuenta_codigo":cuenta.codigo,"cuenta_nombre":cuenta.nombre,"concepto":linea.concepto,
            "debe_centavos":linea.debe_centavos,"haber_centavos":linea.haber_centavos,"estado":"borrador"})
        saldos[int(cuenta.id)]["debe_centavos"]+=int(linea.debe_centavos);saldos[int(cuenta.id)]["haber_centavos"]+=int(linea.haber_centavos)
        saldos[int(cuenta.id)]["movimientos"].append({"asiento_id":asiento.id,"fecha":asiento.fecha.isoformat(),"concepto":linea.concepto,"debe_centavos":linea.debe_centavos,"haber_centavos":linea.haber_centavos})
    control_asientos=[]
    for asiento_id,asiento in sorted(cabeceras.items()):
        if asiento.estado!="borrador":continue
        items=por_asiento.get(asiento_id,[]);debe=sum(int(x.debe_centavos) for x in items);haber=sum(int(x.haber_centavos) for x in items)
        codigos=[]
        if len(items)<2:codigos.append("sin_lineas_suficientes")
        if debe!=haber:codigos.append("lineas_desbalanceadas")
        if debe!=int(asiento.total_debe_centavos) or haber!=int(asiento.total_haber_centavos):codigos.append("totales_inconsistentes")
        if len({int(x.renglon) for x in items})!=len(items):codigos.append("renglones_duplicados")
        control_asientos.append({"asiento_id":asiento_id,"lineas":len(items),"debe_centavos":debe,"haber_centavos":haber,"hallazgos":codigos,"integro":not codigos})
    balance=[]
    for cuenta_id,valores in sorted(saldos.items(),key=lambda x:mapa[x[0]].codigo):
        cuenta=mapa[cuenta_id];balance.append({"cuenta_id":cuenta_id,"codigo":cuenta.codigo,"nombre":cuenta.nombre,
            "debe_centavos":valores["debe_centavos"],"haber_centavos":valores["haber_centavos"],"saldo_deudor_centavos":max(valores["debe_centavos"]-valores["haber_centavos"],0),
            "saldo_acreedor_centavos":max(valores["haber_centavos"]-valores["debe_centavos"],0)})
    mayor=[{"cuenta_id":cuenta_id,"codigo":mapa[cuenta_id].codigo,"nombre":mapa[cuenta_id].nombre,"movimientos":valores["movimientos"]} for cuenta_id,valores in sorted(saldos.items(),key=lambda x:mapa[x[0]].codigo)]
    total_debe=sum(x["debe_centavos"] for x in balance);total_haber=sum(x["haber_centavos"] for x in balance)
    resultado={"organizacion_id":int(organizacion_id),"unidad_negocio_id":int(unidad_negocio_id),"modo":"reportes_contables_borrador_no_oficiales",
        "periodo":{"desde":desde.isoformat() if desde else None,"hasta":hasta.isoformat() if hasta else None},
        "diario_borrador":diario,"mayor_auxiliar":mayor,"balance_sumas_saldos":balance,"control_asientos":control_asientos,
        "totales":{"debe_centavos":total_debe,"haber_centavos":total_haber,"balanceado":total_debe==total_haber},
        "hallazgos":hallazgos,"aprobado":not hallazgos and all(x["integro"] for x in control_asientos) and total_debe==total_haber,
        "controles":{"persistencia_reporte":False,"asientos_contabilizados":0,"libros_modificados":0,"saldos_modificados":0,"conexiones_externas":0}}
    resultado["huella_reporte"]=hashlib.sha256(json.dumps(resultado,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
    return resultado


def exportar_reportes(resultado):return io.BytesIO(json.dumps(resultado,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8"))
