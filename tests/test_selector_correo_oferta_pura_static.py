from pathlib import Path


SRC = Path("modules/transportes/selector.py").read_text(encoding="utf-8")


def _bloque_sugerir_correo():
    idx = SRC.index("def sugerir_sucursales_correo_pedido")
    fin = SRC.find("\ndef ", idx + 1)
    if fin == -1:
        fin = idx + 5000
    return SRC[idx:fin]


def test_selector_correo_usa_oferta_pura():
    bloque = _bloque_sugerir_correo()

    assert "services.workflow_correo_sucursal_oferta" in bloque
    assert "preparar_oferta_sucursales_correo" in bloque
    assert "oferta_correo = preparar_oferta_sucursales_correo" in bloque
    assert "return oferta_correo.mensaje" in bloque


def test_selector_correo_mantiene_guardado_raw_compatible():
    bloque = _bloque_sugerir_correo()

    assert "sucs = sucursales[:limite_sucursales]" in bloque
    assert "pedido.correo_sucursales_ofrecidas = json.dumps(sucs" in bloque
    assert "ids = oferta_correo.ids" in bloque


def test_selector_correo_sigue_siendo_quien_persiste_por_ahora():
    bloque = _bloque_sugerir_correo()

    assert "from app import db" in bloque
    assert "db.session.commit()" in bloque
