from pathlib import Path


def test_bootstrap_crea_identidad_tn_antes_de_consultar_pedidos():
    fuente = Path("services/bootstrap_base_datos.py").read_text(encoding="utf-8")

    posicion_tn = fuente.index('"asegurar_columnas_integracion_tn"')
    posicion_backfill = fuente.index('"backfill_ml_identidad_cuenta_pedidos"')

    assert posicion_tn < posicion_backfill
