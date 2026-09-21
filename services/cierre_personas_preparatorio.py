"""Competencias, cobertura y expediente final de personas sin efectos laborales."""
import hashlib,io,json
from collections import defaultdict
from datetime import date

def registrar_competencia(datos,*,empleado,organizacion_id,unidad_negocio_id,Competencia,db_session):
    if empleado is None or empleado.tipo_registro!="empleado" or int(empleado.organizacion_id)!=int(organizacion_id) or int(empleado.unidad_negocio_id)!=int(unidad_negocio_id):raise ValueError("El empleado no pertenece al contexto activo.")
    codigo=str(datos.get("codigo") or "").strip();nombre=str(datos.get("nombre") or "").strip()
    try:nivel=int(datos.get("nivel"));vence=date.fromisoformat(str(datos.get("vence_el"))) if datos.get("vence_el") else None
    except ValueError:raise ValueError("Nivel o vencimiento invalido.")
    if not codigo or not nombre or not 1<=nivel<=5:raise ValueError("Codigo, nombre y nivel entre uno y cinco son obligatorios.")
    c=Competencia(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,empleado_id=empleado.id,codigo=codigo,nombre=nombre,nivel=nivel,vence_el=vence,verificada=False,habilita_asignacion=False,observacion=str(datos.get("observacion") or "").strip() or None)
    db_session.add(c);db_session.commit();return c

def expediente_personas(*,organizacion_id,unidad_negocio_id,empleados,turnos,novedades,competencias,hoy=None):
    hoy=hoy or date.today();ids={int(e.id) for e in empleados if e.tipo_registro=="empleado" and int(e.organizacion_id)==int(organizacion_id) and int(e.unidad_negocio_id)==int(unidad_negocio_id)};hallazgos=[];cobertura=defaultdict(lambda:{"empleados":set(),"minutos":0});turnos_validos=[]
    for t in turnos:
        if int(t.organizacion_id)!=int(organizacion_id) or int(t.unidad_negocio_id)!=int(unidad_negocio_id):continue
        if int(t.empleado_id) not in ids:hallazgos.append({"codigo":"empleado_fuera_contexto","turno_id":t.id});continue
        if t.confirmado or t.afecta_nomina:hallazgos.append({"codigo":"turno_con_impacto","turno_id":t.id});continue
        if t.estado=="planificado":
            turnos_validos.append(t);clave=(t.inicio.date().isoformat(),t.sector);cobertura[clave]["empleados"].add(int(t.empleado_id));cobertura[clave]["minutos"]+=int((t.fin-t.inicio).total_seconds()/60)
    ausencias=[];minutos_extra=0
    for n in novedades:
        if int(n.organizacion_id)!=int(organizacion_id) or int(n.unidad_negocio_id)!=int(unidad_negocio_id):continue
        if n.aprobada or n.afecta_nomina:hallazgos.append({"codigo":"novedad_con_impacto","novedad_id":n.id});continue
        if n.estado=="propuesta" and n.tipo in {"ausencia","licencia"}:ausencias.append(n)
        if n.estado=="propuesta" and n.tipo=="horas_extra":minutos_extra+=int(n.minutos_propuestos)
    for t in turnos_validos:
        for n in ausencias:
            if int(n.empleado_id)==int(t.empleado_id) and n.fecha_desde<=t.inicio.date()<=n.fecha_hasta:hallazgos.append({"codigo":"turno_con_ausencia","turno_id":t.id,"novedad_id":n.id})
    vencimientos=[]
    for c in competencias:
        if int(c.organizacion_id)!=int(organizacion_id) or int(c.unidad_negocio_id)!=int(unidad_negocio_id) or int(c.empleado_id) not in ids:continue
        if c.verificada or c.habilita_asignacion:hallazgos.append({"codigo":"competencia_habilitante","competencia_id":c.id})
        if c.vence_el:vencimientos.append({"competencia_id":c.id,"empleado_id":c.empleado_id,"vence_el":c.vence_el.isoformat(),"estado":"vencida" if c.vence_el<hoy else ("proxima" if (c.vence_el-hoy).days<=30 else "vigente_no_verificada")})
    filas=[{"fecha":k[0],"sector":k[1],"empleados":len(v["empleados"]),"minutos_planificados":v["minutos"]} for k,v in sorted(cobertura.items())]
    r={"organizacion_id":int(organizacion_id),"unidad_negocio_id":int(unidad_negocio_id),"modo":"expediente_personas_no_laboral","cobertura_diaria":filas,"vencimientos_competencias":sorted(vencimientos,key=lambda x:(x["vence_el"],x["competencia_id"])),"minutos_extra_propuestos":minutos_extra,"hallazgos":hallazgos,"aprobado":not hallazgos,"controles":{"fichajes":0,"novedades_aprobadas":0,"asignaciones_habilitadas":0,"liquidaciones":0,"costos_modificados":0,"conexiones_externas":0}}
    r["huella_expediente"]=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(",",":")).encode()).hexdigest();return r
def exportar_expediente(r):return io.BytesIO(json.dumps(r,ensure_ascii=False,sort_keys=True,indent=2).encode())
