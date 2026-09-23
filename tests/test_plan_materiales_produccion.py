import json
from pathlib import Path

from services.plan_materiales_produccion import planificar_materiales, exportar_plan


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


def orden(identificador, numero, cantidad_buena="0", estado="aprobada"):
    parte=[] if cantidad_buena == "0" else [Obj(estado="informado", cantidad_buena=cantidad_buena,
                                                 cantidad_rechazada="0", minutos_reales="10")]
    return Obj(id=identificador, numero=numero, organizacion_id=7, unidad_negocio_id=9,
               estado=estado, cantidad_planificada="10",
               insumos_planificados=[Obj(insumo_id=3, cantidad_planificada="20")],
               partes_informados=parte)


def mapeo(stock=25, reservado=0, bloqueado=0):
    existencia=Obj(id=11, organizacion_id=7, stock_actual=stock,
                   stock_reservado=reservado, stock_bloqueado=bloqueado,
                   control_activo=True)
    insumo=Obj(organizacion_id=7, unidad_negocio_id=9, activo=True)
    return Obj(id=5, organizacion_id=7, unidad_negocio_id=9, insumo_id=3,
               activo=True, insumo=insumo, existencia=existencia)


def test_asigna_stock_neto_por_prioridad_y_sugiere_compra():
    resultado=planificar_materiales(
        organizacion_id=7, unidad_negocio_id=9,
        ordenes=[orden(2,"OP-2"), orden(1,"OP-1")], mapeos_insumo=[mapeo(stock=30, reservado=5)],
    )
    assert [x["orden_id"] for x in resultado["asignaciones_virtuales"]] == [1,2]
    assert resultado["asignaciones_virtuales"][0]["asignada_virtual"] == "20"
    assert resultado["asignaciones_virtuales"][1]["asignada_virtual"] == "5"
    assert resultado["sugerencias_compra"][0]["cantidad"] == "15"


def test_descuenta_avance_y_excluye_estados_no_activos():
    resultado=planificar_materiales(
        organizacion_id=7, unidad_negocio_id=9,
        ordenes=[orden(1,"OP-1","5"), orden(2,"OP-2",estado="cancelada")],
        mapeos_insumo=[mapeo(stock=10)],
    )
    assert resultado["resumen"]["ordenes_consideradas"] == 1
    assert resultado["asignaciones_virtuales"][0]["requerida"] == "10"
    assert resultado["sugerencias_compra"] == []


def test_detecta_faltantes_ambiguedad_y_cruces_tenant():
    base=mapeo(); duplicado=Obj(**base.__dict__); duplicado.id=6
    ambiguo=planificar_materiales(organizacion_id=7, unidad_negocio_id=9,
                                  ordenes=[orden(1,"OP")], mapeos_insumo=[base,duplicado])
    assert ambiguo["hallazgos"][0]["codigo"] == "mapeo_ambiguo"
    faltante=planificar_materiales(organizacion_id=7, unidad_negocio_id=9,
                                   ordenes=[orden(1,"OP")], mapeos_insumo=[])
    assert faltante["hallazgos"][0]["codigo"] == "mapeo_faltante"
    base.existencia.organizacion_id=8
    cruzado=planificar_materiales(organizacion_id=7, unidad_negocio_id=9,
                                  ordenes=[orden(1,"OP")], mapeos_insumo=[base])
    assert cruzado["hallazgos"][0]["codigo"] == "existencia_otro_tenant"


def test_plan_es_reproducible_e_idempotente():
    uno=planificar_materiales(organizacion_id=7, unidad_negocio_id=9,
                              ordenes=[orden(1,"OP")], mapeos_insumo=[mapeo(stock=0)])
    dos=planificar_materiales(organizacion_id=7, unidad_negocio_id=9,
                              ordenes=[orden(1,"OP")], mapeos_insumo=[mapeo(stock=0)])
    assert uno["huella_plan"] == dos["huella_plan"]
    assert uno["sugerencias_compra"][0]["clave_idempotencia"] == dos["sugerencias_compra"][0]["clave_idempotencia"]
    assert json.load(exportar_plan(uno))["huella_plan"] == uno["huella_plan"]


def test_ruta_y_panel_exponen_plan_tenant():
    rutas=Path("modules/admin/produccion/routes.py").read_text(encoding="utf-8")
    panel=Path("templates/admin_produccion.html").read_text(encoding="utf-8")
    assert 'route("/admin/produccion/plan-materiales")' in rutas
    assert "organizacion_id=organizacion.id, unidad_negocio_id=unidad.id" in rutas
    assert "planificación agregada de materiales" in panel


def test_servicio_no_reserva_compra_mueve_ni_conecta():
    texto=Path("services/plan_materiales_produccion.py").read_text(encoding="utf-8")
    for prohibido in ("db.session", ".commit(", ".add(", "MovimientoInventario", "OrdenCompra(",
                       "requests.", "urlopen", "http://", "https://"):
        assert prohibido not in texto
