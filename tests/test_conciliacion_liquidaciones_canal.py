from datetime import datetime
from pathlib import Path

from services.conciliacion_liquidaciones_canal import (
    calcular_expectativa,
    conciliar_venta,
    construir_conciliaciones,
    registrar_movimiento,
    registrar_venta,
)


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


class Sesion:
    def __init__(self): self.agregados = []; self.commits = 0
    def add(self, objeto): self.agregados.append(objeto)
    def commit(self): self.commits += 1


def regla():
    return Obj(
        comision_pct=10, umbral_envio_centavos=3300000,
        costo_envio_default_centavos=500000,
        tramos=[Obj(precio_desde_centavos=0, precio_hasta_centavos=3300000, cargo_fijo_centavos=100000)],
    )


def venta(**cambios):
    datos = dict(
        referencia_venta="VENTA-1", cuenta_codigo="CUENTA-1", estado="confirmada",
        cantidad=1, importe_bruto_centavos=2000000,
        liquidacion_esperada_centavos=1700000,
        piso_unitario_snapshot_centavos=1500000,
    )
    datos.update(cambios); return Obj(**datos)


def movimiento(importe=1700000, direccion="credito", tipo="liquidacion_neta", **cambios):
    datos = dict(
        referencia_venta="VENTA-1", cuenta_codigo="CUENTA-1", impacta_saldo=True,
        estado="confirmado", importe_centavos=importe, direccion=direccion, tipo=tipo,
    )
    datos.update(cambios); return Obj(**datos)


def test_expectativa_desglosa_comision_cargo_y_envio_por_cantidad():
    resultado = calcular_expectativa(2000000, 2, regla())
    assert resultado == {
        "importe_bruto_centavos": 4000000,
        "comision_esperada_centavos": 400000,
        "cargo_fijo_esperado_centavos": 200000,
        "envio_esperado_centavos": 0,
        "liquidacion_esperada_centavos": 3400000,
    }
    con_envio = calcular_expectativa(4000000, 1, regla())
    assert con_envio["envio_esperado_centavos"] == 500000


def test_registros_congelan_expectativa_e_identidad_sin_conectar():
    sesion = Sesion(); momento = datetime(2026, 9, 4)
    registro = registrar_venta(
        organizacion_id=1, unidad_negocio_id=2, lista_precio_id=3,
        catalogo_producto_id=11, cuenta_codigo="CUENTA-1", referencia_venta="VENTA-1",
        referencia_item="ITEM-1", referencia_pago="PAGO-1", cantidad=1,
        precio_unitario_centavos=2000000, estado="confirmada", fecha_venta=momento,
        regla_canal=regla(), costo_unitario_centavos=1000000,
        piso_unitario_centavos=1500000, usuario=Obj(id=9, username="admin"),
        VentaCanalItem=Obj, db_session=sesion,
    )
    assert registro.liquidacion_esperada_centavos == 1700000
    assert registro.piso_unitario_snapshot_centavos == 1500000
    registrar_movimiento(
        organizacion_id=1, unidad_negocio_id=2, cuenta_codigo="CUENTA-1",
        referencia_venta="VENTA-1", referencia_pago="PAGO-1",
        referencia_movimiento="MOV-1", tipo="liquidacion_neta", direccion="credito",
        importe_centavos=1700000, fecha_movimiento=momento,
        MovimientoLiquidacionCanal=Obj, db_session=sesion,
    )
    assert len(sesion.agregados) == 2 and sesion.commits == 2


def test_liquidacion_neta_exacta_concilia_y_cumple_piso():
    resultado = conciliar_venta("VENTA-1", "CUENTA-1", [venta()], [movimiento()])
    assert resultado["estado_conciliacion"] == "conciliada"
    assert resultado["diferencia_centavos"] == 0
    assert resultado["estado_economico"] == "cumple"


def test_pago_bruto_menos_deducciones_produce_la_misma_liquidacion():
    movimientos = [
        movimiento(2000000, "credito", "pago_bruto"),
        movimiento(200000, "debito", "comision"),
        movimiento(100000, "debito", "cargo_fijo"),
    ]
    resultado = conciliar_venta("VENTA-1", "CUENTA-1", [venta()], movimientos)
    assert resultado["liquidacion_real_centavos"] == 1700000
    assert resultado["estado_conciliacion"] == "conciliada"


def test_distingue_pendiente_parcial_anulada_y_devuelta():
    assert conciliar_venta("VENTA-1", "CUENTA-1", [venta()], [])["estado_conciliacion"] == "pendiente"
    assert conciliar_venta("VENTA-1", "CUENTA-1", [venta()], [movimiento(1000000)])["estado_conciliacion"] == "pago_parcial"
    assert conciliar_venta("VENTA-1", "CUENTA-1", [venta(estado="cancelada")], [])["estado_conciliacion"] == "anulada"
    assert conciliar_venta("VENTA-1", "CUENTA-1", [venta(estado="devuelta")], [])["estado_conciliacion"] == "devuelta"


def test_regla_principal_detecta_liquidacion_esperada_bajo_piso():
    resultado = conciliar_venta(
        "VENTA-1", "CUENTA-1",
        [venta(liquidacion_esperada_centavos=1400000, piso_unitario_snapshot_centavos=1500000)],
        [movimiento(1400000)],
    )
    assert resultado["estado_conciliacion"] == "conciliada"
    assert resultado["estado_economico"] == "bajo_piso"
    filas, resumen = construir_conciliaciones(resultado["items"], resultado["movimientos"])
    assert filas[0]["estado_economico"] == "bajo_piso" and resumen["bajo_piso"] == 1


def test_modelos_panel_y_motor_son_saas_y_desconectados():
    modelo = Path("models/conciliacion_ventas_canal.py").read_text(encoding="utf-8")
    servicio = Path("services/conciliacion_liquidaciones_canal.py").read_text(encoding="utf-8")
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_conciliacion_canal.html").read_text(encoding="utf-8")
    assert "class VentaCanalItem" in modelo and "class MovimientoLiquidacionCanal" in modelo
    assert "/admin/comercial/conciliacion" in rutas
    assert "Debajo del piso económico" in panel
    assert "No consulta cuentas de pago" in panel
    for prohibido in ("requests", "OAuth", "Webhook", "MercadoLibre", "MercadoPago", "access_token"):
        assert prohibido not in servicio
