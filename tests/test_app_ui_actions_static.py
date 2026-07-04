from pathlib import Path


APP = Path("app.py").read_text(encoding="utf-8")
DETALLE = Path("templates/detalle_pedido.html").read_text(encoding="utf-8")


def test_app_define_helper_accion_ui_pedido():
    assert "def accion_ui_pedido" in APP

    idx = APP.index("def accion_ui_pedido")
    bloque = APP[idx: idx + 900]

    assert "resolver_accion_ui_pedido" in bloque
    assert "accion_principal_pedido" in bloque
    assert "accion_sugerida_pedido" in bloque
    assert "rol_actual()" in bloque


def test_app_expone_accion_ui_pedido_al_contexto_template():
    assert '"accion_ui_pedido": accion_ui_pedido' in APP


def test_detalle_usa_accion_ui_para_resolver_accion_principal():
    assert "{% set accion_ui = accion_ui_pedido(pedido, 'detalle') %}" in DETALLE
    assert "{% set accion = accion_ui.accion %}" in DETALLE


def test_detalle_muestra_mensaje_si_no_hay_boton_por_permiso():
    assert "{% if accion_ui.mensaje %}" in DETALLE
    assert "{{ accion_ui.mensaje }}" in DETALLE
    assert "Sin acción" in DETALLE
