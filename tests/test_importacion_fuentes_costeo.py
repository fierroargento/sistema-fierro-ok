from pathlib import Path

from services.importacion_fuentes_costeo import DEFINICIONES, sugerir_mapeo_fuente


def test_cada_conjunto_tiene_campos_y_plantilla_propia():
    assert set(DEFINICIONES) == {"insumos", "empleados", "costos-fijos", "fichas"}
    assert "precio_unitario" in DEFINICIONES["insumos"]["campos"]
    assert "horas_productivas" in DEFINICIONES["empleados"]["campos"]
    assert "importe_mensual" in DEFINICIONES["costos-fijos"]["campos"]
    assert "tipo_linea" in DEFINICIONES["fichas"]["campos"]


def test_mapeo_acepta_encabezados_excel():
    mapeo = sugerir_mapeo_fuente("insumos", ["CÓDIGO", "NOMBRE", "PRECIO_UNITARIO"])
    assert mapeo == {"0": "codigo", "1": "nombre", "2": "precio_unitario"}


def test_interfaz_expone_mapeo_exportaciones_y_orden_correcto():
    template = Path("templates/admin_importacion_fuentes_costeo.html").read_text(encoding="utf-8")
    fuentes = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")
    estilos = Path("static/admin_comercial.css").read_text(encoding="utf-8")
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    assert "Seleccionar todo" in template
    assert "Exportar Excel" in template and "Exportar PDF" in template
    assert "Importar insumos" in fuentes and "Importar fichas" in fuentes
    assert "#fichas-tecnicas { order: 8; }" in estilos
    assert 'grid-template-columns: repeat(5' in estilos
    assert "exportar_fuente_costeo" in rutas


def test_importador_productivo_no_conecta_canales():
    contenido = Path("services/importacion_fuentes_costeo.py").read_text(encoding="utf-8")
    for prohibido in ("MercadoLibre", "TiendaNube", "Pedido", "Webhook", "OAuth"):
        assert prohibido not in contenido
