from services.ia_recolector_logistica import (
    debe_reencauzar_pp6040_sin_faltantes_service,
    tiene_motivo_operador_duro_recolector,
)


class Pedido:
    pass


def es_ml_acordas(_pedido):
    return True


def es_pp6040(_pedido):
    return True


def test_reencauza_pp6040_sin_faltantes_y_sin_motivo_duro():
    pedido = Pedido()

    assert debe_reencauzar_pp6040_sin_faltantes_service(
        pedido=pedido,
        resultado={"resumen": "cliente pasó datos completos pero antes faltaba CP"},
        faltantes=[],
        requiere_operador_final=True,
        es_ml_acordas_entrega_fn=es_ml_acordas,
        pedido_es_plegable_pp6040_fn=es_pp6040,
    )


def test_no_reencauza_si_hay_faltantes_reales():
    pedido = Pedido()

    assert not debe_reencauzar_pp6040_sin_faltantes_service(
        pedido=pedido,
        resultado={"resumen": "falta codigo postal"},
        faltantes=["codigo_postal"],
        requiere_operador_final=True,
        es_ml_acordas_entrega_fn=es_ml_acordas,
        pedido_es_plegable_pp6040_fn=es_pp6040,
    )


def test_no_reencauza_si_no_requiere_operador():
    pedido = Pedido()

    assert not debe_reencauzar_pp6040_sin_faltantes_service(
        pedido=pedido,
        resultado={"resumen": "datos completos"},
        faltantes=[],
        requiere_operador_final=False,
        es_ml_acordas_entrega_fn=es_ml_acordas,
        pedido_es_plegable_pp6040_fn=es_pp6040,
    )


def test_no_reencauza_motivo_duro_cancelacion_reclamo_o_retiro():
    pedido = Pedido()

    for resumen in [
        "cliente quiere cancelar",
        "hay reclamo por problema con producto",
        "quiere retirar personalmente",
        "pide cambio de modalidad",
    ]:
        assert tiene_motivo_operador_duro_recolector({"resumen": resumen})
        assert not debe_reencauzar_pp6040_sin_faltantes_service(
            pedido=pedido,
            resultado={"resumen": resumen},
            faltantes=[],
            requiere_operador_final=True,
            es_ml_acordas_entrega_fn=es_ml_acordas,
            pedido_es_plegable_pp6040_fn=es_pp6040,
        )


def test_no_reencauza_si_no_es_ml_o_no_es_pp6040():
    pedido = Pedido()

    assert not debe_reencauzar_pp6040_sin_faltantes_service(
        pedido=pedido,
        resultado={"resumen": "datos completos"},
        faltantes=[],
        requiere_operador_final=True,
        es_ml_acordas_entrega_fn=lambda _pedido: False,
        pedido_es_plegable_pp6040_fn=es_pp6040,
    )

    assert not debe_reencauzar_pp6040_sin_faltantes_service(
        pedido=pedido,
        resultado={"resumen": "datos completos"},
        faltantes=[],
        requiere_operador_final=True,
        es_ml_acordas_entrega_fn=es_ml_acordas,
        pedido_es_plegable_pp6040_fn=lambda _pedido: False,
    )
