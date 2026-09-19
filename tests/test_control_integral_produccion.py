import json
from pathlib import Path

from services.control_integral_produccion import controlar_produccion, exportar_control


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


def orden():
    insumo=Obj(insumo_id=1, cantidad_planificada="20")
    operacion=Obj(minutos_planificados="50")
    parte=Obj(id=4, estado="informado", cantidad_buena="6", cantidad_rechazada="2", minutos_reales="40",
              impacta_inventario=False, consume_insumos=False, crea_producto_terminado=False)
    return Obj(id=1, numero="OP-1", organizacion_id=7, unidad_negocio_id=9, estado="aprobada",
               cantidad_planificada="10", costo_unitario_centavos=10000, costo_planificado_centavos=100000,
               impacta_inventario=False, ejecucion_habilitada=False,
               insumos_planificados=[insumo], operaciones_planificadas=[operacion],
               maquinas_planificadas=[], partes_informados=[parte])


def test_control_coherente_aprueba_y_firma():
    resultado=controlar_produccion(organizacion_id=7, unidad_negocio_id=9, ordenes=[orden()])
    assert resultado["aprobado"] is True and len(resultado["huella_control"]) == 64
    assert resultado["resumen"]["simulaciones"] == 1


def test_detecta_ejecucion_parte_con_impacto_y_costo_inconsistente():
    item=orden(); item.ejecucion_habilitada=True; item.costo_planificado_centavos=1
    item.partes_informados[0].consume_insumos=True
    codigos={x["codigo"] for x in controlar_produccion(organizacion_id=7, unidad_negocio_id=9, ordenes=[item])["hallazgos"]}
    assert {"orden_ejecutable","parte_con_impacto","costo_plan_inconsistente"} <= codigos


def test_detecta_sobreproduccion_y_plan_incompleto():
    item=orden(); item.insumos_planificados=[]; item.partes_informados[0].cantidad_buena="11"
    codigos={x["codigo"] for x in controlar_produccion(organizacion_id=7, unidad_negocio_id=9, ordenes=[item])["hallazgos"]}
    assert {"plan_incompleto","sobreproduccion"} <= codigos


def test_exportacion_es_reproducible():
    uno=controlar_produccion(organizacion_id=7, unidad_negocio_id=9, ordenes=[orden()])
    dos=controlar_produccion(organizacion_id=7, unidad_negocio_id=9, ordenes=[orden()])
    assert uno["huella_control"] == dos["huella_control"]
    assert json.load(exportar_control(uno))["huella_control"] == uno["huella_control"]


def test_ruta_y_panel_exponen_control_tenant():
    rutas=Path("modules/admin/produccion/routes.py").read_text(encoding="utf-8")
    panel=Path("templates/admin_produccion.html").read_text(encoding="utf-8")
    assert 'route("/admin/produccion/control-integral")' in rutas
    assert "organizacion_id=organizacion.id" in rutas and "unidad_negocio_id=unidad.id" in rutas
    assert "Descargar control integral de Producción" in panel


def test_control_es_solo_lectura_y_offline():
    servicio=Path("services/control_integral_produccion.py").read_text(encoding="utf-8")
    for prohibido in ("db.session", "MovimientoInventario", "requests.", "urlopen", "http://", "https://"):
        assert prohibido not in servicio
