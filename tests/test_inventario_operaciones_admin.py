from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]


def leer(ruta):
    return RAIZ.joinpath(ruta).read_text(encoding="utf-8")


def test_operaciones_quedan_modulares_y_tenant():
    servicio = leer("services/inventario_operaciones_admin.py")
    assert "def procesar_operacion_inventario" in servicio
    assert "_tenant(organizacion" in servicio
    for accion in (
        "crear_ubicacion", "preparar_items_catalogo", "crear_existencia_item",
        "crear_reserva", "cerrar_reserva", "crear_transferencia",
        "despachar_transferencia", "recibir_transferencia", "crear_conteo",
        "guardar_conteo", "conciliar_conteo",
    ):
        assert f'"{accion}"' in servicio


def test_interfaz_operativa_es_compacta_y_segura():
    plantilla = leer("templates/admin_inventario.html")
    assert plantilla.count('class="source-catalog"') >= 7
    assert "No publica cantidades" in plantilla or "no publica cantidades" in plantilla
    assert "Preparar SKU sin activar" in plantilla
    assert "Crear en cero" in plantilla
    assert "Guardar conteo sin ajustar" in plantilla
    assert "Conciliar y ajustar" in plantilla
    assert "confirm('Se aplicarán ajustes auditados" in plantilla


def test_transferencias_muestran_y_actualizan_transito():
    plantilla = leer("templates/admin_inventario.html")
    servicio = leer("services/inventario_saas.py")
    assert "En tránsito" in plantilla
    assert "transferencia.destino.stock_transito" in servicio
    assert "confirmar=False" in servicio


def test_movimientos_admiten_flush_para_transacciones_compuestas():
    nucleo = leer("services/inventario_nucleo.py")
    assert "confirmar=True" in nucleo
    assert "db_session.flush()" in nucleo
