"""Control final, reproducible y de solo lectura del subsistema fiscal."""
import hashlib,io,json

def consultar_registros(modelo,*,organizacion_id):
    return modelo.query.filter_by(organizacion_id=organizacion_id).order_by(modelo.id.asc()).all()

def controlar(*,organizacion_id,modulo,entidades,configuraciones,puntos,tipos,borradores,eventos,lotes,expedientes):
    entidades=[x for x in entidades if x.organizacion_id==organizacion_id];configs=[x for x in configuraciones if x.organizacion_id==organizacion_id];puntos=[x for x in puntos if x.organizacion_id==organizacion_id];borradores=[x for x in borradores if x.organizacion_id==organizacion_id];eventos=[x for x in eventos if x.organizacion_id==organizacion_id];lotes=[x for x in lotes if x.organizacion_id==organizacion_id];expedientes=[x for x in expedientes if x.organizacion_id==organizacion_id]
    entidad_ids={x.id for x in entidades};config_ids={x.id for x in configs};punto_ids={x.id for x in puntos};borrador_ids={x.id for x in borradores}
    tipos=[x for x in tipos if x.punto_venta_fiscal_id in punto_ids]
    hallazgos=[]
    def agregar(codigo,entidad,identificador,detalle):hallazgos.append({"codigo":codigo,"entidad":entidad,"id":identificador,"detalle":detalle})
    if not modulo or modulo.estado not in {"prueba","activo"}:agregar("modulo_no_preparado","modulo",None,"El módulo fiscal no está en prueba.")
    for e in entidades:
        if not e.activa or not e.facturacion_habilitada:agregar("entidad_no_habilitada","entidad_fiscal",e.id,"La entidad no está habilitada administrativamente.")
        if len(str(e.cuit or ""))!=11 or not str(e.cuit or "").isdigit():agregar("cuit_invalido","entidad_fiscal",e.id,"El CUIT no tiene once dígitos.")
    for c in configs:
        if c.entidad_fiscal_id not in entidad_ids:agregar("configuracion_huerfana","configuracion_fiscal",c.id,"La configuración no pertenece a una entidad del tenant.")
        if c.estado not in {"configurada","prueba"}:agregar("configuracion_incompleta","configuracion_fiscal",c.id,"La configuración aún no está preparada.")
    for p in puntos:
        if p.entidad_fiscal_id not in entidad_ids or p.configuracion_fiscal_id not in config_ids:agregar("punto_huerfano","punto_venta",p.id,"El punto no conserva su cadena fiscal.")
        if p.emision_real_habilitada:agregar("emision_real_indebida","punto_venta",p.id,"La emisión real debe permanecer bloqueada.")
    for t in tipos:
        if t.punto_venta_fiscal_id not in punto_ids:agregar("tipo_huerfano","tipo_comprobante",t.id,"El tipo no pertenece al tenant.")
    expedientes_por_borrador={x.borrador_comprobante_fiscal_id:x for x in expedientes if x.estado=="certificado"}
    for b in borradores:
        if b.estado=="listo" and b.id not in expedientes_por_borrador:agregar("listo_sin_expediente","borrador",b.id,"El borrador listo aún no fue certificado.")
        if b.estado!="autorizado" and (b.cae or b.numero_autorizado):agregar("autorizacion_inconsistente","borrador",b.id,"Hay datos de autorización fuera del estado autorizado.")
    for x in expedientes:
        if x.borrador_comprobante_fiscal_id not in borrador_ids:agregar("expediente_huerfano","expediente",x.id,"El expediente no pertenece a un borrador del tenant.")
        if x.puede_emitir:agregar("expediente_ejecutable","expediente",x.id,"Un expediente interno no puede emitir.")
    resumen={"entidades":len(entidades),"configuraciones":len(configs),"puntos_venta":len(puntos),"tipos":len(tipos),"borradores":len(borradores),"borradores_listos":sum(x.estado=="listo" for x in borradores),"lotes":len(lotes),"expedientes":len(expedientes),"eventos":len(eventos),"hallazgos":len(hallazgos)}
    controles={"aislamiento_tenant":True,"integridad_cadena":not any(x["codigo"] in {"configuracion_huerfana","punto_huerfano","tipo_huerfano","expediente_huerfano"} for x in hallazgos),"borradores_cubiertos":not any(x["codigo"]=="listo_sin_expediente" for x in hallazgos),"autorizaciones_consistentes":not any(x["codigo"]=="autorizacion_inconsistente" for x in hallazgos),"emision_real_bloqueada":not any(x["codigo"] in {"emision_real_indebida","expediente_ejecutable"} for x in hallazgos),"acciones_externas":0,"escrituras":0}
    base={"organizacion_id":organizacion_id,"resumen":resumen,"controles":controles,"hallazgos":hallazgos,"aprobado":not hallazgos,"modo":"control_offline","emision_real":False}
    base["huella"]=hashlib.sha256(json.dumps(base,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest();return base

def exportar(resultado):return io.BytesIO(json.dumps(resultado,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8"))
