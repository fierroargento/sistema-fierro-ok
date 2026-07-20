from types import SimpleNamespace

from services.workflow_sucursal_decision import (
    decidir_sucursal_correo_ofrecida,
    decidir_sucursal_ofrecida,
    decidir_sucursal_via_cargo_ofrecida,
    texto_consulta_sucursal,
    texto_parece_eleccion_sucursal,
)


SUCURSALES_VIA = [
    {
        "id": "vc-1",
        "nombre": "Agencia Formosa",
        "direccion": "Av. Italia Nro.1856",
        "localidad": "Formosa",
        "provincia": "Formosa",
    },
    {
        "id": "vc-2",
        "nombre": "Terminal Formosa Boleteria 5",
        "direccion": "Av. Gutnisky Nro.2615",
        "localidad": "Formosa",
        "provincia": "Formosa",
    },
    {
        "id": "vc-3",
        "nombre": "Otra Agencia",
        "direccion": "Calle 123",
        "localidad": "Formosa",
        "provincia": "Formosa",
    },
]


def test_via_cargo_detecta_sucursal_nro_2():
    decision = decidir_sucursal_via_cargo_ofrecida(
        texto="Sucursal Nro 2",
        sucursales_catalogo=SUCURSALES_VIA,
        ids_ofrecidas=["vc-1", "vc-2"],
    )

    assert decision.seleccionada is True
    assert decision.indice == 1
    assert decision.sucursal["nombre"] == "Terminal Formosa Boleteria 5"
    assert decision.requiere_operador is False


def test_via_cargo_detecta_opcion_2():
    decision = decidir_sucursal_via_cargo_ofrecida(
        texto="opcion 2",
        sucursales_catalogo=SUCURSALES_VIA,
        ids_ofrecidas=["vc-1", "vc-2"],
    )

    assert decision.seleccionada is True
    assert decision.indice == 1


def test_via_cargo_detecta_la_2():
    decision = decidir_sucursal_via_cargo_ofrecida(
        texto="la 2",
        sucursales_catalogo=SUCURSALES_VIA,
        ids_ofrecidas=["vc-1", "vc-2"],
    )

    assert decision.seleccionada is True
    assert decision.indice == 1


def test_via_cargo_opcion_fuera_de_rango_no_selecciona():
    decision = decidir_sucursal_via_cargo_ofrecida(
        texto="opcion 3",
        sucursales_catalogo=SUCURSALES_VIA,
        ids_ofrecidas=["vc-1", "vc-2"],
    )

    assert decision.seleccionada is False
    assert decision.motivo in {
        "sin_eleccion_explicita",
        "opcion_fuera_de_rango_o_id_no_encontrado",
    }


def test_via_cargo_mensaje_mixto_detecta_sucursal_y_consulta():
    decision = decidir_sucursal_via_cargo_ofrecida(
        texto="Sucursal Nro 2. Horarios para retirar?",
        sucursales_catalogo=SUCURSALES_VIA,
        ids_ofrecidas=["vc-1", "vc-2"],
    )

    assert decision.seleccionada is True
    assert decision.indice == 1
    assert decision.consulta_secundaria is True
    assert decision.requiere_operador is True


def test_consulta_sin_eleccion_no_selecciona_y_requiere_operador():
    decision = decidir_sucursal_via_cargo_ofrecida(
        texto="Que horarios tienen para retirar?",
        sucursales_catalogo=SUCURSALES_VIA,
        ids_ofrecidas=["vc-1", "vc-2"],
    )

    assert decision.seleccionada is False
    assert decision.requiere_operador is True
    assert decision.consulta_secundaria is True


def test_correo_usa_detector_inyectado_y_normaliza_resultado():
    pedido = SimpleNamespace(id=1)

    def detector(_pedido, texto):
        assert _pedido is pedido
        assert texto == "opcion 1"
        return {
            "agencyId": "correo-1",
            "name": "Correo Centro",
            "address": "San Martin 123",
            "city": "Viedma",
            "province": "Rio Negro",
        }

    decision = decidir_sucursal_correo_ofrecida(
        pedido=pedido,
        texto="opcion 1",
        detector_correo_fn=detector,
    )

    assert decision.seleccionada is True
    assert decision.transporte == "correo"
    assert decision.sucursal["id"] == "correo-1"
    assert decision.sucursal["nombre"] == "Correo Centro"
    assert decision.sucursal["direccion"] == "San Martin 123"


def test_router_general_delega_por_transporte():
    decision = decidir_sucursal_ofrecida(
        transporte="Via Cargo",
        texto="Sucursal Nro 2",
        sucursales_catalogo=SUCURSALES_VIA,
        ids_ofrecidas=["vc-1", "vc-2"],
    )

    assert decision.seleccionada is True
    assert decision.transporte == "via_cargo"


def test_helpers_texto():
    assert texto_parece_eleccion_sucursal("Sucursal Nro 2") is True
    assert texto_consulta_sucursal("Horarios para retirar?") is True

def test_decision_via_cargo_para_pedido_usa_opciones_guardadas():
    from services.workflow_sucursal_decision import (
        decidir_sucursal_via_cargo_para_pedido,
    )

    pedido = SimpleNamespace(
        ia_sucursales_ofrecidas='["vc-1", "vc-2"]',
    )

    decision = decidir_sucursal_via_cargo_para_pedido(
        pedido=pedido,
        texto="prefiero la segunda",
        sucursales_catalogo=SUCURSALES_VIA,
    )

    assert decision.seleccionada is True
    assert decision.indice == 1
    assert (
        decision.sucursal["nombre"]
        == "Terminal Formosa Boleteria 5"
    )


def test_decision_via_cargo_para_pedido_rechaza_ids_invalidos():
    from services.workflow_sucursal_decision import (
        decidir_sucursal_via_cargo_para_pedido,
    )

    pedido = SimpleNamespace(
        ia_sucursales_ofrecidas="{invalido",
    )

    decision = decidir_sucursal_via_cargo_para_pedido(
        pedido=pedido,
        texto="opcion 1",
        sucursales_catalogo=SUCURSALES_VIA,
    )

    assert decision.seleccionada is False
    assert decision.motivo == "sin_sucursales_ofrecidas"


def test_decision_via_cargo_para_pedido_conserva_fallback(
    monkeypatch,
):
    import services.workflow_sucursal_decision as workflow

    errores = []
    pedido = SimpleNamespace(
        ia_sucursales_ofrecidas='["vc-1", "vc-2"]',
    )

    def fallar_decision_central(**kwargs):
        raise RuntimeError(
            "fallo simulado del motor central"
        )

    monkeypatch.setattr(
        workflow,
        "decidir_sucursal_via_cargo_ofrecida",
        fallar_decision_central,
    )

    decision = (
        workflow.decidir_sucursal_via_cargo_para_pedido(
            pedido=pedido,
            texto="Sucursal Nro 2",
            sucursales_catalogo=SUCURSALES_VIA,
            log_error_fn=errores.append,
        )
    )

    assert len(errores) == 1
    assert decision.seleccionada is True
    assert decision.indice == 1
    assert decision.motivo == "fallback_legacy"
    assert (
        decision.sucursal["nombre"]
        == "Terminal Formosa Boleteria 5"
    )


def test_deteccion_ofrecidas_correo_pp6040_puede_continuar():
    from services.workflow_sucursal_decision import (
        evaluar_sucursales_ofrecidas_pedido,
    )

    llamadas = []
    pedido = SimpleNamespace(
        correo_sucursales_ofrecidas='["CA-1"]',
        ia_sucursales_ofrecidas=None,
    )

    resultado = evaluar_sucursales_ofrecidas_pedido(
        pedido,
        pedido_es_plegable_fn=lambda valor: (
            llamadas.append(valor) or True
        ),
    )

    assert resultado.correo_ofrecidas is True
    assert resultado.via_cargo_ofrecidas is False
    assert resultado.puede_detectar is True
    assert llamadas == []


def test_deteccion_ofrecidas_via_pp6040_no_continua():
    from services.workflow_sucursal_decision import (
        evaluar_sucursales_ofrecidas_pedido,
    )

    pedido = SimpleNamespace(
        correo_sucursales_ofrecidas=None,
        ia_sucursales_ofrecidas='["VC-1"]',
    )

    resultado = evaluar_sucursales_ofrecidas_pedido(
        pedido,
        pedido_es_plegable_fn=lambda _pedido: True,
    )

    assert resultado.correo_ofrecidas is False
    assert resultado.via_cargo_ofrecidas is True
    assert resultado.puede_detectar is False


def test_deteccion_ofrecidas_via_no_plegable_continua():
    from services.workflow_sucursal_decision import (
        evaluar_sucursales_ofrecidas_pedido,
    )

    pedido = SimpleNamespace(
        correo_sucursales_ofrecidas=None,
        ia_sucursales_ofrecidas='["VC-1"]',
    )

    resultado = evaluar_sucursales_ofrecidas_pedido(
        pedido,
        pedido_es_plegable_fn=lambda _pedido: False,
    )

    assert resultado.correo_ofrecidas is False
    assert resultado.via_cargo_ofrecidas is True
    assert resultado.puede_detectar is True


def test_deteccion_sin_ofrecidas_no_evalua_pp6040():
    from services.workflow_sucursal_decision import (
        evaluar_sucursales_ofrecidas_pedido,
    )

    llamadas = []
    pedido = SimpleNamespace(
        correo_sucursales_ofrecidas=None,
        ia_sucursales_ofrecidas=None,
    )

    resultado = evaluar_sucursales_ofrecidas_pedido(
        pedido,
        pedido_es_plegable_fn=lambda valor: (
            llamadas.append(valor) or False
        ),
    )

    assert resultado.correo_ofrecidas is False
    assert resultado.via_cargo_ofrecidas is False
    assert resultado.puede_detectar is False
    assert llamadas == []
