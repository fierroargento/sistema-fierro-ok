"""Certificación integral del CRM por tenant, sin mensajes ni conexiones."""
import hashlib,io,json,re

ESTADOS_CLIENTE={"potencial","cliente","inactivo"};ESTADOS_OPORTUNIDAD={"abierta","ganada","perdida","cancelada"};ESTADOS_ACTIVIDAD={"pendiente","completada","cancelada"}

def certificar_crm(*,organizacion_id,modulo,unidades,etapas,clientes,identidades,oportunidades,actividades):
    unidades=[x for x in unidades if x.organizacion_id==organizacion_id];etapas=[x for x in etapas if x.organizacion_id==organizacion_id];clientes=[x for x in clientes if x.organizacion_id==organizacion_id];identidades=[x for x in identidades if x.organizacion_id==organizacion_id];oportunidades=[x for x in oportunidades if x.organizacion_id==organizacion_id];actividades=[x for x in actividades if x.organizacion_id==organizacion_id]
    unidad_ids={x.id for x in unidades};etapa_ids={x.id for x in etapas};cliente_ids={x.id for x in clientes};oportunidad_ids={x.id for x in oportunidades};hallazgos=[]
    def agregar(codigo,entidad,id,detalle):hallazgos.append({"codigo":codigo,"entidad":entidad,"id":id,"detalle":detalle})
    codigos=set();documentos={};emails={};telefonos={}
    for c in clientes:
        codigo=str(c.codigo or "").strip().lower()
        if not codigo or codigo in codigos:agregar("codigo_cliente_duplicado","cliente",c.id,"El código está vacío o repetido.")
        codigos.add(codigo)
        if c.unidad_negocio_id is not None and c.unidad_negocio_id not in unidad_ids:agregar("unidad_cliente_ajena","cliente",c.id,"La unidad no pertenece al tenant.")
        if c.estado not in ESTADOS_CLIENTE:agregar("estado_cliente_invalido","cliente",c.id,"El estado comercial no es válido.")
        for nombre,valor,indice in (("documento",c.documento,documentos),("email",c.email,emails),("telefono",c.telefono,telefonos)):
            clave=str(valor or "").strip().lower()
            if clave:
                if clave in indice and indice[clave]!=c.id:agregar(f"{nombre}_duplicado","cliente",c.id,f"El {nombre} coincide con otro cliente del tenant.")
                indice[clave]=c.id
        if c.email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",str(c.email).strip()):agregar("email_invalido","cliente",c.id,"El correo electrónico no tiene formato válido.")
    claves_identidad={}
    for i in identidades:
        if i.cliente_crm_id not in cliente_ids:agregar("identidad_huerfana","identidad",i.id,"La identidad no pertenece a un cliente del tenant.")
        clave=(str(i.canal or "").lower(),str(i.identificador_externo or "").strip())
        if not clave[0] or not clave[1]:agregar("identidad_incompleta","identidad",i.id,"Falta canal o identificador externo.")
        elif clave in claves_identidad and claves_identidad[clave]!=i.cliente_crm_id:agregar("identidad_duplicada","identidad",i.id,"La identidad está asignada a más de un cliente.")
        claves_identidad[clave]=i.cliente_crm_id
    for o in oportunidades:
        if o.cliente_crm_id not in cliente_ids:agregar("oportunidad_huerfana","oportunidad",o.id,"El cliente no pertenece al tenant.")
        if o.unidad_negocio_id is not None and o.unidad_negocio_id not in unidad_ids:agregar("unidad_oportunidad_ajena","oportunidad",o.id,"La unidad no pertenece al tenant.")
        if o.etapa_crm_id is not None and o.etapa_crm_id not in etapa_ids:agregar("etapa_oportunidad_ajena","oportunidad",o.id,"La etapa no pertenece al tenant.")
        if o.estado not in ESTADOS_OPORTUNIDAD or not 0<=int(o.probabilidad or 0)<=100 or int(o.importe_estimado_centavos or 0)<0:agregar("economia_oportunidad_invalida","oportunidad",o.id,"Estado, probabilidad o importe inválidos.")
    for a in actividades:
        if a.cliente_crm_id not in cliente_ids or (a.oportunidad_crm_id is not None and a.oportunidad_crm_id not in oportunidad_ids):agregar("actividad_huerfana","actividad",a.id,"Cliente u oportunidad fuera del tenant.")
        if a.estado not in ESTADOS_ACTIVIDAD:agregar("estado_actividad_invalido","actividad",a.id,"El estado de actividad no es válido.")
        if a.estado=="completada" and not a.fecha_completada:agregar("actividad_completada_sin_fecha","actividad",a.id,"Falta la fecha de finalización.")
    resumen={"unidades":len(unidades),"etapas":len(etapas),"clientes":len(clientes),"identidades":len(identidades),"oportunidades":len(oportunidades),"actividades":len(actividades),"hallazgos":len(hallazgos)}
    controles={"aislamiento_tenant":True,"identidades_unicas":not any(x["codigo"]=="identidad_duplicada" for x in hallazgos),"relaciones_integras":not any("huerfana" in x["codigo"] or "_ajena" in x["codigo"] for x in hallazgos),"calidad_contactos":not any(x["codigo"] in {"documento_duplicado","email_duplicado","telefono_duplicado","email_invalido"} for x in hallazgos),"automatizaciones":False,"mensajes_enviados":0,"acciones_externas":0,"escrituras":0}
    base={"organizacion_id":organizacion_id,"modulo_estado":getattr(modulo,"estado","desactivado") if modulo else "desactivado","resumen":resumen,"controles":controles,"hallazgos":hallazgos,"aprobada":not hallazgos,"modo":"offline"};base["huella"]=hashlib.sha256(json.dumps(base,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest();return base
def exportar_certificacion(resultado):return io.BytesIO(json.dumps(resultado,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8"))
