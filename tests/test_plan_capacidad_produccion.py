import json
from pathlib import Path

from services.plan_capacidad_produccion import planificar_capacidad, exportar_capacidad


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


def orden(identificador, estado="aprobada", buenas="0"):
    partes=[] if buenas == "0" else [Obj(estado="informado", cantidad_buena=buenas,
                                          cantidad_rechazada="0", minutos_reales="10")]
    return Obj(id=identificador, numero=f"OP-{identificador}", organizacion_id=7, unidad_negocio_id=9,
               estado=estado, cantidad_planificada="10", partes_informados=partes,
               operaciones_planificadas=[Obj(empleado_id=2, minutos_planificados="600")],
               maquinas_planificadas=[Obj(maquina_id=3, minutos_planificados="300")])


def versiones(horas_persona="20", horas_maquina="10"):
    empleado=Obj(id=2, organizacion_id=7, unidad_negocio_id=9, activo=True)
    maquina=Obj(id=3, organizacion_id=7, unidad_negocio_id=9, activo=True)
    return ([Obj(vigente=True, horas_productivas=horas_persona, empleado=empleado)],
            [Obj(vigente=True, horas_productivas_mensuales=horas_maquina, maquina=maquina)])


def test_agrega_carga_pendiente_y_capacidad():
    personas, maquinas=versiones()
    resultado=planificar_capacidad(organizacion_id=7, unidad_negocio_id=9,
        ordenes=[orden(1,buenas="5"),orden(2)], versiones_empleado=personas, versiones_maquina=maquinas)
    assert resultado["carga_personas"][0]["carga_minutos"] == "900"
    assert resultado["carga_personas"][0]["capacidad_minutos"] == "1200"
    assert resultado["carga_maquinas"][0]["carga_minutos"] == "450"
    assert resultado["resumen"]["cuellos_botella"] == 0


def test_detecta_sobrecarga_y_ordena_aprobadas_primero():
    personas, maquinas=versiones(horas_persona="5", horas_maquina="5")
    resultado=planificar_capacidad(organizacion_id=7, unidad_negocio_id=9,
        ordenes=[orden(1,"en_revision"),orden(2,"aprobada")],
        versiones_empleado=personas, versiones_maquina=maquinas)
    assert [x["orden_id"] for x in resultado["secuencia_sugerida"]] == [2,1]
    assert resultado["resumen"]["cuellos_botella"] == 2 and resultado["aprobado"] is False


def test_detecta_capacidad_faltante_y_recurso_cruzado():
    sin_capacidad=planificar_capacidad(organizacion_id=7, unidad_negocio_id=9,
        ordenes=[orden(1)], versiones_empleado=[], versiones_maquina=[])
    codigos={x["codigo"] for x in sin_capacidad["hallazgos"]}
    assert {"capacidad_persona_faltante","capacidad_maquina_faltante"} <= codigos
    personas, maquinas=versiones(); personas[0].empleado.organizacion_id=8
    cruzado=planificar_capacidad(organizacion_id=7, unidad_negocio_id=9,
        ordenes=[orden(1)], versiones_empleado=personas, versiones_maquina=maquinas)
    assert cruzado["hallazgos"][0]["codigo"] == "recurso_fuera_tenant"


def test_resultado_firmado_y_reproducible():
    personas, maquinas=versiones()
    uno=planificar_capacidad(organizacion_id=7, unidad_negocio_id=9, ordenes=[orden(1)],
                             versiones_empleado=personas, versiones_maquina=maquinas)
    dos=planificar_capacidad(organizacion_id=7, unidad_negocio_id=9, ordenes=[orden(1)],
                             versiones_empleado=personas, versiones_maquina=maquinas)
    assert uno["huella_capacidad"] == dos["huella_capacidad"]
    assert json.load(exportar_capacidad(uno))["huella_capacidad"] == uno["huella_capacidad"]


def test_ruta_filtra_tenant_unidad_y_panel_expone_plan():
    rutas=Path("modules/admin/produccion/routes.py").read_text(encoding="utf-8")
    panel=Path("templates/admin_produccion.html").read_text(encoding="utf-8")
    assert 'route("/admin/produccion/plan-capacidad")' in rutas
    assert "EmpleadoProductivo\"].organizacion_id == organizacion.id" in rutas
    assert "planificación de personas y máquinas" in panel


def test_plan_no_inicia_ordena_persiste_ni_conecta():
    texto=Path("services/plan_capacidad_produccion.py").read_text(encoding="utf-8")
    for prohibido in ("db.session", ".commit(", ".add(", "MovimientoInventario", "requests.",
                       "urlopen", "http://", "https://"):
        assert prohibido not in texto
