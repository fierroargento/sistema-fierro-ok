import json
from pathlib import Path

from services.control_motores_comerciales import (
    construir_control_motores,
    exportar_control_motores,
)


class Obj:
    def __init__(self, **datos):
        self.__dict__.update(datos)


def lista(lista_id=1):
    return Obj(id=lista_id, nombre="Mercado Libre")


def politica(lista_id=1, **cambios):
    datos = dict(
        id=10, lista_precio_id=lista_id, vigente=True, comision_pct=16,
        incremento_redondeo_centavos=100, flete_venta_centavos=50000,
        cargo_fijo_centavos=30000,
    )
    datos.update(cambios)
    return Obj(**datos)


def regla(lista_id=1, **cambios):
    datos = dict(
        id=20, lista_precio_id=lista_id, vigente=True, comision_pct=16,
        incremento_redondeo_centavos=100,
        costo_envio_default_centavos=50000,
        tramos=[Obj(precio_desde_centavos=0, cargo_fijo_centavos=30000)],
    )
    datos.update(cambios)
    return Obj(**datos)


def test_motores_equivalentes_habilitan_evaluar_retiro_sin_ejecutarlo():
    items = [
        Obj(lista_precio_id=1, vigente=False),
        Obj(lista_precio_id=1, vigente=True),
    ]
    resultado = construir_control_motores([lista()], [politica()], [regla()], items)
    fila = resultado["filas"][0]
    assert fila["estado"] == "alineada"
    assert fila["retiro_legacy_habilitado"] is True
    assert fila["precios_historicos"] == 2 and fila["precios_vigentes"] == 1
    assert resultado["escrituras"] == resultado["migraciones"] == 0


def test_diferencias_economicas_impiden_retirar_motor_historico():
    nueva = regla(
        comision_pct=18, incremento_redondeo_centavos=500,
        costo_envio_default_centavos=70000,
        tramos=[Obj(precio_desde_centavos=0, cargo_fijo_centavos=40000)],
    )
    fila = construir_control_motores([lista()], [politica()], [nueva], [])["filas"][0]
    assert fila["estado"] == "divergente"
    assert set(fila["diferencias"]) == {
        "comision_distinta", "redondeo_distinto",
        "flete_envio_distinto", "cargo_fijo_distinto",
    }
    assert fila["retiro_legacy_habilitado"] is False


def test_motor_historico_sin_regla_nueva_queda_bloqueado():
    resultado = construir_control_motores([lista()], [politica()], [], [])
    assert resultado["resumen"]["bloqueadas"] == 1
    assert resultado["filas"][0]["bloqueos"] == ["solo_motor_historico"]


def test_duplicados_vigentes_se_detectan_sin_elegir_un_registro_arbitrario():
    resultado = construir_control_motores(
        [lista()], [politica(), politica(id=11)], [regla(), regla(id=21)], [],
    )
    fila = resultado["filas"][0]
    assert fila["estado"] == "bloqueada"
    assert fila["politica_legacy_id"] is None
    assert fila["regla_canal_id"] is None
    assert len(fila["bloqueos"]) == 2


def test_exportacion_es_utf8_firmada_y_reproducible():
    primero = construir_control_motores([lista()], [politica()], [regla()], [])
    segundo = construir_control_motores([lista()], [politica()], [regla()], [])
    assert primero["firma_evidencia"] == segundo["firma_evidencia"]
    exportado = json.loads(exportar_control_motores(primero).read().decode("utf-8"))
    assert exportado == primero
    assert len(exportado["firma_evidencia"]) == 64


def test_panel_y_ruta_exponen_control_tenant_sin_operaciones_externas():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    consultas = Path("services/comercial_consultas.py").read_text(encoding="utf-8")
    servicio = Path("services/control_motores_comerciales.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    assert '"control_motores": control_motores' in consultas
    assert "/admin/comercial/control-motores/exportar" in rutas
    assert "organizacion.id, unidad_activa.id" in rutas
    assert "Convivencia de motores comerciales" in panel
    assert "No migra, desactiva ni publica precios" in panel
    for prohibido in ("db.session", "requests.", "http://", "https://"):
        assert prohibido not in servicio
