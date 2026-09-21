"""Plan firmado y no ejecutable para decidir el reemplazo futuro de DUX."""
import hashlib,io,json

DOMINIOS=("catalogo","costos","inventario","pedidos","mercado_libre","tienda_nube","facturacion","tesoreria","usuarios","respaldo_reversion")

def construir_plan(datos,*,organizacion_id):
    etapas=[];hallazgos=[]
    for dominio in DOMINIOS:
        validado=str(datos.get(dominio) or "").lower() in {"1","true","si","on"}
        responsable=str(datos.get(f"responsable_{dominio}") or "").strip()
        evidencia=str(datos.get(f"evidencia_{dominio}") or "").strip()
        etapas.append({"dominio":dominio,"validado":validado,"responsable":responsable,"evidencia":evidencia})
        if not validado:hallazgos.append({"codigo":"dominio_no_validado","dominio":dominio,"detalle":"Falta validar el dominio antes del corte."})
        if validado and not responsable:hallazgos.append({"codigo":"responsable_faltante","dominio":dominio,"detalle":"La validacion no tiene responsable."})
        if validado and not evidencia:hallazgos.append({"codigo":"evidencia_faltante","dominio":dominio,"detalle":"La validacion no tiene referencia de evidencia."})
    ventana=str(datos.get("ventana_corte") or "").strip();reversion=str(datos.get("plan_reversion") or "").strip();criterio=str(datos.get("criterio_exito") or "").strip()
    if not ventana:hallazgos.append({"codigo":"ventana_faltante","dominio":"gobierno","detalle":"Falta definir la ventana de corte."})
    if len(reversion)<20:hallazgos.append({"codigo":"reversion_incompleta","dominio":"gobierno","detalle":"El plan de reversion debe ser explicito."})
    if len(criterio)<20:hallazgos.append({"codigo":"criterio_incompleto","dominio":"gobierno","detalle":"Falta un criterio verificable de exito."})
    resultado={"organizacion_id":int(organizacion_id),"modo":"plan_corte_dux_no_ejecutable","apto_para_ensayo":not hallazgos,"autorizacion_corte":False,"ventana_corte":ventana,"plan_reversion":reversion,"criterio_exito":criterio,"etapas":etapas,"hallazgos":hallazgos,"resumen":{"dominios":len(DOMINIOS),"validados":sum(x["validado"] for x in etapas),"bloqueos":len(hallazgos)},"controles":{"dux_modificado":0,"canales_modificados":0,"integraciones_activadas":0,"precios_publicados":0,"stock_movido":0,"facturas_emitidas":0,"pagos_registrados":0,"escrituras":0}}
    resultado["huella_plan"]=hashlib.sha256(json.dumps(resultado,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest();return resultado

def exportar_plan(resultado):return io.BytesIO(json.dumps(resultado,ensure_ascii=False,sort_keys=True,indent=2).encode())
