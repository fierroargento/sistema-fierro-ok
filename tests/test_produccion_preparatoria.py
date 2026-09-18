from decimal import Decimal
from pathlib import Path

from services.produccion_nucleo import cambiar_estado, crear_orden_preparatoria


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


class Coleccion(Obj):
    pass


class Orden(Obj):
    def __init__(self, **datos):
        super().__init__(**datos)
        self.insumos_planificados = []
        self.operaciones_planificadas = []
        self.maquinas_planificadas = []


class Session:
    def __init__(self): self.items = []; self.commits = 0
    def add(self, item): self.items.append(item)
    def commit(self): self.commits += 1


MODELOS = {
    "OrdenProduccion": Orden,
    "OrdenProduccionInsumo": Coleccion,
    "OrdenProduccionOperacion": Coleccion,
    "OrdenProduccionMaquina": Coleccion,
}


def perfil():
    return Obj(
        id=1, organizacion_id=7, unidad_negocio_id=9, producto_id=11,
        tipo="produccion", activo=True,
        insumos_costeo=[Obj(insumo_id=2, cantidad="3", porcentaje_merma="10")],
        operaciones_costeo=[Obj(empleado_id=3, nombre="Soldadura", minutos="5")],
        maquinas_costeo=[Obj(maquina_id=4, nombre="Corte", minutos="2")],
    )


def crear(cantidad="2"):
    return crear_orden_preparatoria(
        {"numero": "op-1", "cantidad": cantidad}, perfil=perfil(),
        version_costo=Obj(id=8, vigente=True, costo_total_centavos=10000),
        organizacion_id=7, unidad_negocio_id=9, modelos=MODELOS,
        db_session=Session(), usuario_id=5,
    )


def test_orden_congela_ficha_y_costo_sin_habilitar_ejecucion():
    orden = crear()
    assert orden.numero == "OP-1" and orden.costo_planificado_centavos == 20000
    assert orden.insumos_planificados[0].cantidad_planificada == Decimal("6.600000")
    assert orden.operaciones_planificadas[0].minutos_planificados == Decimal("10.000000")
    assert orden.maquinas_planificadas[0].minutos_planificados == Decimal("4.000000")
    assert orden.impacta_inventario is False and orden.ejecucion_habilitada is False


def test_aprobacion_interna_mantiene_bloqueos():
    orden = crear(); sesion = Session()
    cambiar_estado(orden, "en_revision", organizacion_id=7, unidad_negocio_id=9, db_session=sesion)
    cambiar_estado(orden, "aprobada", organizacion_id=7, unidad_negocio_id=9, db_session=sesion)
    assert orden.estado == "aprobada"
    assert orden.impacta_inventario is False and orden.ejecucion_habilitada is False


def test_rechaza_perfil_cruzado_o_sin_costo_vigente():
    for p, version, esperado in ((Obj(**{**perfil().__dict__, "organizacion_id": 8}), Obj(id=1, vigente=True, costo_total_centavos=1), "tenant"), (perfil(), None, "vigente")):
        try:
            crear_orden_preparatoria(
                {"numero": "X", "cantidad": "1"}, perfil=p, version_costo=version,
                organizacion_id=7, unidad_negocio_id=9, modelos=MODELOS, db_session=Session(),
            )
        except ValueError as error: assert esperado in str(error)
        else: raise AssertionError("Se aceptó una orden productiva inválida.")


def test_modelos_bloquean_inventario_y_ejecucion_en_base():
    modelo = Path("models/produccion.py").read_text(encoding="utf-8")
    assert "impacta_inventario = false AND ejecucion_habilitada = false" in modelo
    assert "consumo_registrado" in modelo and "avance_registrado" in modelo


def test_panel_es_tenant_y_solo_administrativo():
    rutas = Path("modules/admin/produccion/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_produccion.html").read_text(encoding="utf-8")
    assert 'Blueprint("admin_produccion"' in rutas
    assert 'membresia.rol != "admin"' in rutas
    assert "ejecución física permanece bloqueada" in panel


def test_servicio_no_importa_consumidores_productivos_o_externos():
    servicio = Path("services/produccion_nucleo.py").read_text(encoding="utf-8")
    for prohibido in ("MovimientoInventario", "requests.", "urlopen", "EventoFiscal", "Pedido"):
        assert prohibido not in servicio
