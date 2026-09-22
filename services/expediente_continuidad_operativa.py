"""Expediente firmado de continuidad, no ejecutable y sin persistencia."""
import hashlib,io,json

FIRMAS={"respaldo":"huella_respaldo","ensayo":"huella_ensayo_restauracion","comparacion":"huella_comparacion"}
def _canonico(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode("utf-8")
def _leer(archivo,tipo):
 contenido=archivo.read() if hasattr(archivo,"read") else archivo
 if not isinstance(contenido,bytes) or not contenido or len(contenido)>20_000_000:raise ValueError(f"El archivo {tipo} debe ser JSON y no superar 20 MB.")
 try:d=json.loads(contenido.decode("utf-8-sig"))
 except (UnicodeDecodeError,json.JSONDecodeError) as e:raise ValueError(f"El archivo {tipo} no es JSON UTF-8 valido.") from e
 campo=FIRMAS[tipo];firma=d.get(campo);base={k:v for k,v in d.items() if k!=campo}
 if firma!=hashlib.sha256(_canonico(base)).hexdigest():raise ValueError(f"La firma del archivo {tipo} no coincide.")
 return d
def construir(respaldo,ensayo,comparacion,datos,*,organizacion_id,unidad_negocio_id):
 documentos={"respaldo":_leer(respaldo,"respaldo"),"ensayo":_leer(ensayo,"ensayo"),"comparacion":_leer(comparacion,"comparacion")};hallazgos=[]
 for tipo,d in documentos.items():
  if int(d.get("organizacion_id",-1))!=int(organizacion_id):raise ValueError(f"El archivo {tipo} pertenece a otro tenant.")
  if int(d.get("unidad_negocio_id",-1))!=int(unidad_negocio_id):raise ValueError(f"El archivo {tipo} pertenece a otra unidad.")
 if not documentos["respaldo"].get("respaldo_reconstruible",False):hallazgos.append({"codigo":"respaldo_no_reconstruible","detalle":"El respaldo declara cobertura incompleta."})
 if not documentos["ensayo"].get("aprobado",False):hallazgos.append({"codigo":"ensayo_no_aprobado","detalle":"El ensayo de restauracion contiene hallazgos."})
 if documentos["comparacion"].get("estado")!="sin_perdidas_detectadas":hallazgos.append({"codigo":"comparacion_con_perdidas","detalle":"La comparacion requiere revision antes del simulacro."})
 if documentos["comparacion"].get("origenes",{}).get("posterior",{}).get("huella")!=documentos["respaldo"].get("huella_respaldo"):hallazgos.append({"codigo":"respaldo_no_es_posterior","detalle":"La comparacion no termina en el respaldo presentado."})
 try:rpo=int(datos.get("rpo_minutos") or 0);rto=int(datos.get("rto_minutos") or 0)
 except (TypeError,ValueError):raise ValueError("RPO y RTO deben expresarse en minutos enteros.")
 responsable=str(datos.get("responsable") or "").strip();custodia=str(datos.get("custodia") or "").strip();reversion=str(datos.get("procedimiento_reversion") or "").strip();validacion=str(datos.get("criterio_validacion") or "").strip()
 if not 1<=rpo<=1440:hallazgos.append({"codigo":"rpo_invalido","detalle":"El RPO debe estar entre 1 y 1440 minutos."})
 if not 1<=rto<=1440:hallazgos.append({"codigo":"rto_invalido","detalle":"El RTO debe estar entre 1 y 1440 minutos."})
 for codigo,valor,minimo in (("responsable_faltante",responsable,3),("custodia_incompleta",custodia,10),("reversion_incompleta",reversion,30),("validacion_incompleta",validacion,20)):
  if len(valor)<minimo:hallazgos.append({"codigo":codigo,"detalle":"La definicion operativa es insuficiente."})
 resultado={"organizacion_id":int(organizacion_id),"unidad_negocio_id":int(unidad_negocio_id),"modo":"expediente_continuidad_no_ejecutable","estado":"apto_para_simulacro_humano" if not hallazgos else "bloqueado","restauracion_autorizada":False,"corte_dux_autorizado":False,"objetivos":{"rpo_minutos":rpo,"rto_minutos":rto},"gobierno":{"responsable":responsable,"custodia":custodia,"procedimiento_reversion":reversion,"criterio_validacion":validacion},"evidencias":{tipo:{"firma":d[FIRMAS[tipo]],"modo":d.get("modo")} for tipo,d in documentos.items()},"hallazgos":hallazgos,"resumen":{"evidencias":3,"hallazgos":len(hallazgos)},"controles":{"restauraciones":0,"escrituras":0,"cortes":0,"dux_modificado":0,"conexiones_externas":0}}
 resultado["huella_expediente_continuidad"]=hashlib.sha256(_canonico(resultado)).hexdigest();return resultado
def exportar(r):return io.BytesIO(json.dumps(r,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8"))

