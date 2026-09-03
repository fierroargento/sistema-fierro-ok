from pathlib import Path

from services.importacion_inclusiones_catalogo import (
    CAMPOS_INCLUSIONES,
    sugerir_mapeo_inclusiones,
    validar_mapeo_inclusiones,
)


def test_contrato_separa_inclusion_de_clasificacion_y_costos():
    assert set(CAMPOS_INCLUSIONES) == {
        "catalogo_codigo", "sku", "descripcion", "sku_comercial",
        "nombre_comercial", "marca", "categoria",
    }
    for campo in ("catalogo_codigo", "sku", "descripcion"):
        assert CAMPOS_INCLUSIONES[campo]["obligatorio"] is True


def test_sugiere_columnas_comunes():
    assert sugerir_mapeo_inclusiones([
        "CATALOGO", "SKU", "DESCRIPCIÓN", "NOMBRE COMERCIAL", "OTRA",
    ]) == {
        "0": "catalogo_codigo", "1": "sku", "2": "descripcion",
        "3": "nombre_comercial", "4": "",
    }


def test_mapeo_exige_identidad_y_descripcion():
    try:
        validar_mapeo_inclusiones({"0": "sku"})
    except ValueError as error:
        assert "Codigo de catalogo" in str(error)
        assert "Descripcion maestra" in str(error)
    else:
        raise AssertionError("Se acepto un mapeo incompleto.")


def test_servicio_nace_desconectado_de_canales_y_sin_activar():
    contenido = Path("services/importacion_inclusiones_catalogo.py").read_text(
        encoding="utf-8"
    )
    for prohibido in ("requests", "OAuth", "Webhook", "MercadoLibreCuenta"):
        assert prohibido not in contenido
    assert 'estado_comercial="borrador"' in contenido
    assert 'estado_disponibilidad="no_disponible"' in contenido
    assert "disponible=False" in contenido
    assert "activo=False" in contenido


def test_panel_expone_flujo_separado_con_vista_previa():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    template = Path(
        "templates/admin_importacion_inclusiones_catalogo.html"
    ).read_text(encoding="utf-8")
    assert "def importar_inclusiones_catalogo" in rutas
    assert "previsualizar_inclusiones" in rutas
    assert "Los datos cambiaron desde la validacion" in rutas
    assert "Importar productos por catálogo" in panel
    assert "Ningún dato fue modificado todavía" in template
    assert "No activa productos, no cambia precios" in template
