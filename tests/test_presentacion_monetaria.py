from services.presentacion_monetaria import formatear_centavos_ars


def test_formatea_centavos_con_convencion_argentina():
    assert formatear_centavos_ars(100_000_000) == "1.000.000,00"
    assert formatear_centavos_ars(568_182) == "5.681,82"
    assert formatear_centavos_ars(0) == "0,00"


def test_panel_usa_un_formateador_monetario_modular():
    from pathlib import Path

    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    template = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")
    assert "from services.presentacion_monetaria import formatear_centavos_ars" in rutas
    assert "formatear_centavos_ars=formatear_centavos_ars" in rutas
    assert template.count("formatear_centavos_ars(") >= 7
