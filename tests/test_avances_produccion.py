from decimal import Decimal
from pathlib import Path

from services.avances_produccion import registrar_parte, resumir_orden


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


class Parte(Obj): pass


class Session:
    def __init__(self): self.items=[]; self.commits=0
    def add(self, item): self.items.append(item)
    def commit(self): self.commits += 1


def orden(partes=None):
    return Obj(id=1, organizacion_id=7, unidad_negocio_id=9, estado="aprobada",
               cantidad_planificada="10", partes_informados=partes or [])


def registrar(orden_obj, buenas, rechazadas="0"):
    return registrar_parte(
        {"numero":"P-1", "cantidad_buena":buenas, "cantidad_rechazada":rechazadas, "minutos_reales":"45"},
        orden=orden_obj, organizacion_id=7, unidad_negocio_id=9,
        ParteProduccion=Parte, db_session=Session(), usuario_id=4,
    )


def test_parte_informa_avance_sin_efectos_fisicos():
    parte = registrar(orden(), "6", "1")
    assert parte.cantidad_buena == Decimal("6.000000")
    assert parte.impacta_inventario is False
    assert parte.consume_insumos is False and parte.crea_producto_terminado is False


def test_acumulado_no_puede_superar_plan():
    previa = Obj(estado="informado", cantidad_buena="7", cantidad_rechazada="1", minutos_reales="10")
    try: registrar(orden([previa]), "3")
    except ValueError as error: assert "supera" in str(error)
    else: raise AssertionError("Se aceptó sobreproducción.")


def test_resumen_separa_buenas_rechazadas_y_pendientes():
    partes = [Obj(estado="informado", cantidad_buena="6", cantidad_rechazada="1", minutos_reales="45")]
    resumen = resumir_orden(orden(partes))
    assert resumen["buenas"] == 6 and resumen["rechazadas"] == 1
    assert resumen["pendientes"] == 3 and resumen["minutos_reales"] == 45


def test_solo_orden_aprobada_y_del_contexto_admite_parte():
    for cambio, esperado in (({"estado":"borrador"}, "aprobada"), ({"organizacion_id":8}, "tenant")):
        item = orden(); item.__dict__.update(cambio)
        try: registrar(item, "1")
        except ValueError as error: assert esperado in str(error)
        else: raise AssertionError("Se aceptó parte inválido.")


def test_modelo_impide_impactos_y_panel_declara_bloqueo():
    modelo = Path("models/produccion.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_produccion.html").read_text(encoding="utf-8")
    assert "impacta_inventario = false AND consume_insumos = false" in modelo
    assert "sin consumir insumos ni ingresar productos" in panel


def test_servicio_no_importa_inventario_costos_o_conexiones():
    servicio = Path("services/avances_produccion.py").read_text(encoding="utf-8")
    for prohibido in ("db.session", "MovimientoInventario", "CostoProductoVersion", "requests.", "urlopen"):
        assert prohibido not in servicio
