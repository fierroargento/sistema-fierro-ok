"""Expediente final en memoria para evaluar, nunca ejecutar, la transicion desde DUX."""
import hashlib,io,json
def _leer(archivo,nombre):
 contenido=archivo.read() if hasattr(archivo,"read") else archivo
 if not isinstance(contenido,bytes) or not contenido or len(contenido)>3_000_000:raise ValueError(f"{nombre} debe ser un JSON de hasta 3 MB.")
 try:d=json.loads(contenido.decode("utf-8-sig"))
 except (UnicodeDecodeError,json.JSONDecodeError) as error:raise ValueError(f"{nombre} no es JSON UTF-8 valido.") from error
 if not isinstance(d,dict):raise ValueError(f"{nombre} debe contener un objeto JSON.")
 return d
def _firma(documento,campo,nombre):
 declarada=documento.get(campo);base={k:v for k,v in documento.items() if k!=campo};calculada=hashlib.sha256(json.dumps(base,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
 if not declarada or declarada!=calculada:raise ValueError(f"La firma de {nombre} no coincide.")
 return declarada
def construir_expediente(plan_archivo,ensayo_archivo,certificacion_archivo,*,organizacion_id):
 plan=_leer(plan_archivo,"Plan de corte");ensayo=_leer(ensayo_archivo,"Ensayo de corte");cert=_leer(certificacion_archivo,"Certificacion SaaS")
 for nombre,d in (("plan",plan),("ensayo",ensayo),("certificacion",cert)):
  if d.get("organizacion_id")!=int(organizacion_id):raise ValueError(f"El {nombre} pertenece a otro tenant.")
 firmas={"plan":_firma(plan,"huella_plan","plan"),"ensayo":_firma(ensayo,"huella_ensayo","ensayo"),"certificacion":_firma(cert,"huella_expediente","certificacion")}
 hallazgos=[]
 if not plan.get("apto_para_ensayo"):hallazgos.append({"codigo":"plan_bloqueado","detalle":"El plan de corte presenta bloqueos."})
 if plan.get("autorizacion_corte") is not False:hallazgos.append({"codigo":"plan_ejecutable","detalle":"El plan no conserva la frontera no ejecutable."})
 if not ensayo.get("aprobado"):hallazgos.append({"codigo":"ensayo_con_diferencias","detalle":"Los snapshots no coinciden."})
 if ensayo.get("autorizacion_corte") is not False:hallazgos.append({"codigo":"ensayo_ejecutable","detalle":"El ensayo no conserva la frontera no ejecutable."})
 if not cert.get("aprobada"):hallazgos.append({"codigo":"saas_no_certificado","detalle":"El expediente SaaS no esta aprobado."})
 resultado={"organizacion_id":int(organizacion_id),"modo":"expediente_transicion_dux_no_ejecutable","decision_recomendada":"apto_para_ensayo_controlado" if not hallazgos else "bloqueado","autorizacion_corte_real":False,"firmas_origen":firmas,"resumen":{"dominios_planificados":plan.get("resumen",{}).get("dominios",0),"diferencias_productos":ensayo.get("resumen",{}).get("diferencias_productos",0),"componentes_certificados":cert.get("resumen",{}).get("componentes_identificados",0),"hallazgos":len(hallazgos)},"hallazgos":hallazgos,"controles":{"dux_desconectado":0,"integraciones_activadas":0,"stock_modificado":0,"precios_publicados":0,"pedidos_modificados":0,"facturas_emitidas":0,"pagos_registrados":0,"configuracion_modificada":0,"documentos_persistidos":0,"conexiones_externas":0}}
 resultado["huella_expediente_transicion"]=hashlib.sha256(json.dumps(resultado,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest();return resultado
def exportar(resultado):return io.BytesIO(json.dumps(resultado,ensure_ascii=False,sort_keys=True,indent=2).encode())
