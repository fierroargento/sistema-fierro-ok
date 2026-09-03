from decimal import Decimal
from pathlib import Path

from services.costos_productos import preparar_detalles
from services.composicion_costo_producto import construir_detalles
from services.motor_costeo_productos import (
    diagnosticar_perfil,
    diagnosticar_perfiles,
    huella_detalles,
)


class Obj:
    def __init__(self, **datos):
        self.__dict__.update(datos)


class ModeloCosto:
    pass


def perfil_produccion(precio=1000):
    insumo = Obj(
        codigo="MAT-1", nombre="Material", unidad_medida="unidad",
        versiones_precio=[Obj(
            vigente=True, moneda="ARS", precio_unitario_centavos=precio,
        )],
    )
    return Obj(
        id=7, activo=True, tipo="produccion", organizacion_id=2,
        unidad_negocio_id=3, producto_id=11,
        producto=Obj(sku="SKU-1"),
        insumos_costeo=[Obj(
            insumo=insumo, cantidad=Decimal("2"),
            porcentaje_merma=Decimal("0"), observacion=None,
        )],
        operaciones_costeo=[], maquinas_costeo=[], costos_fijos_costeo=[],
    )


def version_desde(perfil, numero=1):
    detalles = preparar_detalles(construir_detalles(perfil))
    return Obj(
        producto_id=perfil.producto_id,
        organizacion_id=perfil.organizacion_id,
        unidad_negocio_id=perfil.unidad_negocio_id,
        moneda="ARS", estado="preparatorio", numero_version=numero,
        detalles=[Obj(**detalle) for detalle in detalles],
        costo_total_centavos=sum(x["subtotal_centavos"] for x in detalles),
    )


def test_diagnostico_detecta_sin_calcular_actualizado_y_desactualizado():
    perfil = perfil_produccion()
    sin_calcular = diagnosticar_perfil(
        perfil, [], CostoProductoVersion=ModeloCosto,
    )
    assert sin_calcular["estado"] == "sin_calcular"
    assert sin_calcular["costo_estimado_centavos"] == 2000
    assert sin_calcular["puede_recalcular"] is True

    anterior = version_desde(perfil)
    actualizado = diagnosticar_perfil(
        perfil, [anterior], CostoProductoVersion=ModeloCosto,
    )
    assert actualizado["estado"] == "actualizado"
    assert huella_detalles(anterior.detalles) == huella_detalles(
        preparar_detalles(construir_detalles(perfil))
    )

    perfil.insumos_costeo[0].insumo.versiones_precio[0].precio_unitario_centavos = 1200
    cambiado = diagnosticar_perfil(
        perfil, [anterior], CostoProductoVersion=ModeloCosto,
    )
    assert cambiado["estado"] == "desactualizado"
    assert cambiado["costo_estimado_centavos"] == 2400


def test_diagnostico_incompleto_explica_la_fuente_faltante():
    perfil = perfil_produccion()
    perfil.insumos_costeo[0].insumo.versiones_precio = []
    resultado = diagnosticar_perfil(
        perfil, [], CostoProductoVersion=ModeloCosto,
    )
    assert resultado["estado"] == "incompleto"
    assert "no tiene precio vigente" in resultado["detalle"]
    assert resultado["puede_recalcular"] is False


def test_resumen_separa_manuales_pendientes_y_actualizados():
    produccion = perfil_produccion()
    simple = Obj(
        id=8, activo=True, tipo="simple", organizacion_id=2,
        unidad_negocio_id=3, producto_id=12, producto=Obj(sku="SKU-2"),
    )
    diagnosticos, resumen = diagnosticar_perfiles(
        [produccion, simple], [], CostoProductoVersion=ModeloCosto,
    )
    assert diagnosticos[8]["estado"] == "manual_pendiente"
    assert resumen == {
        "total": 2, "actualizados": 0, "pendientes": 1,
        "incompletos": 0, "manuales": 1,
    }


def test_recalculo_masivo_es_preparatorio_tenant_y_sin_canales():
    servicio = Path("services/fuentes_costo_admin.py").read_text(encoding="utf-8")
    motor = Path("services/motor_costeo_productos.py").read_text(encoding="utf-8")
    interfaz = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")
    assert 'accion == "recalcular_fichas_masivo"' in servicio
    assert "unidad_negocio_id == unidad_activa.id" in servicio
    assert "confirmar_cada_version = False" in servicio
    assert "pendiente de activación" in servicio
    assert "Recalcular seleccionadas" in interfaz
    assert "Las nuevas versiones quedan preparatorias" in interfaz
    for prohibido in ("requests", "OAuth", "Webhook", "MercadoLibre"):
        assert prohibido not in motor
