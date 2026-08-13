from pathlib import Path

from services.catalogo_ficha_integral import (
    calcular_completitud,
    numero_visual,
    parsear_atributos,
    parsear_atributos_estructurados,
    parsear_variantes,
    parsear_variantes_estructuradas,
)


def test_atributos_y_variantes_tienen_formato_controlado():
    assert parsear_atributos("Tamaño=60x40\nMaterial=Hierro") == {
        "Tamaño": "60x40", "Material": "Hierro",
    }
    assert parsear_variantes("PP-NEGRA | Color=Negro") == [{
        "sku": "PP-NEGRA", "opciones": "Color=Negro", "activa": True,
    }]


def test_presentacion_logistica_elimina_decimales_innecesarios():
    assert numero_visual("3000.000") == "3000"
    assert numero_visual("30.500") == "30.5"


def test_completitud_bloquea_fichas_incompletas():
    class Ficha:
        marca = categoria = descripcion_corta = descripcion_publica = None
        material = contenido_paquete = None
        imagenes_json = "[]"

    class Producto:
        peso_gr = largo_cm = ancho_cm = alto_cm = None

    porcentaje, faltantes = calcular_completitud(Ficha(), Producto())
    assert porcentaje == 0
    assert "imagen" in faltantes
    assert "peso embalado" in faltantes


def test_ficha_cubre_publicacion_logistica_variantes_y_cross_sell():
    modelo = Path("models/catalogo_producto.py").read_text(encoding="utf-8")
    servicio = Path("services/catalogos_admin_comercial.py").read_text(encoding="utf-8")
    plantilla = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    migraciones = Path("services/migraciones_saas.py").read_text(encoding="utf-8")
    for contrato in (
        "atributos_json", "variantes_json", "imagenes_json", "canales_json",
        "relaciones_json", "completitud_pct", "peso_producto_gr",
    ):
        assert contrato in modelo
        assert contrato in migraciones
    assert "subir_imagenes" in servicio
    assert "La ficha no puede quedar disponible" in servicio
    for texto in (
        "Producto y embalaje", "Atributos y variantes", "Imágenes",
        "Canales de publicación", "Cross-sell y relaciones", "Completitud actual",
    ):
        assert texto in plantilla
    assert "no publica ni sincroniza" in plantilla.lower()


def test_fichas_existentes_calculan_completitud_y_navegan_por_bloques():
    consultas = Path("services/comercial_consultas.py").read_text(encoding="utf-8")
    plantilla = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    javascript = Path("static/admin_comercial.js").read_text(encoding="utf-8")
    assert "inclusion.completitud_visual = porcentaje" in consultas
    assert "inclusion.faltantes_visual" in consultas
    assert "data-catalog-jump" in plantilla
    assert "data-catalog-panel" in plantilla
    assert "Falta completar:" in plantilla
    assert "formulario.scrollTo" in javascript


def test_tabla_catalogo_cabe_en_escritorio_sin_perder_datos():
    plantilla = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    estilos = Path("static/admin_comercial.css").read_text(encoding="utf-8")
    assert 'class="comercial-table catalog-products-table"' in plantilla
    assert "<th>SKU</th>" not in plantilla
    assert "maestro {{ i.producto.sku }}" in plantilla
    assert "i.faltantes_visual.split(', ')[:3]" in plantilla
    assert ".catalog-products-table { width:100%;table-layout:fixed; }" in estilos
    assert ".source-catalog-table { overflow-x:visible; }" in estilos
    assert "min-width:780px" in estilos


def test_navegacion_de_ficha_permanece_visible_y_sin_mover_el_fondo():
    plantilla = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    estilos = Path("static/admin_comercial.css").read_text(encoding="utf-8")
    javascript = Path("static/admin_comercial.js").read_text(encoding="utf-8")
    assert 'class="catalog-dialog-head"' in plantilla
    assert 'class="catalog-dialog-nav"' in plantilla
    assert "overflow:hidden" in estilos
    assert "max-height:calc(100vh - 30px)" in estilos
    assert "overscroll-behavior:contain" in estilos
    assert ".catalog-dialog-nav button.is-active" in estilos
    assert "panel.offsetTop - compensacionFija()" in javascript
    assert 'formulario.addEventListener("scroll"' in javascript
    assert 'activarPestana("identidad")' in javascript


class FormularioListas(dict):
    def getlist(self, nombre):
        valor = self.get(nombre, [])
        return valor if isinstance(valor, list) else [valor]


def test_atributos_y_variantes_se_guardan_como_filas_estructuradas():
    formulario = FormularioListas({
        "atributo_nombre": ["Color", "Material"],
        "atributo_valor": ["Negro", "Hierro"],
        "variante_sku": ["PP6040H-N"],
        "variante_opciones": ["Color=Negro"],
        "variante_estado": ["activa"],
        "variante_peso_gr": ["3200,5"],
        "variante_largo_cm": ["42"],
        "variante_ancho_cm": ["36"],
        "variante_alto_cm": ["4,5"],
        "variante_imagen_url": ["https://img/negra.webp"],
    })
    assert parsear_atributos_estructurados(formulario) == {
        "Color": "Negro", "Material": "Hierro",
    }
    assert parsear_variantes_estructuradas(formulario) == [{
        "sku": "PP6040H-N", "opciones": "Color=Negro", "estado": "activa",
        "activa": True, "peso_gr": "3200.5", "largo_cm": "42",
        "ancho_cm": "36", "alto_cm": "4.5",
        "imagen_url": "https://img/negra.webp",
    }]


def test_editor_de_variantes_es_operable_sin_texto_libre():
    plantilla = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    javascript = Path("static/admin_comercial.js").read_text(encoding="utf-8")
    estilos = Path("static/admin_comercial.css").read_text(encoding="utf-8")
    for contrato in (
        "data-add-attribute", "data-add-variant", "variante_sku",
        "variante_estado", "variante_imagen_url",
        "Logística e imagen",
    ):
        assert contrato in plantilla
    assert "plantilla.content.cloneNode(true)" in javascript
    assert "[data-remove-row]" in javascript
    assert ".catalog-variant-main" in estilos
    assert 'name="variante_stock"' not in plantilla
    assert "se administran desde Inventario" in plantilla
