from pathlib import Path


def _bloque_detectar_sucursal():
    texto = Path("app.py").read_text(
        encoding="utf-8"
    )
    inicio = texto.index(
        "def detectar_sucursal(pedido, mensaje):"
    )
    fin = texto.find("\ndef ", inicio + 1)
    if fin == -1:
        fin = len(texto)
    return texto[inicio:fin]


def test_app_detectar_sucursal_rutea_solo_correo():
    bloque = _bloque_detectar_sucursal()

    assert (
        'if "correo" not in transporte_actual:'
        in bloque
    )
    assert (
        "decidir_sucursal_correo_ofrecida"
        in bloque
    )
    assert (
        "detectar_sucursal_correo_ofrecida"
        in bloque
    )
    assert (
        "detector_correo_fn="
        "detectar_sucursal_correo_ofrecida"
        in bloque
    )
    assert (
        "decision_correo.seleccionada"
        in bloque
    )


def test_app_detector_no_conserva_via_cargo_legacy():
    texto = Path("app.py").read_text(
        encoding="utf-8"
    )
    bloque = _bloque_detectar_sucursal()

    assert (
        'with open("via_cargo_sucursales.json"'
        not in bloque
    )
    assert "[VIA CARGO]" not in bloque
    assert (
        "_texto_parece_eleccion_sucursal"
        not in texto
    )
    assert "_es_consulta_no_eleccion" in texto
