from pathlib import Path


def test_modelo_persiste_costos_porcentuales_separados():
    fuente = Path("models/regla_canal.py").read_text(encoding="utf-8-sig")
    assert "publicidad_pct = db.Column" in fuente
    assert "financiacion_pct = db.Column" in fuente
    assert "ck_regla_canal_costos_porcentuales" in fuente


def test_alta_administrativa_recibe_publicidad_y_financiacion():
    servicio = Path("services/comercial_admin.py").read_text(encoding="utf-8-sig")
    formulario = Path("templates/admin_comercial.html").read_text(encoding="utf-8-sig")
    assert 'publicidad_pct=formulario.get("publicidad_pct", 0)' in servicio
    assert 'financiacion_pct=formulario.get("financiacion_pct", 0)' in servicio
    assert 'name="publicidad_pct"' in formulario
    assert 'name="financiacion_pct"' in formulario


def test_migracion_es_aditiva_y_nace_en_cero():
    fuente = Path("services/migraciones_saas.py").read_text(encoding="utf-8-sig")
    bloque = fuente.split("def asegurar_costos_porcentuales_canal", 1)[1].split("def asegurar_obligaciones_ajustables", 1)[0]
    assert "ADD COLUMN" in bloque
    assert "NOT NULL DEFAULT 0" in bloque
    for prohibido in ("DROP ", "DELETE ", "UPDATE "):
        assert prohibido not in bloque


def test_motor_permanece_offline_y_sin_publicacion():
    fuente = Path("services/motor_comercial_canal.py").read_text(encoding="utf-8-sig").lower()
    for prohibido in ("requests", "urlopen", "db.session", "mercadolibre", "tiendanube", "webhook"):
        assert prohibido not in fuente
