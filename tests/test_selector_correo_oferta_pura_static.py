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


def test_preparacion_correo_usa_oferta_pura():
    bloque = _bloque_funcion(
        "preparar_oferta_sucursales_correo_pedido"
    )

    assert (
        "services.workflow_correo_sucursal_oferta"
        in bloque
    )
    assert "preparar_oferta_sucursales_correo" in bloque
    assert (
        "oferta_correo = preparar_oferta_sucursales_correo"
        in bloque
    )
    assert (
        "ResultadoPreparacionOfertaCorreo.preparada"
        in bloque
    )
    assert "db.session.commit()" not in bloque


def test_preparacion_correo_mantiene_raw_compatible():
    bloque = _bloque_funcion(
        "preparar_oferta_sucursales_correo_pedido"
    )

    assert (
        "sucs = sucursales[:limite_sucursales]"
        in bloque
    )
    assert (
        "aplicar_oferta_sucursales_correo_al_pedido"
        in bloque
    )
    assert "oferta_correo.ids" in bloque
