from pathlib import Path


def _leer(ruta):
    return Path(ruta).read_text(encoding="utf-8")


def test_panel_permite_administrar_politicas_desconectadas():
    panel = _leer("templates/admin_inventario.html")
    rutas = _leer("modules/admin/inventario/routes.py")
    assert 'value="crear_politica_disponibilidad"' in panel
    assert 'value="actualizar_politica_disponibilidad"' in panel
    assert 'value="politicas-disponibilidad"' in panel
    assert '"politicas-disponibilidad"' in rutas
    assert "Escribí PREVISUALIZAR" in panel
    assert 'name="vinculo_canal_comercial_id"' in panel
    assert "Cuenta empresarial exacta" in panel
    assert 'id="buscar-producto-politica"' in panel
    assert 'role="combobox"' in panel
    assert 'id="producto-politica"' in panel


def test_producto_politica_se_busca_y_conserva_id_validado():
    javascript = _leer("static/admin_comercial.js")
    estilos = _leer("static/admin_comercial.css")
    panel = _leer("templates/admin_inventario.html")

    assert "iniciarBuscadorProductoPolitica()" in javascript
    assert 'getElementById("buscar-producto-politica")' in javascript
    assert 'getElementById("producto-politica")' in javascript
    assert "productos.filter" in javascript
    assert "selector.value = producto.value" in javascript
    assert 'setCustomValidity("Elegí un producto de la lista.")' in javascript
    assert ".inventory-policy-form .product-master-field > small" in estilos
    assert ".inventory-policy-form .product-combobox-options button" in estilos
    assert "background: #fff" in estilos
    assert "white-space: normal" in estilos
    assert "overflow-x: hidden" in estilos
    assert "20260820-2" in panel


def test_servicio_mantiene_sobreventa_y_publicacion_bloqueadas():
    servicio = _leer("services/inventario_admin.py")
    calculo = _leer("services/inventario_disponibilidad_comercial.py")
    assert 'accion == "actualizar_politica_disponibilidad"' in servicio
    assert "politica.permite_sin_stock = False" in servicio
    assert '!= "PREVISUALIZAR"' in servicio
    assert "La venta sin stock permanece bloqueada" in servicio
    assert "vinculo_canal_comercial_id=vinculo.id" in servicio
    assert '"puede_publicar": False' in calculo
    assert "requests" not in calculo


def test_alta_nace_desactivada_y_sin_sobreventa():
    servicio = _leer("services/inventario_admin.py")
    bloque = servicio.split(
        'if accion == "crear_politica_disponibilidad":', 1
    )[1].split(
        'if accion == "actualizar_politica_disponibilidad":', 1
    )[0]
    assert "activa=False" in bloque
    assert "permite_sin_stock=False" in bloque
