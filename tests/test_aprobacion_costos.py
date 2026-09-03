from decimal import Decimal
from pathlib import Path

from services.aprobacion_costos import (
    archivar_version,
    comparar_versiones,
    preparar_revisiones,
    rechazar_version,
    validar_version_preparatoria,
)
from services.composicion_costo_producto import construir_detalles
from services.costos_productos import preparar_detalles


class Obj:
    def __init__(self, **datos):
        self.__dict__.update(datos)


class Sesion:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


class ModeloCosto:
    pass


def perfil_y_version(precio=1000):
    insumo = Obj(
        codigo="I-1", nombre="Insumo", unidad_medida="unidad",
        versiones_precio=[Obj(
            vigente=True, moneda="ARS", precio_unitario_centavos=precio,
        )],
    )
    perfil = Obj(
        id=3, activo=True, tipo="produccion", organizacion_id=1,
        unidad_negocio_id=2, producto_id=4,
        producto=Obj(sku="SKU-1"),
        insumos_costeo=[Obj(
            insumo=insumo, cantidad=Decimal("2"),
            porcentaje_merma=Decimal("0"), observacion=None,
        )],
        operaciones_costeo=[], maquinas_costeo=[], costos_fijos_costeo=[],
    )
    detalles = preparar_detalles(construir_detalles(perfil))
    version = Obj(
        id=8, estado="preparatorio", vigente=False, tipo="calculado",
        organizacion_id=1, unidad_negocio_id=2, producto_id=4,
        moneda="ARS", numero_version=2,
        costo_total_centavos=sum(x["subtotal_centavos"] for x in detalles),
        detalles=[Obj(**detalle) for detalle in detalles], observacion=None,
    )
    return perfil, version


def test_comparacion_muestra_diferencia_absoluta_y_porcentual():
    candidata = Obj(costo_total_centavos=12500)
    vigente = Obj(costo_total_centavos=10000)
    assert comparar_versiones(candidata, vigente) == {
        "costo_anterior_centavos": 10000,
        "costo_nuevo_centavos": 12500,
        "diferencia_centavos": 2500,
        "diferencia_pct": Decimal("25.00"),
    }


def test_aprobacion_revalida_snapshot_y_bloquea_version_obsoleta():
    perfil, version = perfil_y_version()
    assert validar_version_preparatoria(
        perfil, version, CostoProductoVersion=ModeloCosto,
    ) is True
    perfil.insumos_costeo[0].insumo.versiones_precio[0].precio_unitario_centavos = 1500
    try:
        validar_version_preparatoria(
            perfil, version, CostoProductoVersion=ModeloCosto,
        )
    except ValueError as error:
        assert "desactualizada" in str(error)
    else:
        raise AssertionError("Se aprobó un snapshot obsoleto.")


def test_rechazo_y_archivo_exigen_motivo_y_conservan_historial():
    sesion = Sesion()
    _perfil, rechazada = perfil_y_version()
    rechazar_version(rechazada, "Fuente incorrecta", db_session=sesion)
    assert rechazada.estado == "cancelado"
    assert "Fuente incorrecta" in rechazada.observacion

    _perfil, archivada = perfil_y_version()
    archivada.estado = "vigente"
    archivada.vigente = True
    archivada.vigente_hasta = None
    archivar_version(archivada, "Reemplazo", db_session=sesion)
    assert archivada.estado == "archivado"
    assert archivada.vigente is False
    assert archivada.vigente_hasta is not None
    assert sesion.commits == 2


def test_bandeja_elige_ultima_pendiente_y_compara_con_vigente():
    perfil, candidata = perfil_y_version()
    antigua = Obj(**{**candidata.__dict__, "id": 6, "numero_version": 1})
    vigente = Obj(
        **{**candidata.__dict__, "id": 7, "numero_version": 1,
           "estado": "vigente", "vigente": True,
           "costo_total_centavos": 1500}
    )
    revisiones = preparar_revisiones([perfil], [antigua, vigente, candidata])
    assert len(revisiones) == 1
    assert revisiones[0]["candidata"].id == 8
    assert revisiones[0]["vigente"].id == 7
    assert revisiones[0]["diferencia_centavos"] == 500


def test_interfaz_y_rutas_no_permiten_aprobar_sin_revalidar():
    interfaz = Path("templates/admin_fuentes_costos.html").read_text(
        encoding="utf-8"
    )
    admin = Path("services/fuentes_costo_admin.py").read_text(encoding="utf-8")
    comercial = Path("services/comercial_admin.py").read_text(encoding="utf-8")
    assert "Versiones pendientes de aprobación" in interfaz
    assert "diferencia_pct" in interfaz
    assert 'value="aprobar_costos_masivo"' in interfaz
    assert '"rechazar_costo"' in admin and '"archivar_costo"' in admin
    assert "validar_version_preparatoria(" in admin
    assert "validar_version_preparatoria(" in comercial
    assert "No se pueden aprobar dos versiones" in admin
    for contenido in (admin, comercial):
        assert "MercadoLibre" not in contenido
