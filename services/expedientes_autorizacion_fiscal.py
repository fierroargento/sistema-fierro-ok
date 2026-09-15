"""Certifica expedientes fiscales internos sin solicitar CAE ni transportar datos."""
import hashlib,io,json

def evaluar_borrador(borrador, *, organizacion_id):
    bloqueos=[];entidad=getattr(borrador,"entidad_fiscal",None);punto=getattr(borrador,"punto_venta",None);tipo=getattr(borrador,"tipo_comprobante",None);config=getattr(punto,"configuracion",None)
    if borrador.organizacion_id!=organizacion_id:bloqueos.append("borrador_ajeno")
    if borrador.estado!="listo":bloqueos.append("estado_no_listo")
    if borrador.cae or borrador.numero_autorizado:bloqueos.append("autorizacion_preexistente")
    if not entidad or entidad.organizacion_id!=organizacion_id or not entidad.activa or not entidad.facturacion_habilitada:bloqueos.append("entidad_no_habilitada")
    if not punto or punto.organizacion_id!=organizacion_id or punto.entidad_fiscal_id!=getattr(entidad,"id",None) or punto.estado!="activo":bloqueos.append("punto_no_habilitado")
    if getattr(punto,"emision_real_habilitada",False):bloqueos.append("emision_real_indebida")
    if not config or config.organizacion_id!=organizacion_id or config.entidad_fiscal_id!=getattr(entidad,"id",None) or config.estado not in {"configurada","prueba"}:bloqueos.append("configuracion_no_preparada")
    if not tipo or tipo.punto_venta_fiscal_id!=getattr(punto,"id",None) or not tipo.activo:bloqueos.append("tipo_no_habilitado")
    items=list(getattr(borrador,"items",[]) or []);neto=sum(int(x.neto_centavos) for x in items);iva=sum(int(x.iva_centavos) for x in items);total=sum(int(x.total_centavos) for x in items)
    if not items:bloqueos.append("sin_items")
    if (neto,iva,total)!=(borrador.neto_centavos,borrador.iva_centavos,borrador.total_centavos):bloqueos.append("totales_inconsistentes")
    evidencia={"organizacion_id":organizacion_id,"borrador_id":borrador.id,"referencia":borrador.referencia_externa,"entidad_fiscal_id":getattr(entidad,"id",None),"punto_venta_fiscal_id":getattr(punto,"id",None),"tipo_comprobante_fiscal_id":getattr(tipo,"id",None),"receptor":borrador.receptor_nombre,"documento":borrador.receptor_documento,"moneda":borrador.moneda,"neto_centavos":neto,"iva_centavos":iva,"total_centavos":total,"items":len(items),"bloqueos":bloqueos,"puede_emitir":False,"acciones_externas":0}
    evidencia["huella"]=hashlib.sha256(json.dumps(evidencia,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest();return evidencia

def listar_candidatos(BorradorComprobanteFiscal,*,organizacion_id):return BorradorComprobanteFiscal.query.filter_by(organizacion_id=organizacion_id,estado="listo").order_by(BorradorComprobanteFiscal.id.desc()).all()
def listar_expedientes(ExpedienteAutorizacionFiscal,*,organizacion_id):return ExpedienteAutorizacionFiscal.query.filter_by(organizacion_id=organizacion_id).order_by(ExpedienteAutorizacionFiscal.id.desc()).all()
def certificar(borrador,*,organizacion_id,usuario,ExpedienteAutorizacionFiscal,EventoFiscal,db_session):
    evidencia=evaluar_borrador(borrador,organizacion_id=organizacion_id)
    if evidencia["bloqueos"]:raise ValueError("El borrador no supera la certificación: "+", ".join(evidencia["bloqueos"])+".")
    if ExpedienteAutorizacionFiscal.query.filter_by(organizacion_id=organizacion_id,borrador_comprobante_fiscal_id=borrador.id).first():raise ValueError("El borrador ya tiene un expediente fiscal.")
    try:
        expediente=ExpedienteAutorizacionFiscal(organizacion_id=organizacion_id,borrador_comprobante_fiscal_id=borrador.id,estado="certificado",huella=evidencia["huella"],evidencia_json=json.dumps(evidencia,ensure_ascii=False,sort_keys=True,separators=(",",":")),puede_emitir=False,creado_por=getattr(usuario,"username","admin"));db_session.add(expediente)
        db_session.add(EventoFiscal(organizacion_id=organizacion_id,borrador_comprobante_fiscal_id=borrador.id,tipo="expediente_certificado",detalle="Expediente interno certificado sin solicitud de CAE.",referencia_externa=borrador.referencia_externa,usuario=getattr(usuario,"username","admin")));db_session.commit()
    except Exception:db_session.rollback();raise
    return expediente
def exportar(expediente):return io.BytesIO(json.dumps({"expediente_id":expediente.id,"estado":expediente.estado,"huella":expediente.huella,"puede_emitir":False,"evidencia":json.loads(expediente.evidencia_json)},ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8"))
