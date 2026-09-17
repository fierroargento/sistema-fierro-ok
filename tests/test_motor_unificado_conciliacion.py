from pathlib import Path


def test_snapshot_de_venta_conserva_todos_los_costos_del_canal():
    modelo = Path("models/conciliacion_ventas_canal.py").read_text(encoding="utf-8")
    servicio = Path("services/conciliacion_liquidaciones_canal.py").read_text(encoding="utf-8")
    for nombre in (
        "publicidad_esperada_centavos",
        "financiacion_esperada_centavos",
        "devoluciones_esperadas_centavos",
    ):
        assert nombre in modelo
        assert nombre in servicio
    assert "liquidar_precio(" in servicio
    assert "publicidad_pct=getattr(regla_canal" in servicio
    assert "financiacion_pct=getattr(regla_canal" in servicio
    assert "devoluciones_pct=getattr(regla_canal" in servicio


def test_migracion_es_aditiva_y_compatible_con_historial_existente():
    fuente = Path("services/migraciones_saas.py").read_text(encoding="utf-8")
    bloque = fuente.split("def asegurar_desglose_liquidacion_canal", 1)[1].split(
        "def asegurar_obligaciones_ajustables", 1
    )[0]
    assert "ADD COLUMN" in bloque
    assert "NOT NULL DEFAULT 0" in bloque
    for prohibido in ("DROP ", "DELETE ", "UPDATE "):
        assert prohibido not in bloque


def test_bootstrap_aplica_la_migracion_sin_conectar_canales():
    bootstrap = Path("services/bootstrap_base_datos.py").read_text(encoding="utf-8")
    assert bootstrap.count("asegurar_desglose_liquidacion_canal") == 2


def test_panel_y_excel_explican_el_desglose_de_la_liquidacion():
    panel = Path("templates/admin_conciliacion_canal.html").read_text(encoding="utf-8")
    servicio = Path("services/conciliacion_liquidaciones_canal.py").read_text(encoding="utf-8")
    assert "Publicidad $" in panel and "Cuotas $" in panel and "Devoluciones $" in panel
    assert '"PUBLICIDAD_ESPERADA"' in servicio
    assert '"FINANCIACION_ESPERADA"' in servicio
    assert '"DEVOLUCIONES_ESPERADAS"' in servicio


def test_conciliacion_permanece_offline_y_sin_movimientos_automaticos():
    fuente = Path("services/conciliacion_liquidaciones_canal.py").read_text(encoding="utf-8").lower()
    for prohibido in ("requests", "access_token", "oauth", "webhook", "mercadolibre", "tiendanube"):
        assert prohibido not in fuente
