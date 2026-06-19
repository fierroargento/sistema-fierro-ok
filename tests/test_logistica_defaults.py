from services.logistica_defaults import aplicar_default_via_cargo_sucursal_ml_acordas
from tests.fixtures.pedido_factory import ItemFake, PedidoFake


def test_ml_acordas_no_pp6040_aplica_via_cargo_sucursal_por_defecto():
    pedido = PedidoFake(
        canal="Mercado Libre",
        ml_tipo="Acordás la Entrega",
        empresa_envio="",
        tipo_entrega="",
        items=[ItemFake(sku="PF8050J", descripcion="Parrilla De Hierro 80x50")],
    )

    modificado = aplicar_default_via_cargo_sucursal_ml_acordas(pedido)

    assert modificado is True
    assert pedido.empresa_envio == "Vía Cargo"
    assert pedido.tipo_entrega == "Sucursal"


def test_ml_acordas_pp6040_no_fuerza_via_cargo():
    pedido = PedidoFake(
        canal="Mercado Libre",
        ml_tipo="Acordás la Entrega",
        empresa_envio="",
        tipo_entrega="",
        items=[ItemFake(sku="PP6040H", descripcion="Parrilla plegable")],
    )

    modificado = aplicar_default_via_cargo_sucursal_ml_acordas(pedido)

    assert modificado is False
    assert pedido.empresa_envio == ""
    assert pedido.tipo_entrega == ""


def test_no_pisa_transporte_o_tipo_ya_definidos():
    pedido = PedidoFake(
        canal="Mercado Libre",
        ml_tipo="Acordás la Entrega",
        empresa_envio="Andreani",
        tipo_entrega="Domicilio",
        items=[ItemFake(sku="PF8050J", descripcion="Parrilla De Hierro 80x50")],
    )

    modificado = aplicar_default_via_cargo_sucursal_ml_acordas(pedido)

    assert modificado is False
    assert pedido.empresa_envio == "Andreani"
    assert pedido.tipo_entrega == "Domicilio"


def test_no_aplica_fuera_de_ml_acordas():
    pedido = PedidoFake(
        canal="Tienda Nube",
        ml_tipo="",
        empresa_envio="",
        tipo_entrega="",
        items=[ItemFake(sku="PF8050J", descripcion="Parrilla De Hierro 80x50")],
    )

    modificado = aplicar_default_via_cargo_sucursal_ml_acordas(pedido)

    assert modificado is False
    assert pedido.empresa_envio == ""
    assert pedido.tipo_entrega == ""

class ItemLogisticaFake:
    def __init__(self, sku="", descripcion=""):
        self.sku = sku
        self.descripcion = descripcion


class PedidoLogisticaFake:
    def __init__(self):
        self.canal = "Mercado Libre"
        self.ml_tipo = "Acordás la Entrega"
        self.items = [ItemLogisticaFake(sku="BRASERO80", descripcion="Brasero grande")]
        self.codigo_postal = "8400"
        self.empresa_envio = ""
        self.tipo_entrega = ""
        self.costo_envio_sucursal = None
        self.costo_envio = None
        self.ia_resumen = ""


def test_default_acordas_prioriza_correo_si_costo_menor_al_umbral(monkeypatch):
    from services.logistica_defaults import aplicar_default_via_cargo_sucursal_ml_acordas

    monkeypatch.setenv("CORREO_MAX_COSTO_SUCURSAL_ACORDAS", "15000")

    pedido = PedidoLogisticaFake()

    modificado = aplicar_default_via_cargo_sucursal_ml_acordas(
        pedido,
        cotizar_correo_fn=lambda cp, tipo: {
            "disponible": True,
            "precio": 12000,
        },
    )

    assert modificado is True
    assert pedido.empresa_envio == "Correo Argentino"
    assert pedido.tipo_entrega == "Sucursal"
    assert pedido.costo_envio_sucursal == 12000
    assert pedido.costo_envio == 12000
    assert "Correo Argentino sucursal priorizado" in pedido.ia_resumen


def test_default_acordas_mantiene_via_cargo_si_correo_supera_umbral(monkeypatch):
    from services.logistica_defaults import aplicar_default_via_cargo_sucursal_ml_acordas

    monkeypatch.setenv("CORREO_MAX_COSTO_SUCURSAL_ACORDAS", "15000")

    pedido = PedidoLogisticaFake()

    modificado = aplicar_default_via_cargo_sucursal_ml_acordas(
        pedido,
        cotizar_correo_fn=lambda cp, tipo: {
            "disponible": True,
            "precio": 22000,
        },
    )

    assert modificado is True
    assert pedido.empresa_envio == "Vía Cargo"
    assert pedido.tipo_entrega == "Sucursal"


def test_default_acordas_mantiene_via_cargo_si_umbral_cero(monkeypatch):
    from services.logistica_defaults import aplicar_default_via_cargo_sucursal_ml_acordas

    monkeypatch.setenv("CORREO_MAX_COSTO_SUCURSAL_ACORDAS", "0")

    pedido = PedidoLogisticaFake()

    modificado = aplicar_default_via_cargo_sucursal_ml_acordas(
        pedido,
        cotizar_correo_fn=lambda cp, tipo: {
            "disponible": True,
            "precio": 12000,
        },
    )

    assert modificado is True
    assert pedido.empresa_envio == "Vía Cargo"
    assert pedido.tipo_entrega == "Sucursal"


def test_default_acordas_no_pisa_decision_existente(monkeypatch):
    from services.logistica_defaults import aplicar_default_via_cargo_sucursal_ml_acordas

    monkeypatch.setenv("CORREO_MAX_COSTO_SUCURSAL_ACORDAS", "15000")

    pedido = PedidoLogisticaFake()
    pedido.empresa_envio = "Andreani"
    pedido.tipo_entrega = "Domicilio"

    modificado = aplicar_default_via_cargo_sucursal_ml_acordas(
        pedido,
        cotizar_correo_fn=lambda cp, tipo: {
            "disponible": True,
            "precio": 12000,
        },
    )

    assert modificado is False
    assert pedido.empresa_envio == "Andreani"
    assert pedido.tipo_entrega == "Domicilio"
