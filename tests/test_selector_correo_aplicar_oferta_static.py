from pathlib import Path


SRC = Path("modules/transportes/selector.py").read_text(encoding="utf-8")


def _bloque_sugerir_correo():
    idx = SRC.index("def sugerir_sucursales_correo_pedido")
    fin = SRC.find("\ndef ", idx + 1)
    if fin == -1:
        fin = idx + 5000
    return SRC[idx:fin]


def test_selector_correo_usa_helper_aplicar_oferta():
    bloque = _bloque_sugerir_correo()

    assert "aplicar_oferta_sucursales_correo_al_pedido" in bloque
    assert "preparar_oferta_sucursales_correo" in bloque
    assert "canal_origen=canal_origen" in bloque


def test_selector_correo_ya_no_asigna_campos_operativos_a_mano():
    bloque = _bloque_sugerir_correo()

    assert 'pedido.empresa_envio = "Correo Argentino"' not in bloque
    assert 'pedido.tipo_entrega = "Sucursal"' not in bloque
    assert 'pedido.wa_estado = "falta_elegir_transporte"' not in bloque
    assert 'pedido.wa_ultimo_contacto = datetime.utcnow()' not in bloque


def test_selector_correo_sigue_persistiendo_por_ahora():
    bloque = _bloque_sugerir_correo()

    assert "from app import db" in bloque
    assert "db.session.commit()" in bloque
