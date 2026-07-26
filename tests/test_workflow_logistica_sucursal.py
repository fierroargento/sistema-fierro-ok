from types import SimpleNamespace

from services.workflow_logistica_sucursal import (
    aplicar_sucursal_elegida_al_pedido,
    normalizar_sucursal_operativa,
)


def test_normaliza_sucursal_via_cargo():
    sucursal = {
        "id": "vc-2",
        "nombre": "Terminal Formosa",
        "direccion": "Av. Gutnisky 2615",
        "localidad": "Formosa",
        "provincia": "Formosa",
    }

    datos = normalizar_sucursal_operativa(sucursal)

    assert datos["id"] == "vc-2"
    assert datos["nombre"] == "Terminal Formosa"
    assert datos["direccion"] == "Av. Gutnisky 2615"


def test_normaliza_sucursal_correo():
    sucursal = {
        "agencyId": "correo-1",
        "name": "Correo Centro",
        "address": "San Martin 123",
        "city": "Viedma",
        "province": "Rio Negro",
        "postalCode": "8500",
    }

    datos = normalizar_sucursal_operativa(sucursal)

    assert datos["id"] == "correo-1"
    assert datos["nombre"] == "Correo Centro"
    assert datos["direccion"] == "San Martin 123"
    assert datos["localidad"] == "Viedma"
    assert datos["provincia"] == "Rio Negro"
    assert datos["cp"] == "8500"


def test_aplica_sucursal_al_pedido_sin_commit_ni_mensajes():
    pedido = SimpleNamespace(
        sucursal_nombre="",
        direccion="",
        localidad="",
        provincia="",
        codigo_postal="3600",
        empresa_envio="",
        tipo_entrega="",
        ia_sucursales_ofrecidas='["vc-1", "vc-2"]',
        correo_sucursales_ofrecidas="[]",
        ia_requiere_operador=True,
        ia_esperando_respuesta=True,
        ml_mensajes_pendientes=True,
    )

    sucursal = {
        "id": "vc-2",
        "nombre": "Terminal Formosa Boleteria 5",
        "direccion": "Av. Gutnisky Nro.2615",
        "localidad": "Formosa",
        "provincia": "Formosa",
    }

    ok = aplicar_sucursal_elegida_al_pedido(
        pedido,
        sucursal,
        transporte="Vía Cargo",
    )

    assert ok is True
    assert pedido.sucursal_nombre == "Terminal Formosa Boleteria 5"
    assert pedido.direccion == "Av. Gutnisky Nro.2615"
    assert pedido.localidad == "Formosa"
    assert pedido.provincia == "Formosa"
    assert pedido.empresa_envio == "Vía Cargo"
    assert pedido.tipo_entrega == "Sucursal"
    assert pedido.ia_sucursales_ofrecidas is None
    assert pedido.correo_sucursales_ofrecidas is None
    assert pedido.ia_requiere_operador is False
    assert pedido.ia_esperando_respuesta is False
    assert pedido.ml_mensajes_pendientes is False


def test_no_pisa_transporte_existente():
    pedido = SimpleNamespace(
        sucursal_nombre="",
        direccion="",
        localidad="",
        provincia="",
        empresa_envio="Via Cargo",
        tipo_entrega="",
    )

    ok = aplicar_sucursal_elegida_al_pedido(
        pedido,
        {
            "nombre": "Agencia Formosa",
            "direccion": "Av. Italia 1856",
            "localidad": "Formosa",
            "provincia": "Formosa",
        },
        transporte="Correo Argentino",
    )

    assert ok is True
    assert pedido.empresa_envio == "Via Cargo"


def test_no_aplica_si_no_hay_nombre():
    pedido = SimpleNamespace()

    ok = aplicar_sucursal_elegida_al_pedido(
        pedido,
        {"direccion": "Sin nombre"},
        transporte="Via Cargo",
    )

    assert ok is False



def test_marca_resumen_sucursal_confirmada():
    from services.workflow_logistica_sucursal import marca_resumen_sucursal_confirmada

    marca = marca_resumen_sucursal_confirmada(
        1,
        {"nombre": "Terminal Formosa Boleteria 5"},
    )

    assert marca == "Sucursal confirmada por opción 2: Terminal Formosa Boleteria 5"


def test_agrega_marca_resumen_sucursal_confirmada_una_sola_vez():
    from services.workflow_logistica_sucursal import agregar_marca_resumen_sucursal_confirmada

    resumen = "Datos completos"
    sucursal = {"nombre": "Terminal Formosa Boleteria 5"}

    nuevo = agregar_marca_resumen_sucursal_confirmada(resumen, 1, sucursal)
    repetido = agregar_marca_resumen_sucursal_confirmada(nuevo, 1, sucursal)

    assert nuevo == "Datos completos | Sucursal confirmada por opción 2: Terminal Formosa Boleteria 5"
    assert repetido == nuevo


def test_no_agrega_marca_si_faltan_datos():
    from services.workflow_logistica_sucursal import agregar_marca_resumen_sucursal_confirmada

    assert agregar_marca_resumen_sucursal_confirmada("Datos completos", None, {"nombre": "X"}) == "Datos completos"
    assert agregar_marca_resumen_sucursal_confirmada("Datos completos", 1, {}) == "Datos completos"


def test_aplica_decision_sucursal_al_pedido():
    from types import SimpleNamespace

    from services.workflow_logistica_sucursal import (
        aplicar_decision_sucursal_al_pedido,
    )
    from services.workflow_sucursal_decision import (
        DecisionSucursal,
    )

    pedido = SimpleNamespace(
        sucursal_nombre="",
        direccion="",
        localidad="",
        provincia="",
        codigo_postal="",
        empresa_envio="",
        tipo_entrega="",
        ia_sucursales_ofrecidas='["vc-1"]',
        correo_sucursales_ofrecidas=None,
        ia_requiere_operador=True,
        ia_esperando_respuesta=True,
        ml_mensajes_pendientes=True,
        ia_resumen="Datos completos",
    )
    decision = DecisionSucursal(
        seleccionada=True,
        sucursal={
            "id": "vc-1",
            "nombre": "Terminal Viedma",
            "direccion": "Ruta 3",
            "localidad": "Viedma",
            "provincia": "Rio Negro",
            "cp": "8500",
        },
        indice=0,
        transporte="via_cargo",
        motivo="sucursal_confirmada_por_opcion",
    )

    aplicado = aplicar_decision_sucursal_al_pedido(
        pedido,
        decision,
        transporte="Vía Cargo",
    )

    assert aplicado is True
    assert pedido.sucursal_nombre == "Terminal Viedma"
    assert pedido.direccion == "Ruta 3"
    assert pedido.localidad == "Viedma"
    assert pedido.provincia == "Rio Negro"
    assert pedido.codigo_postal == "8500"
    assert pedido.empresa_envio == "Vía Cargo"
    assert pedido.tipo_entrega == "Sucursal"
    assert pedido.ia_sucursales_ofrecidas is None
    assert pedido.ia_requiere_operador is False
    assert pedido.ia_esperando_respuesta is False
    assert pedido.ml_mensajes_pendientes is False
    assert (
        "Sucursal confirmada por opción 1: "
        "Terminal Viedma"
        in pedido.ia_resumen
    )


def test_no_aplica_decision_sucursal_no_seleccionada():
    from types import SimpleNamespace

    from services.workflow_logistica_sucursal import (
        aplicar_decision_sucursal_al_pedido,
    )
    from services.workflow_sucursal_decision import (
        DecisionSucursal,
    )

    pedido = SimpleNamespace(
        sucursal_nombre="",
        ia_resumen="Sin cambios",
    )
    decision = DecisionSucursal(
        seleccionada=False,
        motivo="sin_eleccion_explicita",
    )

    aplicado = aplicar_decision_sucursal_al_pedido(
        pedido,
        decision,
        transporte="Vía Cargo",
    )

    assert aplicado is False
    assert pedido.sucursal_nombre == ""
    assert pedido.ia_resumen == "Sin cambios"

class SessionSucursalDetectadaFake:
    def __init__(self, error=None):
        self.error = error
        self.commits = 0

    def commit(self):
        self.commits += 1
        if self.error:
            raise self.error


def crear_pedido_sucursal_detectada(**cambios):
    datos = {
        "sucursal_nombre": "",
        "direccion": "",
        "localidad": "",
        "provincia": "",
        "codigo_postal": "8500",
        "empresa_envio": "",
        "tipo_entrega": "",
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def sucursal_detectada():
    return {
        "nombre": "Correo Centro",
        "direccion": "San Martín 123",
        "localidad": "Viedma",
        "provincia": "Río Negro",
        "cp": "9999",
    }


def test_aplica_y_persiste_sucursal_detectada_legacy():
    from services.workflow_logistica_sucursal import (
        aplicar_y_persistir_sucursal_detectada,
    )

    pedido = crear_pedido_sucursal_detectada()
    session = SessionSucursalDetectadaFake()
    eventos = []

    resultado = aplicar_y_persistir_sucursal_detectada(
        pedido,
        sucursal_detectada(),
        db_session=session,
        limpiar_revision_fn=lambda valor: (
            eventos.append(("limpiar", valor))
        ),
        marcar_pendiente_fn=lambda valor: (
            eventos.append(("marcar", valor))
        ),
    )

    assert resultado.aplicada is True
    assert resultado.persistida is True
    assert pedido.sucursal_nombre == "Correo Centro"
    assert pedido.direccion == "San Martín 123"
    assert pedido.localidad == "Viedma"
    assert pedido.provincia == "Río Negro"
    assert pedido.empresa_envio == "Vía Cargo"
    assert pedido.tipo_entrega == "Sucursal"
    assert pedido.codigo_postal == "8500"
    assert eventos == [
        ("limpiar", pedido),
        ("marcar", pedido),
    ]
    assert session.commits == 1


def test_adaptador_no_pisa_transporte_existente():
    from services.workflow_logistica_sucursal import (
        aplicar_y_persistir_sucursal_detectada,
    )

    pedido = crear_pedido_sucursal_detectada(
        empresa_envio="Correo Argentino",
    )

    resultado = aplicar_y_persistir_sucursal_detectada(
        pedido,
        sucursal_detectada(),
        db_session=SessionSucursalDetectadaFake(),
        limpiar_revision_fn=lambda _pedido: None,
        marcar_pendiente_fn=lambda _pedido: None,
    )

    assert resultado.aplicada is True
    assert pedido.empresa_envio == "Correo Argentino"


def test_adaptador_no_pisa_sucursal_confirmada():
    from services.workflow_logistica_sucursal import (
        aplicar_y_persistir_sucursal_detectada,
    )

    pedido = crear_pedido_sucursal_detectada(
        sucursal_nombre="Correo Norte",
    )
    session = SessionSucursalDetectadaFake()
    llamadas = []

    resultado = aplicar_y_persistir_sucursal_detectada(
        pedido,
        sucursal_detectada(),
        db_session=session,
        limpiar_revision_fn=llamadas.append,
        marcar_pendiente_fn=llamadas.append,
    )

    assert resultado.aplicada is False
    assert pedido.sucursal_nombre == "Correo Norte"
    assert llamadas == []
    assert session.commits == 0


def test_adaptador_tolera_errores_auxiliares():
    from services.workflow_logistica_sucursal import (
        aplicar_y_persistir_sucursal_detectada,
    )

    pedido = crear_pedido_sucursal_detectada()
    session = SessionSucursalDetectadaFake()
    logs = []

    def fallar_limpieza(_pedido):
        raise RuntimeError("fallo limpieza")

    def fallar_marca(_pedido):
        raise RuntimeError("fallo marca")

    resultado = aplicar_y_persistir_sucursal_detectada(
        pedido,
        sucursal_detectada(),
        db_session=session,
        limpiar_revision_fn=fallar_limpieza,
        marcar_pendiente_fn=fallar_marca,
        log_fn=logs.append,
    )

    assert resultado.aplicada is True
    assert resultado.persistida is True
    assert resultado.errores_auxiliares == (
        "fallo limpieza",
        "fallo marca",
    )
    assert session.commits == 1
    assert len(logs) == 2


def test_adaptador_tolera_error_de_commit():
    from services.workflow_logistica_sucursal import (
        aplicar_y_persistir_sucursal_detectada,
    )

    pedido = crear_pedido_sucursal_detectada()
    session = SessionSucursalDetectadaFake(
        RuntimeError("fallo commit"),
    )

    resultado = aplicar_y_persistir_sucursal_detectada(
        pedido,
        sucursal_detectada(),
        db_session=session,
        limpiar_revision_fn=lambda _pedido: None,
        marcar_pendiente_fn=lambda _pedido: None,
    )

    assert resultado.aplicada is True
    assert resultado.persistida is False
    assert resultado.error_persistencia == "fallo commit"
    assert session.commits == 1
