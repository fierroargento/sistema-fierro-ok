import modules.whatsapp.flows as flows
import modules.whatsapp.flows_transporte as flows_transporte
from modules.whatsapp.config import WA_FALTA_ELEGIR_TRANSPORTE


class PedidoDummy:
    def __init__(self):
        self.id = 123
        self.id_venta = "2000016989132354"
        self.canal = "Mercado Libre"
        self.tipo_ml = "Acordas"
        self.telefono = "+5493517381115"
        self.cliente = "LA"
        self.nombre = "LA"
        self.empresa_envio = "Via Cargo"
        self.tipo_entrega = "Sucursal"
        self.sucursal_nombre = ""
        self.direccion = "Pje. Brizuela 3928"
        self.localidad = "Cordoba Capital"
        self.provincia = "Cordoba"
        self.codigo_postal = "5014"
        self.ia_sucursales_ofrecidas = ""
        self.ia_requiere_operador = False
        self.wa_estado = ""
        self.items = []


def test_wa_cerrar_datos_completos_ofrece_sucursal_via_cargo_si_falta_confirmar(monkeypatch):
    pedido = PedidoDummy()
    mensajes = []
    estados = []

    monkeypatch.setattr(
        flows_transporte,
        "normalizar_telefono_service",
        lambda telefono: "5493517381115",
    )
    monkeypatch.setattr(
        flows_transporte,
        "_cargar_sucursales_via_cargo_candidatas",
        lambda pedido, limite=3: [
            {
                "nombre": "Agencia Velez Sarsfield",
                "direccion": "Velez Sarsfield 1580",
                "localidad": "Cordoba Capital",
                "provincia": "Cordoba",
                "cp": "5014",
            }
        ],
    )
    monkeypatch.setattr(
        flows_transporte,
        "wa_enviar_texto",
        lambda tel, texto, **kwargs: mensajes.append(texto) or True,
    )
    monkeypatch.setattr(
        flows,
        "_guardar_estado_wa",
        lambda pedido, estado, tel=None: (
            setattr(pedido, "wa_estado", estado),
            estados.append(estado),
        ),
    )

    resultado = flows_transporte.wa_cerrar_datos_completos(pedido)

    assert resultado is True
    assert pedido.wa_estado == WA_FALTA_ELEGIR_TRANSPORTE
    assert estados == [WA_FALTA_ELEGIR_TRANSPORTE]
    assert "Cargo" in mensajes[0]
    assert "Agencia Velez Sarsfield" in mensajes[0]
    assert "Velez Sarsfield 1580" in mensajes[0]


def test_wa_iniciar_cross_sell_no_inicia_si_falta_sucursal_via_cargo(monkeypatch):
    pedido = PedidoDummy()

    monkeypatch.setattr(
        flows,
        "wa_enviar_texto",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("No debia enviar cross-sell")
        ),
    )

    resultado = flows.wa_iniciar_cross_sell(
        pedido,
        origen="bot",
        forzar=True,
    )

    assert resultado is False


def test_respuesta_cross_sell_prioriza_sucursal_pendiente_y_no_ia(monkeypatch):
    pedido = PedidoDummy()
    llamadas = []

    monkeypatch.setattr(
        flows,
        "normalizar_telefono_service",
        lambda telefono: "5493517381115",
    )
    monkeypatch.setattr(
        flows,
        "wa_ofrecer_sucursales_via_cargo_pendientes",
        lambda pedido, texto_cliente=None: llamadas.append(texto_cliente) or True,
    )
    monkeypatch.setattr(
        flows,
        "_wa_responder_con_ia",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("No debia usar IA general")
        ),
    )

    flows.wa_procesar_respuesta_cross_sell(
        pedido,
        "Donde es Via Cargo cerca de mi domicilio?",
        "KIT_PALA",
        0,
    )

    assert llamadas == ["Donde es Via Cargo cerca de mi domicilio?"]


def test_aplica_sucursal_wa_reemplaza_domicilio_y_cp():
    pedido = PedidoDummy()
    pedido.canal = "Tienda Nube"
    pedido.direccion = (
        "Fray Justo Santamaria de Oro "
        "2663 Piso/Depto: 4C"
    )
    pedido.codigo_postal = "9999"
    pedido.localidad = "Capital Federal"
    pedido.provincia = "Capital Federal"
    pedido.ia_esperando_respuesta = True
    pedido.ml_mensajes_pendientes = True

    aplicado = (
        flows_transporte
        ._aplicar_sucursal_pedido(
            pedido,
            {
                "id": 5788,
                "nombre": "Agencia Palermo",
                "direccion": "Guemes Nro.4326",
                "localidad": "Palermo",
                "provincia": "Capital Federal",
                "cp": 1425,
            },
        )
    )

    assert aplicado is True
    assert pedido.sucursal_nombre == "Agencia Palermo"
    assert pedido.direccion == "Guemes Nro.4326"
    assert pedido.codigo_postal == "1425"
    assert pedido.localidad == "Palermo"
    assert pedido.provincia == "Capital Federal"
    assert pedido.empresa_envio == "Via Cargo"
    assert pedido.tipo_entrega == "Sucursal"
    assert pedido.ia_sucursales_ofrecidas is None
    assert pedido.ia_requiere_operador is False
    assert pedido.ia_esperando_respuesta is False
    assert pedido.ml_mensajes_pendientes is False
