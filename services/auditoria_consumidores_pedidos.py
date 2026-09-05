"""Inventario estático y de solo lectura de accesos globales a Pedido."""

from pathlib import Path


ARCHIVOS_EXCLUIDOS = {
    "services/auditoria_consumidores_pedidos.py",
}

ARCHIVOS_PREPARATORIOS_PERMITIDOS = {
    "services/acceso_tenant_pedidos.py",
    "services/asignacion_tenant_pedidos.py",
    "services/certificacion_pedidos_tenant.py",
    "services/identidad_tenant_pedidos.py",
}


def _grupo(ruta):
    ruta = ruta.replace("\\", "/")
    if ruta == "app.py":
        return "legado_monolitico"
    if ruta.startswith("modules/automation/") or "scheduler" in ruta:
        return "automatizacion"
    if "webhook" in ruta:
        return "webhook"
    if "importacion" in ruta or "importador" in ruta:
        return "importador"
    if ruta.startswith("modules/"):
        return "modulo"
    return "servicio"


def auditar_fuentes_consumidores_pedidos(fuentes):
    """Recibe pares ruta/contenido y no escribe ni importa la aplicación."""
    hallazgos = []
    permitidos = []
    por_grupo = {}
    por_archivo = {}
    for ruta, contenido in fuentes or []:
        ruta = str(ruta).replace("\\", "/")
        if ruta in ARCHIVOS_EXCLUIDOS or ruta.startswith("tests/"):
            continue
        for numero, linea in enumerate(str(contenido).splitlines(), start=1):
            if "Pedido.query" not in linea:
                continue
            grupo = _grupo(ruta)
            registro = {
                "archivo": ruta,
                "linea": numero,
                "grupo": grupo,
                "expresion": linea.strip()[:240],
            }
            if ruta in ARCHIVOS_PREPARATORIOS_PERMITIDOS:
                permitidos.append(registro)
                continue
            por_grupo[grupo] = por_grupo.get(grupo, 0) + 1
            por_archivo[ruta] = por_archivo.get(ruta, 0) + 1
            hallazgos.append(registro)
    prioridades = [
        grupo for grupo in (
            "automatizacion", "webhook", "importador", "modulo",
            "servicio", "legado_monolitico",
        )
        if por_grupo.get(grupo)
    ]
    return {
        "total": len(hallazgos),
        "permitidos_preparatorios": len(permitidos),
        "archivos": len(por_archivo),
        "por_grupo": por_grupo,
        "por_archivo": dict(sorted(por_archivo.items())),
        "prioridades": prioridades,
        "hallazgos": hallazgos[:200],
        "detalle_permitidos": permitidos,
        "hallazgos_limitados": len(hallazgos) > 200,
        "aprobada": not hallazgos,
        "escrituras_realizadas": 0,
        "integraciones_habilitables": False,
    }


def auditar_consumidores_pedidos(raiz=None):
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
    return auditar_fuentes_consumidores_pedidos(fuentes)
