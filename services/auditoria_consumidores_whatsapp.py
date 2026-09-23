"""Inventario estático y de solo lectura de accesos a WhatsAppMensaje."""

from pathlib import Path


ARCHIVOS_EXCLUIDOS = {
    "services/auditoria_consumidores_whatsapp.py",
}

ARCHIVOS_CONTROLADOS = {
    "services/acceso_tenant_whatsapp.py",
    "services/asignacion_tenant_whatsapp.py",
    "services/certificacion_whatsapp_tenant.py",
    "modules/whatsapp/runtime.py",
    "modules/whatsapp/webhook.py",
    "services/canal_manager.py",
    "services/wa_general.py",
    "services/wa_general_bot.py",
    "services/whatsapp_idempotencia.py",
}


def _grupo(ruta):
    ruta = ruta.replace("\\", "/")
    if ruta == "app.py":
        return "legado_monolitico"
    if "webhook" in ruta:
        return "webhook"
    if "scheduler" in ruta or "automation" in ruta:
        return "automatizacion"
    if ruta.startswith("modules/"):
        return "modulo"
    return "servicio"


def auditar_fuentes_consumidores_whatsapp(fuentes):
    hallazgos = []
    controlados = []
    por_grupo = {}
    por_archivo = {}
    for ruta, contenido in fuentes or []:
        ruta = str(ruta).replace("\\", "/")
        if ruta in ARCHIVOS_EXCLUIDOS or ruta.startswith("tests/"):
            continue
        for numero, linea in enumerate(str(contenido).splitlines(), start=1):
            if "WhatsAppMensaje.query" not in linea:
                continue
            registro = {
                "archivo": ruta,
                "linea": numero,
                "grupo": _grupo(ruta),
                "expresion": linea.strip()[:240],
            }
            if ruta in ARCHIVOS_CONTROLADOS:
                controlados.append(registro)
                continue
            grupo = registro["grupo"]
            por_grupo[grupo] = por_grupo.get(grupo, 0) + 1
            por_archivo[ruta] = por_archivo.get(ruta, 0) + 1
            hallazgos.append(registro)
    return {
        "total": len(hallazgos),
        "controlados": len(controlados),
        "archivos": len(por_archivo),
        "por_grupo": por_grupo,
        "por_archivo": dict(sorted(por_archivo.items())),
        "hallazgos": hallazgos[:200],
        "detalle_controlados": controlados,
        "hallazgos_limitados": len(hallazgos) > 200,
        "aprobada": not hallazgos,
        "escrituras_realizadas": 0,
        "integraciones_habilitables": False,
    }


def auditar_consumidores_whatsapp(raiz=None):
    raiz = Path(raiz or Path(__file__).resolve().parents[1])
    fuentes = []
    for archivo in sorted(raiz.rglob("*.py")):
        relativo = archivo.relative_to(raiz).as_posix()
        if relativo.startswith("tests/") or "__pycache__" in archivo.parts:
            continue
        try:
            contenido = archivo.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            continue
        fuentes.append((relativo, contenido))
    return auditar_fuentes_consumidores_whatsapp(fuentes)
