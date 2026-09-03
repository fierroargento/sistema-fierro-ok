from pathlib import Path

from services.importacion_logistica_catalogo import (
    CAMPOS_LOGISTICA,
    plantilla_logistica_catalogo,
    sugerir_mapeo_logistica,
    validar_mapeo_logistica,
)


def test_contrato_usa_identidad_comercial_y_campos_fisicos_tenant():
    assert CAMPOS_LOGISTICA["catalogo_codigo"]["obligatorio"] is True
    assert CAMPOS_LOGISTICA["sku_comercial"]["obligatorio"] is True
    assert "peso_producto_gr" in CAMPOS_LOGISTICA
    assert "alto_producto_cm" in CAMPOS_LOGISTICA
    assert "permite_correo" not in CAMPOS_LOGISTICA


def test_plantilla_y_automapeo_son_compatibles():
    encabezados = [
        definicion["nombre"].upper()
        for definicion in CAMPOS_LOGISTICA.values()
    ]
    mapeo = sugerir_mapeo_logistica(encabezados)
    assert mapeo["0"] == "catalogo_codigo"
    assert mapeo["1"] == "sku_comercial"
    assert mapeo["2"] == "peso_producto_gr"
    assert plantilla_logistica_catalogo() is not None


def test_mapeo_exige_identidad_y_al_menos_un_dato():
    try:
        validar_mapeo_logistica({"0": "catalogo_codigo", "1": "sku_comercial"})
    except ValueError as error:
        assert "al menos un dato" in str(error)
    else:
        raise AssertionError("Se acepto una importacion sin datos para actualizar.")


def test_flujo_es_desconectado_revalida_y_no_activa():
    servicio = Path("services/importacion_logistica_catalogo.py").read_text(
        encoding="utf-8"
    )
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    template = Path(
        "templates/admin_importacion_logistica_catalogo.html"
    ).read_text(encoding="utf-8")
    for prohibido in ("requests", "OAuth", "Webhook", "MercadoLibreCuenta"):
        assert prohibido not in servicio
    assert "Los datos cambiaron desde la validacion" in rutas
    assert "Confirmó importación de ficha física por catálogo" in rutas
    assert "No activa productos, no cambia precios" in template
    assert "celdas vacías conservan el dato actual" in template
