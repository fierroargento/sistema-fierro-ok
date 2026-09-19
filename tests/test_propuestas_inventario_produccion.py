import json
from pathlib import Path

from services.propuestas_inventario_produccion import preparar_propuesta_inventario, exportar_propuesta


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


def orden():
    insumo=Obj(insumo_id=3, cantidad_planificada="20")
    operacion=Obj(minutos_planificados="50")
    parte=Obj(id=4, estado="informado", cantidad_buena="6", cantidad_rechazada="2", minutos_reales="40",
              impacta_inventario=False, consume_insumos=False, crea_producto_terminado=False)
    return Obj(id=1, numero="OP-1", organizacion_id=7, unidad_negocio_id=9, producto_id=30,
               estado="aprobada", cantidad_planificada="10", costo_planificado_centavos=100000,
               insumos_planificados=[insumo], operaciones_planificadas=[operacion], partes_informados=[parte])


def datos():
    existencia_insumo=Obj(id=11, organizacion_id=7, producto_id=20)
    mapeo=Obj(id=5, organizacion_id=7, unidad_negocio_id=9, insumo_id=3,
              activo=True, existencia=existencia_insumo)
    destino=Obj(id=12, organizacion_id=7, producto_id=30)
    return [mapeo], [destino]


def test_compone_salida_ingreso_y_reversion_idempotentes():
    mapeos, destinos=datos()
    resultado=preparar_propuesta_inventario(
        orden(), organizacion_id=7, unidad_negocio_id=9,
        mapeos_insumo=mapeos, existencias_producto=destinos,
    )
    assert resultado["aprobada"] is True and len(resultado["movimientos_propuestos"]) == 2
    assert resultado["movimientos_propuestos"][0]["cantidad"] == "16"
    assert resultado["movimientos_propuestos"][1]["cantidad"] == "6"
    assert len({x["clave_idempotencia"] for x in resultado["movimientos_propuestos"]}) == 2
    assert len(resultado["reversion_teorica"]) == 2


def test_detecta_mapeos_faltantes_ambiguos_y_destino_ambiguo():
    mapeos, destinos=datos()
    duplicado=Obj(**mapeos[0].__dict__); duplicado.id=6
    resultado=preparar_propuesta_inventario(
        orden(), organizacion_id=7, unidad_negocio_id=9,
        mapeos_insumo=mapeos+[duplicado], existencias_producto=destinos+[Obj(id=13, organizacion_id=7, producto_id=30)],
    )
    codigos={x["codigo"] for x in resultado["hallazgos"]}
    assert {"mapeo_insumo_ambiguo", "destino_producto_ambiguo"} <= codigos
    sin_mapeo=preparar_propuesta_inventario(
        orden(), organizacion_id=7, unidad_negocio_id=9, mapeos_insumo=[], existencias_producto=destinos,
    )
    assert sin_mapeo["hallazgos"][0]["codigo"] == "mapeo_insumo_faltante"


def test_rechaza_relaciones_cruzadas_sin_atribuirlas():
    mapeos, destinos=datos(); mapeos[0].existencia.organizacion_id=8
    resultado=preparar_propuesta_inventario(
        orden(), organizacion_id=7, unidad_negocio_id=9,
        mapeos_insumo=mapeos, existencias_producto=destinos+[Obj(id=99, organizacion_id=8, producto_id=30)],
    )
    codigos={x["codigo"] for x in resultado["hallazgos"]}
    assert {"existencia_insumo_otro_tenant", "destino_producto_otro_tenant"} <= codigos


def test_exportacion_es_firmada_y_reproducible():
    mapeos, destinos=datos()
    uno=preparar_propuesta_inventario(orden(), organizacion_id=7, unidad_negocio_id=9,
                                      mapeos_insumo=mapeos, existencias_producto=destinos)
    dos=preparar_propuesta_inventario(orden(), organizacion_id=7, unidad_negocio_id=9,
                                      mapeos_insumo=mapeos, existencias_producto=destinos)
    assert uno["huella_propuesta"] == dos["huella_propuesta"]
    assert json.load(exportar_propuesta(uno))["huella_propuesta"] == uno["huella_propuesta"]


def test_ruta_filtra_tenant_unidad_y_panel_expone_descarga():
    rutas=Path("modules/admin/produccion/routes.py").read_text(encoding="utf-8")
    panel=Path("templates/admin_produccion.html").read_text(encoding="utf-8")
    assert 'route("/admin/produccion/orden/<int:orden_id>/propuesta-inventario")' in rutas
    assert "organizacion_id=organizacion.id, unidad_negocio_id=unidad.id" in rutas
    assert "Propuesta Producción–Inventario" in panel


def test_servicio_no_persiste_ni_ejecuta_efectos():
    texto=Path("services/propuestas_inventario_produccion.py").read_text(encoding="utf-8")
    for prohibido in ("db.session", ".commit(", ".add(", "MovimientoInventario", "requests.", "urlopen", "http://", "https://"):
        assert prohibido not in texto
