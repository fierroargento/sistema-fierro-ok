"""Consolida fuentes internas como candidatos de tesoreria sin persistirlas."""

import hashlib,io,json


def _clave(*partes):
    return hashlib.sha256(":".join(str(x) for x in partes).encode("utf-8")).hexdigest()


def consolidar_origenes(*,organizacion_id,unidad_negocio_id,obligaciones,facturas,ventas,proyecciones_existentes):
    existentes={x.clave_idempotencia for x in proyecciones_existentes if int(x.organizacion_id)==int(organizacion_id)}
    candidatos=[];hallazgos=[]
    for obligacion in obligaciones:
        if int(obligacion.organizacion_id)!=int(organizacion_id):
            hallazgos.append({"codigo":"obligacion_fuera_tenant","obligacion_id":obligacion.id});continue
        unidad=getattr(obligacion.costo_fijo,"unidad_negocio_id",None)
        if unidad is not None and int(unidad)!=int(unidad_negocio_id):continue
        if obligacion.estado in ("pagada","anulada"):continue
        pagado=sum(int(p.importe_centavos) for p in obligacion.pagos if not p.anulado)
        saldo=max(0,int(obligacion.importe_centavos)-pagado)
        if saldo==0:continue
        clave=_clave("obligacion",organizacion_id,unidad_negocio_id,obligacion.id,saldo)
        candidatos.append({"organizacion_id":organizacion_id,"unidad_negocio_id":unidad_negocio_id,
            "origen":"obligacion_costo","origen_id":obligacion.id,"tipo":"egreso",
            "concepto":getattr(obligacion.costo_fijo,"nombre","Obligación productiva"),"importe_centavos":saldo,
            "fecha_prevista":obligacion.fecha_vencimiento.isoformat(),"clave_idempotencia":clave,
            "ya_proyectado":clave in existentes,"cuenta_asignada":False})
    for factura in facturas:
        if int(factura.organizacion_id)!=int(organizacion_id) or int(factura.unidad_negocio_id)!=int(unidad_negocio_id):
            hallazgos.append({"codigo":"factura_fuera_contexto","factura_id":factura.id});continue
        if factura.estado=="anulada" or factura.obligacion_creada:continue
        hallazgos.append({"codigo":"factura_sin_vencimiento","factura_id":factura.id,
                          "importe_centavos":int(factura.total_centavos)})
    for venta in ventas:
        if int(venta.organizacion_id)!=int(organizacion_id) or int(venta.unidad_negocio_id)!=int(unidad_negocio_id):
            hallazgos.append({"codigo":"venta_fuera_contexto","venta_id":venta.id});continue
        if venta.estado!="confirmada" or int(venta.liquidacion_esperada_centavos)<=0:continue
        clave=_clave("venta",organizacion_id,unidad_negocio_id,venta.id,venta.liquidacion_esperada_centavos)
        candidatos.append({"organizacion_id":organizacion_id,"unidad_negocio_id":unidad_negocio_id,
            "origen":"liquidacion_canal_esperada","origen_id":venta.id,"tipo":"ingreso",
            "concepto":f"Liquidación esperada {venta.cuenta_codigo} · {venta.referencia_venta}",
            "importe_centavos":int(venta.liquidacion_esperada_centavos),
            "fecha_prevista":venta.fecha_venta.date().isoformat(),"clave_idempotencia":clave,
            "ya_proyectado":clave in existentes,"cuenta_asignada":False})
    candidatos.sort(key=lambda x:(x["fecha_prevista"],x["tipo"],x["origen"],x["origen_id"]))
    resultado={"organizacion_id":organizacion_id,"unidad_negocio_id":unidad_negocio_id,
        "modo":"candidatos_no_persistidos","resumen":{"candidatos":len(candidatos),
        "duplicados":sum(x["ya_proyectado"] for x in candidatos),"hallazgos":len(hallazgos)},
        "candidatos":candidatos,"hallazgos":hallazgos,
        "controles":{"persistencia":False,"proyecciones_creadas":0,"cobros":0,"pagos":0,"conexiones_externas":0}}
    resultado["huella_origenes"]=hashlib.sha256(json.dumps(resultado,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
    return resultado


def exportar_origenes(resultado):return io.BytesIO(json.dumps(resultado,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8"))
