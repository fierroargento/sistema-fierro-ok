from pathlib import Path

from services.importacion_fuentes_costeo import (
    DEFINICIONES,
    aplicar_modo_vista_fuentes,
    presentar_vista_fuentes,
    resumir_vista_fuentes,
    sugerir_mapeo_fuente,
)


def test_cada_conjunto_tiene_campos_y_plantilla_propia():
    assert set(DEFINICIONES) == {"insumos", "empleados", "recursos", "costos-fijos", "fichas"}
    assert "precio_unitario" in DEFINICIONES["insumos"]["campos"]
    assert "horas_productivas" in DEFINICIONES["empleados"]["campos"]
    assert "porcentaje_cargas" in DEFINICIONES["empleados"]["campos"]
    assert "porcentaje_dedicacion" in DEFINICIONES["recursos"]["campos"]
    assert "importe_periodo" in DEFINICIONES["costos-fijos"]["campos"]
    assert "periodicidad" in DEFINICIONES["costos-fijos"]["campos"]
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


def test_las_cinco_plantillas_tienen_contratos_completos():
    for tipo, config in DEFINICIONES.items():
        assert config["titulo"]
        assert len(config["ejemplo"]) == len(config["campos"])
    servicio = Path("services/importacion_fuentes_costeo.py").read_text(encoding="utf-8")
    assert "def plantilla_excel_fuente" in servicio
    assert "libro.save(salida)" in servicio


def test_historial_distingue_validacion_sin_cambios():
    template = Path("templates/admin_importacion_fuentes_costeo.html").read_text(encoding="utf-8")
    assert "Validado sin cambios" in template
    assert "Sin modificaciones" in template


def test_vista_previa_cierra_configuracion_y_permite_reabrirla():
    template = Path("templates/admin_importacion_fuentes_costeo.html").read_text(encoding="utf-8")
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    assert "{% if mostrar_configuracion %}" in template
    assert "Volver a configurar" in template
    assert "Cerrar configuración" in template
    assert 'request.args.get("configurar") == "1"' in rutas
    assert "mostrar_configuracion=mostrar_configuracion" in rutas


def test_vista_previa_presenta_columnas_monedas_y_estados_legibles():
    columnas, filas = presentar_vista_fuentes("insumos", [{
        "numero": 2,
        "datos": {
            "codigo": "1955", "nombre": "Barra ángulo", "tipo": "materia_prima",
            "unidad_medida": "metro", "precio_unitario": "1910.8009090909", "proveedor": "CODIMAT",
        },
        "accion": "crear", "errores": [],
    }])
    assert [columna["nombre"] for columna in columnas] == [
        "Código", "Nombre", "Tipo", "Unidad de medida", "Precio unitario", "Proveedor",
    ]
    assert filas[0]["valores"] == [
        "1955", "Barra ángulo", "Materia prima", "metro", "$ 1.910,80", "CODIMAT",
    ]
    assert filas[0]["accion"] == "Crear"
    assert filas[0]["clase_accion"] == "create"


def test_vista_previa_rechazada_muestra_detalle_y_guion_para_vacios():
    _columnas, filas = presentar_vista_fuentes("insumos", [{
        "numero": 3,
        "datos": {"codigo": "X", "nombre": "Prueba"},
        "accion": "rechazado", "errores": ["Precio unitario no es válido"],
    }])
    assert "—" in filas[0]["valores"]
    assert filas[0]["accion"] == "Rechazado"
    assert filas[0]["clase_accion"] == "rejected"
    assert filas[0]["detalle"] == "Precio unitario no es válido"


def test_fichas_distinguen_altas_y_actualizaciones():
    servicio = Path("services/importacion_fuentes_costeo.py").read_text(encoding="utf-8")
    assert "perfil.insumos_costeo" in servicio
    assert "perfil.costos_fijos_costeo" in servicio
    assert "perfil.operaciones_costeo" in servicio
    assert 'ids["operacion_id"] = existente.id' in servicio
    assert "El código ya pertenece a otra unidad" in servicio


def test_resumen_y_modo_se_calculan_sin_mutar_vista():
    original = [
        {"accion": "crear", "errores": []},
        {"accion": "actualizar", "errores": []},
        {"accion": "rechazado", "errores": ["dato inválido"]},
    ]
    solo_crear = aplicar_modo_vista_fuentes(original, "solo_crear")

    assert original[1]["accion"] == "actualizar"
    assert solo_crear[1]["accion"] == "rechazado"
    assert resumir_vista_fuentes(solo_crear) == {
        "crear": 1,
        "actualizar": 0,
        "rechazado": 2,
        "aplicables": 1,
    }


def test_confirmacion_revalida_audita_y_pide_confirmacion_humana():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    template = Path("templates/admin_importacion_fuentes_costeo.html").read_text(encoding="utf-8")

    assert "vista_actual = previsualizar_fuentes(" in rutas
    assert "Los datos cambiaron desde la validación" in rutas
    assert "Confirmó importación productiva" in rutas
    assert "resumen_vista.aplicables" in template
    assert "¿Confirmás la importación?" in template


def test_confirmacion_oculta_vista_previa_y_muestra_cierre_compacto():
    template = Path("templates/admin_importacion_fuentes_costeo.html").read_text(encoding="utf-8")

    assert "{% if vista and lote.estado != 'confirmado' %}" in template
    assert "Importación finalizada" in template
    assert "Nueva importación" in template
    assert "Volver a fuentes de costo" in template
    assert "{{ lote.creados }}" in template
    assert "{{ lote.actualizados }}" in template
    assert "{{ lote.rechazados }}" in template
    assert "v='20260810-2'" in template

    estilos = Path("static/admin_comercial.css").read_text(encoding="utf-8")
    assert ".import-completed-actions .comercial-primary" in estilos
    assert "min-height:40px" in estilos
    assert "width:auto" in estilos


def test_exportaciones_son_reimportables_y_conservan_todos_los_campos():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")

    assert 'encabezados = [nombre.upper() for nombre, _obligatorio in config["campos"].values()]' in rutas
    assert "v.proveedor_referencia if v else" in rutas
    assert "v.sueldo_base_centavos / 100" in rutas
    assert "v.usa_porcentaje_general" in rutas
    assert "v.porcentaje_cargas" in rutas
    assert "v.horas_productivas if v else" in rutas
    assert '"si" if r.integra_costo_produccion else "no"' in rutas
    assert "v.comprobante_referencia if v else" in rutas
    assert 'x.porcentaje_asignacion, x.unidades_mensuales' in rutas


def test_validaciones_especificas_rechazan_datos_productivos_inconsistentes():
    servicio = Path("services/importacion_fuentes_costeo.py").read_text(encoding="utf-8")

    assert "TIPOS_INSUMO_VALIDOS" in servicio
    assert "CRITERIOS_DISTRIBUCION_VALIDOS" in servicio
    assert "Las horas productivas no pueden superar las horas mensuales" in servicio
    assert "Un costo informativo debe quedar sin distribuir" in servicio
    assert "El costo fijo no está marcado como productivo" in servicio
    assert "El archivo contiene una fila duplicada" in servicio


def test_reimportacion_actualiza_maestros_y_operaciones_sin_duplicarlos():
    administrador = Path("services/fuentes_costo_admin.py").read_text(encoding="utf-8")
    composicion = Path("services/composicion_costo_producto.py").read_text(encoding="utf-8")
    importador = Path("services/importacion_fuentes_costeo.py").read_text(encoding="utf-8")

    assert "insumo.nombre =" in administrador
    assert "empleado.sector =" in administrador
    assert "costo.criterio_distribucion =" in administrador
    assert "registro_id=formulario.get(\"operacion_id\")" in administrador
    assert "registro_id=None" in composicion
    assert 'ids["operacion_id"] = existente.id' in importador
