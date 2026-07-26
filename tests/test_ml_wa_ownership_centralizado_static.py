from pathlib import Path


def test_app_usa_canal_manager_para_ownership_ml_wa():
    texto = Path("app.py").read_text(encoding="utf-8")

    assert "ml_wa_estado_bloquea_respuesta_ml" in texto
    assert "wa_tiene_ownership_real = bool(" not in texto
    assert 'wa_estado_actual != "requiere_operador"' not in texto


def test_canal_manager_expone_regla_central_ownership():
    texto = Path("services/canal_manager.py").read_text(encoding="utf-8")

    assert "def ml_wa_estado_bloquea_respuesta_ml(" in texto
    assert "_ml_puede_responder_eleccion_sucursal_con_wa_estado" in texto
    assert "ml_wa_estado_bloquea_respuesta_ml(" in texto


def test_auto_respuesta_delega_ownership_completo():
    texto = Path("app.py").read_text(encoding="utf-8")

    inicio = texto.index(
        "def ia_auto_responder_post_analisis("
    )
    fin = texto.find("\ndef ", inicio + 1)
    bloque = texto[inicio:fin]

    assert (
        "evaluar_ownership_wa_para_respuesta_ml("
        in bloque
    )
    assert (
        "obtener_estado_conversacional_fn=("
        in bloque
    )
    assert "wa_tiene_ownership_real" not in bloque
    assert (
        "canal_activo_actual in "
        '("wa", "whatsapp")'
        not in bloque
    )
    assert (
        "resultado_ownership.motivo"
        in bloque
    )
