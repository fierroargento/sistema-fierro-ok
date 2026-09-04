from pathlib import Path

from services.cola_acciones_comerciales import (
    crear_propuestas,
    decidir_propuesta,
    planificar_fila,
)


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


class Query:
    def __init__(self, modelo): self.modelo = modelo
    def filter_by(self, **_filtros): return self
    def all(self): return list(self.modelo.registros)


class Propuesta(Obj):
    registros = []


Propuesta.query = Query(Propuesta)


class Sesion:
    def add(self, propuesta):
        propuesta.id = len(Propuesta.registros) + 1
        Propuesta.registros.append(propuesta)
    def commit(self): pass


def fila(recomendacion="cancelar_promocion_antes_de_actualizar"):
    return {
        "accion_recomendada": recomendacion,
        "regla_canal": Obj(id=8, lista_precio_id=3),
        "inclusion": Obj(id=11),
        "costo": Obj(id=6, producto_id=7),
        "promocion": Obj(id=5),
        "actual": {"precio_final_centavos": 100000},
        "propuesto": {"precio_final_centavos": 130000},
        "minimo": {"piso_liquidacion_centavos": 90000},
        "objetivo": {"piso_liquidacion_centavos": 110000},
        "estado_control": "debajo_del_piso",
    }


def test_plan_con_promocion_ordena_cancelacion_antes_del_precio():
    plan = planificar_fila(fila())
    assert [item["tipo_accion"] for item in plan] == ["cancelar_promocion", "actualizar_precio"]
    assert [item["orden"] for item in plan] == [1, 2]
    assert plan[0]["clave_idempotencia"] != plan[1]["clave_idempotencia"]


def test_fila_sin_promocion_solo_propone_actualizar_precio():
    assert [item["tipo_accion"] for item in planificar_fila(fila("actualizar_precio"))] == ["actualizar_precio"]
    assert planificar_fila(fila("sin_accion")) == []
    assert planificar_fila(fila("completar_catalogo")) == []


def test_creacion_es_idempotente_y_encadena_dependencia():
    Propuesta.registros = []; sesion = Sesion()
    resultado = crear_propuestas(
        [fila()], organizacion_id=1, unidad_negocio_id=2, usuario=Obj(id=9, username="admin"),
        PropuestaAccionComercial=Propuesta, db_session=sesion,
    )
    assert len(resultado["creadas"]) == 2
    cancelar, actualizar = resultado["creadas"]
    assert actualizar.depende_de is cancelar
    assert cancelar.puede_ejecutar is False and actualizar.puede_ejecutar is False
    repetido = crear_propuestas(
        [fila()], organizacion_id=1, unidad_negocio_id=2, usuario=Obj(),
        PropuestaAccionComercial=Propuesta, db_session=sesion,
    )
    assert repetido["creadas"] == [] and repetido["omitidas"] == 2


def test_precio_no_puede_completarse_antes_de_su_dependencia():
    sesion = Sesion()
    actual = fila(); plan = planificar_fila(actual)
    cancelar = Obj(id=1, estado="preparada", puede_ejecutar=False, depende_de=None, tipo_accion=plan[0]["tipo_accion"], huella_calculo=plan[0]["huella_calculo"])
    actualizar = Obj(id=2, estado="preparada", puede_ejecutar=False, depende_de=cancelar, tipo_accion=plan[1]["tipo_accion"], huella_calculo=plan[1]["huella_calculo"])
    decidir_propuesta(cancelar, "aprobar", "", usuario=Obj(), db_session=sesion, fila_actual=actual)
    decidir_propuesta(actualizar, "aprobar", "", usuario=Obj(), db_session=sesion, fila_actual=actual)
    try:
        decidir_propuesta(actualizar, "completar_manual", "Operado", usuario=Obj(), db_session=sesion, fila_actual=actual)
    except ValueError as error: assert "acción anterior" in str(error)
    else: raise AssertionError("Se completó el precio antes de cancelar la promoción.")
    decidir_propuesta(cancelar, "completar_manual", "Comprobante 1", usuario=Obj(), db_session=sesion, fila_actual=actual)
    decidir_propuesta(actualizar, "completar_manual", "Comprobante 2", usuario=Obj(), db_session=sesion, fila_actual=actual)
    assert actualizar.estado == "completada_manual"


def test_rechazo_exige_motivo_y_no_habilita_ejecucion():
    propuesta = Obj(estado="preparada", puede_ejecutar=False, depende_de=None)
    try: decidir_propuesta(propuesta, "rechazar", "", usuario=Obj(), db_session=Sesion())
    except ValueError as error: assert "motivo" in str(error)
    else: raise AssertionError("Se aceptó un rechazo sin motivo.")
    decidir_propuesta(propuesta, "rechazar", "Costo incompleto", usuario=Obj(username="admin"), db_session=Sesion())
    assert propuesta.estado == "rechazada" and propuesta.puede_ejecutar is False


def test_contrato_persistente_y_panel_permanecen_desconectados():
    modelo = Path("models/propuesta_accion_comercial.py").read_text(encoding="utf-8")
    servicio = Path("services/cola_acciones_comerciales.py").read_text(encoding="utf-8")
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    assert "class PropuestaAccionComercial" in modelo
    assert "puede_ejecutar = false" in modelo
    assert "/admin/comercial/control-comercial/proponer" in rutas
    assert "Confirmar gestión manual" in panel
    assert "Aprobar no ejecuta nada" in panel
    for prohibido in ("requests", "OAuth", "Webhook", "MercadoLibre", "access_token"):
        assert prohibido not in servicio
