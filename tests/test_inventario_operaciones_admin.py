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


def test_inventario_hereda_ancho_tarjetas_y_botones_del_panel():
    plantilla = leer("templates/admin_inventario.html")
    estilos = leer("static/admin_comercial.css")
    assert "v='20260814-3'" in plantilla
    assert ".main:has(.inventory-admin)" in estilos
    assert "width:min(1380px,100%)" in estilos
    assert ".inventory-admin .source-section" in estilos
    assert ".inventory-admin button" in estilos
    assert ".inventory-admin .table-shell" in estilos


def test_automatizacion_de_pedidos_queda_preparada_pero_bloqueada():
    plantilla = Path("templates/admin_inventario.html").read_text(encoding="utf-8")
    servicio = Path("services/inventario_pedidos.py").read_text(encoding="utf-8")
    assert "Automatización de pedidos" in plantilla
    assert "Preparada, sin conexión productiva" in plantilla
    assert "Escribí AUTOMATIZAR" in plantilla
    assert "inventario físico inicial" in servicio
    assert "automatizacion_puede_mutar" in servicio
    assert "Simulador de pedidos" in plantilla
    assert "Simular sin modificar" in plantilla
    assert "Historial de simulaciones" in plantilla
    assert '"sim:" + clave_evento_pedido' in servicio


def test_ciclo_de_vida_del_inventario_es_explicito_y_seguro():
    plantilla = leer("templates/admin_inventario.html")
    servicio = leer("services/inventario_operaciones_admin.py")
    assert "actualizar_modulo_inventario" in plantilla
    assert "Escribí ACTIVAR" in plantilla
    assert "actualizar_ubicacion" in plantilla
    assert "actualizar_item" in plantilla
    assert '!= "ACTIVAR"' in servicio
    assert "tiene stock o controles activos" in servicio
    assert "Activá primero el módulo" in servicio


def test_badges_de_desplegables_no_se_estiran():
    estilos = leer("static/admin_comercial.css")
    assert ".source-catalog>summary>.source-count" in estilos
    assert "flex:0 0 auto" in estilos


def test_guardado_de_ubicaciones_regresa_al_panel_y_explica_el_bloqueo():
    plantilla = leer("templates/admin_inventario.html")
    rutas = leer("modules/admin/inventario/routes.py")
    estilos = leer("static/admin_comercial.css")
    assert 'id="configuracion-inventario"' in plantilla
    assert 'name="panel_destino" value="configuracion-inventario"' in plantilla
    assert "Activá primero el módulo" in plantilla
    assert "abrir_configuracion" in rutas
    assert 'request.form.get("panel_destino")' in rutas
    assert '"configuracion-inventario"' in rutas
    assert ".inventory-switch input" in estilos
    assert "width:18px!important" in estilos
    assert ".location-actions" in estilos


def test_configuracion_de_ubicaciones_es_tabular_y_se_edita_en_dialogos():
    plantilla = leer("templates/admin_inventario.html")
    javascript = leer("static/admin_comercial.js")
    estilos = leer("static/admin_comercial.css")
    assert "inventory-locations-table" in plantilla
    assert "data-open-inventory-dialog" in plantilla
    assert 'id="new-inventory-location"' in plantilla
    assert 'id="prepare-inventory-sku"' in plantilla
    assert "Guardar cambios" in plantilla
    assert "iniciarDialogosInventario" in javascript
    assert "showModal" in javascript
    assert ".inventory-config-toolbar" in estilos
    assert ".inventory-dialog-form" in estilos


def test_existencias_permiten_gestionar_control_y_limites_sin_tocar_stock():
    plantilla = leer("templates/admin_inventario.html")
    servicio = leer("services/inventario_operaciones_admin.py")
    rutas = leer("modules/admin/inventario/routes.py")
    estilos = leer("static/admin_comercial.css")
    assert "actualizar_control_existencia" in plantilla
    assert "Guardar control" in plantilla
    assert 'name="stock_minimo"' in plantilla
    assert 'name="stock_maximo"' in plantilla
    assert 'name="control_activo"' in plantilla
    assert 'id="existencias-inventario"' in plantilla
    assert '"actualizar_control_existencia"' in servicio
    assert "cantidades comprometidas o reservas activas" in servicio
    assert "existencia.stock_minimo = minimo" in servicio
    assert "existencia.stock_maximo = maximo" in servicio
    assert "existencia.stock_actual =" not in servicio.split(
        'if accion == "actualizar_control_existencia":', 1
    )[1].split('if accion == "crear_reserva":', 1)[0]
    assert '"existencias-inventario"' in rutas
    assert ".inventory-control-summary" in estilos


def test_panel_oculta_altas_redundantes_y_previsualiza_conteos():
    consultas = leer("services/inventario_consultas.py")
    plantilla = leer("templates/admin_inventario.html")
    servicio = leer("services/inventario_operaciones_admin.py")
    rutas = leer("modules/admin/inventario/routes.py")
    assert "combinaciones_faltantes" in consultas
    assert "sucursales_con_control" in consultas
    assert "Todas las existencias están configuradas" in plantilla
    assert 'name="combinacion"' in plantilla
    assert "Guardar y revisar diferencias" in plantilla
    assert "Conciliar y ajustar stock" in plantilla
    assert "Descargar Excel" in plantilla
    assert "Importar Excel" in plantilla
    assert "conteo_pendiente" in servicio
    assert "control_activo=True" in servicio
    assert "descargar_plantilla_conteo" in rutas
    assert "importar_plantilla_conteo" in rutas
