from pathlib import Path


def test_snapshot_ml_contempla_todos_los_costos_del_motor():
    certificacion = Path("services/certificacion_offline_mercado_libre.py").read_text(encoding="utf-8")
    consolidacion = Path("services/consolidacion_offline_ml.py").read_text(encoding="utf-8")
    lotes = Path("services/lotes_offline_ml.py").read_text(encoding="utf-8")
    for componente in ("publicidad", "financiacion", "devoluciones"):
        assert f'"{componente}_centavos"' in certificacion
        assert f'("{componente}", "{componente}_centavos")' in consolidacion
        assert componente in lotes


def test_componentes_faltantes_bloquean_pero_no_generan_acciones():
    consolidacion = Path("services/consolidacion_offline_ml.py").read_text(encoding="utf-8")
    assert 'bloqueos.append(f"{nombre}_no_informada_en_snapshot")' in consolidacion
    assert "acciones = [] if bloqueos" in consolidacion
    assert '"bloqueada" if bloqueos' in consolidacion


def test_panel_explica_costos_y_archivos_requeridos():
    panel = Path("templates/admin_mercado_libre_offline.html").read_text(encoding="utf-8")
    assert "Publicidad $" in panel
    assert "Cuotas $" in panel
    assert "Devoluciones $" in panel
    assert "Si la política las exige y faltan" in panel


def test_modo_sombra_permanece_sin_transporte_ni_publicacion():
    fuentes = "\n".join(
        Path(ruta).read_text(encoding="utf-8").lower()
        for ruta in (
            "services/certificacion_offline_mercado_libre.py",
            "services/consolidacion_offline_ml.py",
            "services/lotes_offline_ml.py",
        )
    )
    for prohibido in ("requests", "urlopen", "access_token", "client_secret", "db.session"):
        assert prohibido not in fuentes
