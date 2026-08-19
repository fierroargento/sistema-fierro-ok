from pathlib import Path
from types import SimpleNamespace

from services.inventario_eventos_canal import (
    preparar_sobre_evento,
    validar_sobre_evento,
)


def _base(*, tipo="pagado", cantidades=None):
    pedido = SimpleNamespace(
        id=1204, canal="Tienda Nube", tn_cuenta_id=7,
        id_venta="TN-55", estado=tipo,
        items=[SimpleNamespace(sku="PP6040H", cantidad=2)],
    )
    sobre = preparar_sobre_evento(
        pedido, organizacion_id=3, evento_externo_id="evento-55",
        evento_externo=tipo, cantidades=cantidades,
    )
    configuracion = SimpleNamespace(estado="activo", sucursal_operativa_id=10)
    vinculo = SimpleNamespace(
        organizacion_id=3, tienda_nube_cuenta_id=7,
        mercado_libre_cuenta_id=None, sucursal_operativa_id=10, estado="activo",
    )
    item = SimpleNamespace(id=20, organizacion_id=3, sku="PP6040H", activo=True)
    existencia = SimpleNamespace(
        id=30, organizacion_id=3, sucursal_operativa_id=10,
        item_inventario_id=20, control_activo=True,
        stock_actual=10, stock_reservado=2, stock_bloqueado=1,
    )
    return sobre, configuracion, vinculo, item, existencia


def _validar(sobre, configuracion, vinculo, item, existencia, reservas=()):
    return validar_sobre_evento(
        sobre, configuracion=configuracion, vinculos=[vinculo],
        items_inventario=[item], existencias=[existencia], reservas=reservas,
    )


def test_reserva_calcula_delta_sin_mutar_existencia():
    sobre, configuracion, vinculo, item, existencia = _base()
    resultado = _validar(sobre, configuracion, vinculo, item, existencia)
    assert resultado["estado"] == "listo_sin_ejecutar"
    assert resultado["puede_ejecutar"] is False
    assert resultado["lineas"][0]["disponible"] == 7
    assert resultado["lineas"][0]["delta_reservado"] == 2
    assert existencia.stock_reservado == 2
    assert existencia.stock_actual == 10


def test_bloquea_stock_insuficiente_y_automatizacion_inactiva():
    sobre, configuracion, vinculo, item, existencia = _base(cantidades={"PP6040H": 8})
    configuracion.estado = "validacion"
    resultado = _validar(sobre, configuracion, vinculo, item, existencia)
    assert resultado["estado"] == "bloqueado"
    assert any("desactivada" in error for error in resultado["bloqueos"])
    assert any("Stock disponible insuficiente" in error for error in resultado["bloqueos"])


def test_consumo_parcial_exige_reserva_del_mismo_canal_y_referencia():
    sobre, configuracion, vinculo, item, existencia = _base(
        tipo="shipped", cantidades={"PP6040H": 1},
    )
    reserva_ajena = SimpleNamespace(
        organizacion_id=3, existencia_sucursal_id=30, estado="activa",
        canal="Mercado Libre", referencia_externa="TN-55", cantidad=2,
    )
    bloqueado = _validar(
        sobre, configuracion, vinculo, item, existencia, [reserva_ajena],
    )
    assert bloqueado["estado"] == "bloqueado"
    reserva_correcta = SimpleNamespace(
        organizacion_id=3, existencia_sucursal_id=30, estado="activa",
        canal="Tienda Nube", referencia_externa="TN-55", cantidad=2,
    )
    listo = _validar(
        sobre, configuracion, vinculo, item, existencia, [reserva_correcta],
    )
    assert listo["estado"] == "listo_sin_ejecutar"
    assert listo["lineas"][0]["delta_actual"] == -1
    assert listo["lineas"][0]["delta_reservado"] == -1


def test_devolucion_siempre_deriva_a_revision_sin_deltas():
    sobre, configuracion, vinculo, item, existencia = _base(
        tipo="returned", cantidades={"PP6040H": 1},
    )
    resultado = _validar(sobre, configuracion, vinculo, item, existencia)
    assert resultado["estado"] == "revision_manual"
    assert resultado["lineas"][0]["delta_actual"] == 0
    assert resultado["lineas"][0]["delta_reservado"] == 0
    assert resultado["puede_ejecutar"] is False


def test_bloquea_cuenta_ajena_y_sku_sin_control():
    sobre, configuracion, vinculo, item, existencia = _base()
    vinculo.tienda_nube_cuenta_id = 99
    existencia.control_activo = False
    resultado = _validar(sobre, configuracion, vinculo, item, existencia)
    assert resultado["estado"] == "bloqueado"
    assert any("vínculo empresarial único" in error for error in resultado["bloqueos"])
    assert any("Control de existencia desactivado" in error for error in resultado["bloqueos"])


def test_panel_documenta_matriz_y_servicio_no_muta_stock():
    panel = Path("templates/admin_inventario.html").read_text(encoding="utf-8")
    servicio = Path("services/inventario_eventos_canal.py").read_text(encoding="utf-8")
    assert "Matriz de prevalidación multicanal" in panel
    assert "Una devolución nunca ajusta stock automáticamente" in panel
    assert "stock_actual =" not in servicio
    assert "stock_reservado =" not in servicio
