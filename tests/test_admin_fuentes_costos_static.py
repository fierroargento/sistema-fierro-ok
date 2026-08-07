from pathlib import Path


def leer(ruta):
    return Path(ruta).read_text(encoding="utf-8")


def test_panel_tiene_ruta_independiente():
    rutas = leer("modules/admin/comercial/routes.py")
    assert '"/admin/comercial/fuentes-costos"' in rutas
    assert '"admin_fuentes_costos.html"' in rutas
    assert "procesar_accion_fuente_costo(" in rutas


def test_pantalla_separa_tres_fuentes():
    plantilla = leer("templates/admin_fuentes_costos.html")
    assert 'id="insumos"' in plantilla
    assert 'id="empleados"' in plantilla
    assert 'id="costos-fijos"' in plantilla
    assert "Financiación" not in plantilla
    assert "Mercado Libre" not in plantilla


def test_altas_iniciales_incluyen_version_vigente():
    servicio = leer("services/fuentes_costo_admin.py")
    assert 'accion == "crear_insumo"' in servicio
    assert "registrar_precio_insumo(" in servicio
    assert 'accion == "crear_empleado"' in servicio
    assert "registrar_costo_empleado(" in servicio
    assert 'accion == "crear_costo_fijo"' in servicio
    assert "registrar_importe_costo_fijo(" in servicio
    assert servicio.count("commit=False") == 3


def test_actualizaciones_crean_versiones_sin_editar_anteriores():
    servicio = leer("services/fuentes_costo_admin.py")
    assert 'accion == "actualizar_precio_insumo"' in servicio
    assert 'accion == "actualizar_costo_empleado"' in servicio
    assert 'accion == "actualizar_importe_costo_fijo"' in servicio
    assert ".precio_unitario_centavos =" not in servicio
    assert ".costo_mensual_total_centavos =" not in servicio
    assert ".importe_mensual_centavos =" not in servicio


def test_app_solo_cablea_modelos():
    app = leer("app.py")
    assert '"InsumoProductivo": InsumoProductivo' in app
    assert '"EmpleadoProductivo": EmpleadoProductivo' in app
    assert '"CostoFijoProductivo": CostoFijoProductivo' in app
    assert "fuentes_costo_admin" not in app
    assert "fuentes_costo_productivo import" not in app.split(
        "from models.fuentes_costo_productivo import", 1
    )[0]


def test_interfaz_usa_javascript_externo_y_responsive():
    plantilla = leer("templates/admin_fuentes_costos.html")
    javascript = leer("static/admin_fuentes_costos.js")
    estilos = leer("static/admin_comercial.css")
    assert "admin_fuentes_costos.js" in plantilla
    assert "<script>" not in plantilla
    assert "data-production-cost" in javascript
    assert plantilla.count("Ver historial") == 3
    assert ".source-grid" in estilos
    assert "@media (max-width: 560px)" in estilos
