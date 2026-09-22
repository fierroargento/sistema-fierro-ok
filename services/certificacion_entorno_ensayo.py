"""Certifica configuración de staging aislada sin revelar secretos."""
import hashlib
import os

from services.seguridad_entorno import diagnostico_laboratorio_desconectado


MAESTRAS = (
    "CONEXIONES_EXTERNAS_HABILITADAS", "EFECTOS_EXTERNOS_HABILITADOS",
    "WEBHOOKS_HABILITADOS", "SCHEDULER_ENABLED", "BOOTSTRAP_BASE_DATOS_HABILITADO",
)
TRUE = {"1", "true", "si", "sí", "yes", "on"}


def huella_base(url):
    valor = str(url or "").strip()
    return hashlib.sha256(valor.encode()).hexdigest() if valor else ""


def certificar(configuracion=None):
    env = configuracion if configuracion is not None else os.environ
    entorno = str(env.get("SISTEMA_FIERRO_ENTORNO", "")).strip().lower()
    forzado = str(env.get("MODO_LABORATORIO_DESCONECTADO", "")).strip().lower() in TRUE
    base = str(env.get("DATABASE_URL", "")).strip()
    productiva = str(env.get("BASE_PRODUCTIVA_HUELLA_SHA256", "")).strip().lower()
    rama = str(env.get("SISTEMA_FIERRO_RAMA_DESPLIEGUE", "")).strip()
    proposito = str(env.get("SISTEMA_FIERRO_PROPOSITO", "")).strip().lower()
    secreto = str(env.get("SECRET_KEY", ""))
    hallazgos = []
    if entorno != "staging":hallazgos.append({"codigo":"entorno_no_staging","detalle":"El entorno de ensayo debe declararse staging."})
    if not forzado:hallazgos.append({"codigo":"candado_no_forzado","detalle":"Falta activar el candado superior del laboratorio."})
    if not base:hallazgos.append({"codigo":"base_ausente","detalle":"El laboratorio no tiene DATABASE_URL propia."})
    elif not (base.startswith("postgresql://") or base.startswith("postgres://")):hallazgos.append({"codigo":"base_no_postgresql","detalle":"El laboratorio debe utilizar PostgreSQL separado."})
    actual = huella_base(base)
    if not productiva or len(productiva) != 64:hallazgos.append({"codigo":"huella_productiva_ausente","detalle":"Falta la huella SHA-256 de referencia de la base productiva."})
    elif actual and actual == productiva:hallazgos.append({"codigo":"base_productiva_reutilizada","detalle":"DATABASE_URL coincide con la base productiva y debe reemplazarse."})
    activas = [nombre for nombre in MAESTRAS if str(env.get(nombre, "")).strip().lower() in TRUE]
    if activas:hallazgos.append({"codigo":"llaves_maestras_activas","detalle":"Deben permanecer en false: " + ", ".join(activas) + "."})
    if rama != "integracion-saas-2026-09":hallazgos.append({"codigo":"rama_incorrecta","detalle":"El ensayo debe desplegar exclusivamente integracion-saas-2026-09."})
    if proposito != "uat_desconectada":hallazgos.append({"codigo":"proposito_invalido","detalle":"El propósito debe declararse uat_desconectada."})
    if len(secreto) < 32:hallazgos.append({"codigo":"secret_key_debil","detalle":"SECRET_KEY debe ser exclusiva y tener al menos 32 caracteres."})
    diagnostico = diagnostico_laboratorio_desconectado() if configuracion is None else None
    return {"modo":"certificacion_entorno_ensayo_sin_secretos","aprobado":not hallazgos,"entorno":entorno,"proposito":proposito,"rama_despliegue":rama,"laboratorio_forzado":forzado,"base_configurada":bool(base),"base_separada":bool(actual and productiva and len(productiva)==64 and actual!=productiva),"secret_key_configurada":len(secreto)>=32,"huella_base_ensayo":actual,"hallazgos":hallazgos,"controles":{"credenciales_expuestas":0,"conexiones_realizadas":0,"escrituras":0},"diagnostico_runtime":diagnostico}
