from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]


def test_pedido_persiste_cuenta_tienda_nube_sin_backfill_automatico():
    modelo = RAIZ.joinpath("models/pedido.py").read_text(encoding="utf-8")
    app = RAIZ.joinpath("app.py").read_text(encoding="utf-8")
    assert "tn_cuenta_id" in modelo
    assert 'asegurar_columna_si_no_existe("tn_cuenta_id", "INTEGER")' in app
    assert "ix_pedido_tn_cuenta_id" in app
    assert 'pedido.tn_cuenta_id = getattr(cuenta_origen, "id", None)' in app
    assert "TiendaNubeCuenta.query.filter_by(store_id=store_id).first()" in app
    assert "backfill_tn" not in app
