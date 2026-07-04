from pathlib import Path


APP = Path("app.py").read_text(encoding="utf-8")


def test_funciones_actuales_ui_y_estado_siguen_existiendo():
    funciones = [
        "def accion_sugerida_pedido",
        "def accion_principal_pedido",
        "def texto_boton_estado",
        "def primer_paso_pendiente_carga",
        "def puede_imprimir_pedido",
        "def puede_editar_pedido",
        "def puede_avanzar_segun_rol",
        "def puede_avanzar_pedido",
    ]

    for funcion in funciones:
        assert funcion in APP


def test_puede_avanzar_pedido_sigue_concentrando_bloqueos_actuales():
    idx = APP.index("def puede_avanzar_pedido")
    bloque = APP[idx: idx + 4500]

    assert "motor_bloqueo" in bloque
    assert "siguiente_estado" in bloque
    assert "debe_bloquear_etiqueta_lista_por_cross_sell" in bloque
    assert "debe_bloquear_avance_por_agregado" in bloque
    assert "puede_avanzar_segun_rol" in bloque


def test_accion_principal_pedido_sigue_concentrando_acciones_ui_actuales():
    idx = APP.index("def accion_principal_pedido")
    bloque = APP[idx: idx + 5000]

    assert "debe_mostrar_accion_completar_carga" in bloque
    assert "primer_paso_pendiente_carga" in bloque
    assert "puede_imprimir_pedido" in bloque
    assert "lanzar_impresion" in bloque
    assert "avanzar_pedido" in bloque


def test_puede_imprimir_pedido_sigue_limitado_por_estado_y_rol():
    idx = APP.index("def puede_imprimir_pedido")
    bloque = APP[idx: idx + 1200]

    assert "rol_actual()" in bloque
    assert "Estado.ETIQUETA_LISTA" in bloque
    assert '"admin"' in bloque
    assert '"despacho"' in bloque
