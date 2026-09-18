import json
from pathlib import Path

from services.simulacion_cierre_produccion import exportar_simulacion, simular_cierre


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


def orden():
    parte = Obj(estado="informado", cantidad_buena="6", cantidad_rechazada="2", minutos_reales="50")
    return Obj(
        id=1, numero="OP-1", organizacion_id=7, unidad_negocio_id=9,
        estado="aprobada", cantidad_planificada="10", costo_planificado_centavos=100000,
        partes_informados=[parte],
        insumos_planificados=[Obj(insumo_id=3, cantidad_planificada="20")],
        operaciones_planificadas=[Obj(minutos_planificados="50")],
    )


def test_simula_consumos_tiempos_costos_y_resultados_proporcionales():
    resultado = simular_cierre(orden(), organizacion_id=7, unidad_negocio_id=9)
    assert resultado["consumos_teoricos"][0]["cantidad_teorica"] == "16"
    assert resultado["tiempos"]["planificados_proporcionales"] == "40"
    assert resultado["tiempos"]["desvio_minutos"] == "10"
    assert resultado["costos"]["planificado_proporcional_centavos"] == 80000
    assert resultado["propuestas"]["ingreso_producto_terminado"] == "6"


def test_simulacion_permanece_no_ejecutable_y_sin_persistencia():
    resultado = simular_cierre(orden(), organizacion_id=7, unidad_negocio_id=9)
    assert resultado["propuestas"]["ejecutable"] is False
    assert resultado["propuestas"]["movimientos_creados"] == 0
    assert resultado["controles"] == {
        "persistencia": False, "consumos_reales": 0, "altas_stock": 0,
        "cambios_costos": 0, "conexiones_externas": 0,
    }


def test_firma_y_exportacion_son_reproducibles():
    primero = simular_cierre(orden(), organizacion_id=7, unidad_negocio_id=9)
    segundo = simular_cierre(orden(), organizacion_id=7, unidad_negocio_id=9)
    assert primero["huella_simulacion"] == segundo["huella_simulacion"]
    assert json.load(exportar_simulacion(primero))["huella_simulacion"] == primero["huella_simulacion"]


def test_rechaza_contexto_cruzado_orden_no_aprobada_o_sin_avance():
    casos = [({"organizacion_id":8}, "tenant"), ({"estado":"borrador"}, "aprobada"), ({"partes_informados":[]}, "avances")]
    for cambios, esperado in casos:
        item=orden(); item.__dict__.update(cambios)
        try: simular_cierre(item, organizacion_id=7, unidad_negocio_id=9)
        except ValueError as error: assert esperado in str(error)
        else: raise AssertionError("Se aceptó simulación inválida.")


def test_ruta_exporta_json_desde_contexto_tenant():
    rutas=Path("modules/admin/produccion/routes.py").read_text(encoding="utf-8")
    assert 'route("/admin/produccion/orden/<int:orden_id>/simulacion")' in rutas
    assert "organizacion_id=organizacion.id" in rutas and "unidad_negocio_id=unidad.id" in rutas


def test_servicio_es_en_memoria_y_sin_consumidores_productivos():
    servicio=Path("services/simulacion_cierre_produccion.py").read_text(encoding="utf-8")
    for prohibido in ("db.session", "MovimientoInventario", "ExistenciaSucursal", "requests.", "urlopen"):
        assert prohibido not in servicio
