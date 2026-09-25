"""Certifica configuración de staging aislada sin revelar secretos."""
import hashlib
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from services.seguridad_entorno import diagnostico_laboratorio_desconectado


MAESTRAS = (
    "CONEXIONES_EXTERNAS_HABILITADAS", "EFECTOS_EXTERNOS_HABILITADOS",
    "WEBHOOKS_HABILITADOS", "SCHEDULER_ENABLED", "BOOTSTRAP_BASE_DATOS_HABILITADO",
    "OPERACIONES_MASIVAS_HABILITADAS",
)
TRUE = {"1", "true", "si", "sí", "yes", "on"}
CREDENCIAL_PATRON = re.compile(
    r"(?:^|_)(?:TOKEN|SECRET|PASSWORD|PASS|API_KEY|CLIENT_ID|DSN)(?:_|$)",
    re.I,
)
CREDENCIALES_PORTADORAS = {
    "CLOUDINARY_URL", "TN_STORE_ID", "WHATSAPP_PHONE_NUMBER_ID",
}
CREDENCIALES_PERMITIDAS = {
    "SECRET_KEY", "DATABASE_URL", "STAGING_DATABASE_MARKER",
    "BASE_PRODUCTIVA_HUELLA_SHA256", "BASE_PRODUCTIVA_IDENTIDAD_SHA256",
    "BASE_PRODUCTIVA_IDENTIDADES_SHA256",
}


def huella_base(url):
    valor = str(url or "").strip()
    return hashlib.sha256(valor.encode()).hexdigest() if valor else ""


def identidad_base(url):
    """Huella canónica Render: recurso, base y usuario; ignora alias y clave."""
    try:
        partes = urlsplit(str(url or "").strip())
        esquema = "postgresql" if partes.scheme in {"postgres", "postgresql"} else partes.scheme
        host = (partes.hostname or "").lower()
        usuario = (partes.username or "").lower()
        nombre = (partes.path or "").strip("/").lower()
        recurso = host.split(".", 1)[0]
        if esquema != "postgresql" or not recurso or not nombre or not usuario:
            return ""
        identidad = f"postgresql|{recurso}|{nombre}|{usuario}"
        return hashlib.sha256(identidad.encode()).hexdigest()
    except (TypeError, ValueError):
        return ""


def certificar(configuracion=None):
    env = configuracion if configuracion is not None else os.environ
    entorno = str(env.get("SISTEMA_FIERRO_ENTORNO", "")).strip().lower()
    forzado = str(env.get("MODO_LABORATORIO_DESCONECTADO", "")).strip().lower() in TRUE
    base = str(env.get("DATABASE_URL", "")).strip()
    productiva = str(env.get("BASE_PRODUCTIVA_HUELLA_SHA256", "")).strip().lower()
    identidades_productivas = {
        item.strip().lower()
        for item in str(env.get("BASE_PRODUCTIVA_IDENTIDADES_SHA256", "")).replace(",", " ").split()
        if item.strip()
    }
    marcador = str(env.get("STAGING_DATABASE_MARKER", "")).strip()
    rama = str(env.get("SISTEMA_FIERRO_RAMA_DESPLIEGUE", "")).strip()
    proposito = str(env.get("SISTEMA_FIERRO_PROPOSITO", "")).strip().lower()
    secreto = str(env.get("SECRET_KEY", ""))
    hallazgos = []
    if entorno != "staging":hallazgos.append({"codigo":"entorno_no_staging","detalle":"El entorno de ensayo debe declararse staging."})
    if not forzado:hallazgos.append({"codigo":"candado_no_forzado","detalle":"Falta activar el candado superior del laboratorio."})
    if not base:hallazgos.append({"codigo":"base_ausente","detalle":"El laboratorio no tiene DATABASE_URL propia."})
    elif not (base.startswith("postgresql://") or base.startswith("postgres://")):hallazgos.append({"codigo":"base_no_postgresql","detalle":"El laboratorio debe utilizar PostgreSQL separado."})
    actual = huella_base(base)
    identidad_actual = identidad_base(base)
    if not productiva or len(productiva) != 64:hallazgos.append({"codigo":"huella_productiva_ausente","detalle":"Falta la huella SHA-256 de referencia de la base productiva."})
    elif actual and actual == productiva:hallazgos.append({"codigo":"base_productiva_reutilizada","detalle":"DATABASE_URL coincide con la base productiva y debe reemplazarse."})
    if not identidades_productivas or any(len(item) != 64 for item in identidades_productivas):hallazgos.append({"codigo":"identidades_productivas_ausentes","detalle":"Falta la lista canónica de identidades productivas (interna y externa)."})
    elif identidad_actual and identidad_actual in identidades_productivas:hallazgos.append({"codigo":"identidad_base_productiva_reutilizada","detalle":"La identidad canónica de la base coincide con producción."})
    if len(marcador) < 32:hallazgos.append({"codigo":"marcador_staging_ausente","detalle":"Falta STAGING_DATABASE_MARKER exclusivo de esta instalación."})
    activas = [nombre for nombre in MAESTRAS if str(env.get(nombre, "")).strip().lower() in TRUE]
    if activas:hallazgos.append({"codigo":"llaves_maestras_activas","detalle":"Deben permanecer en false: " + ", ".join(activas) + "."})
    if rama != "integracion-saas-2026-09":hallazgos.append({"codigo":"rama_incorrecta","detalle":"El ensayo debe desplegar exclusivamente integracion-saas-2026-09."})
    if proposito != "uat_desconectada":hallazgos.append({"codigo":"proposito_invalido","detalle":"El propósito debe declararse uat_desconectada."})
    if len(secreto) < 32:hallazgos.append({"codigo":"secret_key_debil","detalle":"SECRET_KEY debe ser exclusiva y tener al menos 32 caracteres."})
    credenciales_presentes = sorted(
        nombre for nombre, valor in env.items()
        if not nombre.startswith("BASH_FUNC_")
        and nombre not in CREDENCIALES_PERMITIDAS
        and (CREDENCIAL_PATRON.search(nombre) or nombre in CREDENCIALES_PORTADORAS)
        and str(valor or "").strip()
    )
    if credenciales_presentes:hallazgos.append({"codigo":"credenciales_externas_presentes","detalle":"El laboratorio desconectado no debe recibir credenciales externas: " + ", ".join(credenciales_presentes) + "."})
    modo_archivos = str(env.get("ALMACENAMIENTO_ARCHIVOS", "")).strip().lower()
    raiz_archivos = str(env.get("STAGING_UPLOAD_ROOT", "")).strip()
    if modo_archivos != "local_aislado":hallazgos.append({"codigo":"almacenamiento_no_aislado","detalle":"Staging debe usar ALMACENAMIENTO_ARCHIVOS=local_aislado."})
    if not raiz_archivos or not Path(raiz_archivos).is_absolute():hallazgos.append({"codigo":"raiz_archivos_invalida","detalle":"STAGING_UPLOAD_ROOT debe ser una ruta absoluta exclusiva de staging."})
    diagnostico = diagnostico_laboratorio_desconectado() if configuracion is None else None
    return {"modo":"certificacion_entorno_ensayo_sin_secretos","aprobado":not hallazgos,"entorno":entorno,"proposito":proposito,"rama_despliegue":rama,"laboratorio_forzado":forzado,"base_configurada":bool(base),"base_separada":bool(actual and productiva and len(productiva)==64 and actual!=productiva and identidad_actual and identidades_productivas and identidad_actual not in identidades_productivas),"secret_key_configurada":len(secreto)>=32,"huella_base_ensayo":actual,"identidad_base_ensayo":identidad_actual,"marcador_configurado":len(marcador)>=32,"almacenamiento_aislado":modo_archivos=="local_aislado" and bool(raiz_archivos) and Path(raiz_archivos).is_absolute(),"hallazgos":hallazgos,"controles":{"credenciales_expuestas":0,"conexiones_realizadas":0,"escrituras":0},"diagnostico_runtime":diagnostico}
