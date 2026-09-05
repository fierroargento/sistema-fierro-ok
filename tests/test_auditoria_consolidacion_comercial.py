from pathlib import Path

from services.auditoria_consolidacion_comercial import construir_auditoria, exportar_auditoria, probar_circuito_sintetico


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


def control(**cambios):
    datos = dict(id=1, certificacion_interna_aprobada=True, recepcion_externa_habilitada=False, acciones_externas_habilitadas=False)
    datos.update(cambios); return Obj(**datos)


def auditar(**cambios):
    datos = dict(controles=[control()], eventos=[], ventas=[], movimientos=[], gestiones=[], costos_vigentes=1, reglas_economicas=1, reglas_canal=1, validaciones=1, identidades=1)
    datos.update(cambios); return construir_auditoria(**datos)


def test_circuito_sintetico_valida_adaptacion_correlacion_y_protecciones():
    assert all(probar_circuito_sintetico().values())


def test_estado_sano_resulta_apto_sin_habilitar_conexion():
    resultado = auditar()
    assert resultado["apto_consolidacion"] is True
    assert resultado["criticos"] == 0
    assert resultado["conexion_real_habilitada"] is False


def test_flags_externos_generan_bloqueo_critico():
    resultado = auditar(controles=[control(acciones_externas_habilitadas=True)])
    assert resultado["apto_consolidacion"] is False
    assert next(h for h in resultado["hallazgos"] if h["codigo"] == "bloqueos_externos")["nivel"] == "critico"


def test_detecta_eventos_huerfanos_y_duplicados():
    eventos = [Obj(control_id=99, canal="x", cuenta_codigo="c", tipo_evento="pago", referencia_evento="1"), Obj(control_id=99, canal="x", cuenta_codigo="c", tipo_evento="pago", referencia_evento="1")]
    resultado = auditar(eventos=eventos)
    codigos = {h["codigo"] for h in resultado["hallazgos"] if not h["cumple"]}
    assert {"eventos_huerfanos", "duplicados_staging"} <= codigos


def test_certificacion_e_identidades_son_advertencias_no_ocultas():
    resultado = auditar(controles=[control(certificacion_interna_aprobada=False)], identidades=0)
    assert resultado["advertencias"] == 2
    assert resultado["apto_consolidacion"] is True


def test_exportacion_devuelve_archivo_operable():
    assert hasattr(exportar_auditoria(auditar()), "read")


def test_auditoria_es_solo_lectura_y_sin_transporte():
    servicio = Path("services/auditoria_consolidacion_comercial.py").read_text(encoding="utf-8").lower()
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_auditoria_consolidacion.html").read_text(encoding="utf-8")
    assert "/admin/comercial/auditoria-consolidacion" in rutas
    assert "diagnóstico no corrige ni modifica" in panel
    for prohibido in ("db.session", "requests", "oauth", "webhook", "access_token", "http://", "https://"):
        assert prohibido not in servicio
