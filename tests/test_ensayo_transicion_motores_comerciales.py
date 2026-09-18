import json
from pathlib import Path

from services.ensayo_transicion_motores_comerciales import (
    construir_ensayo_transicion,
    exportar_ensayo_transicion,
)


class Obj:
    def __init__(self, **datos):
        self.__dict__.update(datos)


def politica(**cambios):
    datos = dict(
        id=11, lista_precio_id=1, vigente=True, comision_pct=16,
        cargo_fijo_centavos=100000, flete_venta_centavos=500000,
        margen_objetivo_pct=20, incremento_redondeo_centavos=100,
    )
    datos.update(cambios)
    return Obj(**datos)


def test_traduccion_preserva_comision_cargo_flete_redondeo_y_margen_pendiente():
    ensayo = construir_ensayo_transicion(
        [Obj(id=1, nombre="ML")], [politica()], [], [],
    )
    candidato = ensayo["resultados"][0]["candidato"]
    assert candidato["comision_pct"] == "16"
    assert candidato["tramos"][0]["cargo_fijo_centavos"] == 100000
    assert candidato["costo_envio_default_centavos"] == 500000
    assert candidato["umbral_envio_centavos"] == 1
    assert candidato["margen_objetivo_pct_pendiente_regla_economica"] == "20"
    assert candidato["persistible"] is False


def test_liquidacion_candidata_es_equivalente_en_precios_historicos_y_vigentes():
    items = [
        Obj(id=1, lista_precio_id=1, precio_final_centavos=4000000, vigente=False),
        Obj(id=2, lista_precio_id=1, precio_final_centavos=5000000, vigente=True),
    ]
    ensayo = construir_ensayo_transicion(
        [Obj(id=1, nombre="ML")], [politica()], [], items,
    )
    resultado = ensayo["resultados"][0]
    assert resultado["estado"] == "equivalente"
    assert resultado["precios_comparados"] == 2
    assert all(item["diferencia_centavos"] == 0 for item in resultado["comparaciones"])


def test_flete_cero_no_inventa_umbral_de_envio():
    ensayo = construir_ensayo_transicion(
        [Obj(id=1, nombre="Mostrador")], [politica(flete_venta_centavos=0)], [], [],
    )
    candidato = ensayo["resultados"][0]["candidato"]
    assert candidato["umbral_envio_centavos"] == 0
    assert candidato["costo_envio_default_centavos"] == 0


def test_politica_historica_ambigua_bloquea_el_ensayo_sin_elegir_una():
    ensayo = construir_ensayo_transicion(
        [Obj(id=1, nombre="ML")], [politica(), politica(id=12)], [], [],
    )
    resultado = ensayo["resultados"][0]
    assert resultado["estado"] == "bloqueado"
    assert resultado["candidato"] is None
    assert resultado["aplicable"] is False


def test_exportacion_es_firmada_reproducible_y_declara_cero_efectos():
    args = ([Obj(id=1, nombre="ML")], [politica()], [], [])
    primero = construir_ensayo_transicion(*args)
    segundo = construir_ensayo_transicion(*args)
    assert primero["firma_ensayo"] == segundo["firma_ensayo"]
    salida = json.loads(exportar_ensayo_transicion(primero).read().decode("utf-8"))
    assert salida == primero
    assert salida["escrituras"] == salida["reglas_creadas"] == 0
    assert salida["precios_publicados"] == salida["acciones_externas"] == 0


def test_panel_y_ruta_exponen_ensayo_tenant_sin_persistencia():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    consultas = Path("services/comercial_consultas.py").read_text(encoding="utf-8")
    servicio = Path("services/ensayo_transicion_motores_comerciales.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    assert "/admin/comercial/control-motores/ensayo-transicion" in rutas
    assert '"ensayo_transicion_motores": ensayo_transicion_motores' in consultas
    assert "Ensayo de conversión en memoria" in panel
    assert "0 reglas · 0 publicaciones" in panel
    for prohibido in ("db.session", "requests.", "http://", "https://"):
        assert prohibido not in servicio
