from pathlib import Path

from services.importacion_combos_costeo import sugerir_mapeo_combo, validar_mapeo_combo


def test_sugiere_columnas_especificas_combo():
    assert sugerir_mapeo_combo([
        "SKU_COMBO", "SKU_COMPONENTE", "CANTIDAD", "UNIDAD", "OTRA",
    ]) == {"0": "sku_combo", "1": "sku_componente", "2": "cantidad", "3": "unidad", "4": ""}


def test_sugiere_encabezados_con_guiones_y_espacios():
    assert sugerir_mapeo_combo(["sku-combo", "SKU COMPONENTE"]) == {
        "0": "sku_combo", "1": "sku_componente",
    }


def test_exige_combo_componente_y_cantidad():
    try:
        validar_mapeo_combo({"0": "sku_combo"})
    except ValueError as error:
        assert "SKU componente" in str(error)
        assert "Cantidad" in str(error)
    else:
        raise AssertionError("Se acepto un mapeo incompleto.")


def test_interfaz_y_exportaciones_combo():
    template = Path("templates/admin_importacion_combos.html").read_text(encoding="utf-8")
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    assert "Seleccionar todo" in template
    assert "Solo validar" in template
    assert "Confirmar importación" in template
    assert "plantilla_combos_costeo" in rutas
    assert "exportar_combos_costeo" in rutas


def test_motor_combo_aislado():
    contenido = Path("services/importacion_combos_costeo.py").read_text(encoding="utf-8")
    for prohibido in ("MercadoLibre", "TiendaNube", "Pedido", "ListaPrecio", "Webhook"):
        assert prohibido not in contenido


def test_modos_y_unidad_se_validan_antes_de_confirmar():
    motor = Path("services/importacion_combos_costeo.py").read_text(encoding="utf-8")
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    assert 'modo="crear_actualizar"' in motor
    assert "unidades diferentes" in motor
    assert 'lote.modo == "solo_validar"' in rutas
