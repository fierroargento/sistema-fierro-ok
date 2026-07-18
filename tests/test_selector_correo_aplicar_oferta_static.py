from pathlib import Path


SRC = Path(
    "modules/transportes/selector.py"
).read_text(encoding="utf-8-sig")


def _bloque_funcion(nombre):
    idx = SRC.index(f"def {nombre}")
    fin = SRC.find("\ndef ", idx + 1)

    if fin == -1:
        fin = len(SRC)

    return SRC[idx:fin]


def test_preparacion_correo_usa_helper_aplicar_oferta():
    bloque = _bloque_funcion(
        "preparar_oferta_sucursales_correo_pedido"
    )

    assert (
        "aplicar_oferta_sucursales_correo_al_pedido"
        in bloque
    )
    assert "preparar_oferta_sucursales_correo" in bloque
    assert "canal_origen=canal_origen" in bloque
    assert "db.session.commit()" not in bloque


def test_preparacion_correo_no_asigna_campos_operativos_a_mano():
    bloque = _bloque_funcion(
        "preparar_oferta_sucursales_correo_pedido"
    )

    assert (
        'pedido.empresa_envio = "Correo Argentino"'
        not in bloque
    )
    assert 'pedido.tipo_entrega = "Sucursal"' not in bloque
    assert (
        'pedido.wa_estado = "falta_elegir_transporte"'
        not in bloque
    )
    assert (
        "pedido.wa_ultimo_contacto = datetime.utcnow()"
        not in bloque
    )


def test_wrapper_correo_sigue_persistiendo_por_ahora():
    bloque = _bloque_funcion(
        "sugerir_sucursales_correo_pedido"
    )

    assert (
        "preparar_oferta_sucursales_correo_pedido"
        in bloque
    )
    assert "from app import db" in bloque
    assert "db.session.commit()" in bloque
    assert "db.session.rollback()" in bloque
    assert "return resultado.mensaje" in bloque
