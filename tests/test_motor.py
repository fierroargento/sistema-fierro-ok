from app import motor_bloqueo

class ItemFake:
    def __init__(self, sku="PP6040", descripcion="Parrilla plegable PP6040", cantidad=1):
        self.sku = sku
        self.descripcion = descripcion
        self.cantidad = cantidad

class PedidoFake:
    def __init__(self):
        self.estado = "Etiqueta Lista"

        self.canal = "Mercado Libre"
        self.ml_tipo = "Acordás la Entrega"

        self.tipo_entrega = "Sucursal"

        self.transporte = "Via Cargo"
        self.empresa_envio = "Via Cargo"

        self.sucursal = "Sucursal Test"
        self.sucursal_nombre = "Sucursal Test"
        self.direccion_sucursal = "Direccion Sucursal Test"

        self.direccion = "Direccion Sucursal Test"
        self.localidad = "Localidad Test"
        self.provincia = "Provincia Test"
        self.codigo_postal = "8500"

        self.observaciones = ""
        self.tn_order_status = ""

        self.cliente = "Cliente Test"

        self.ml_buyer_nickname = ""
        self.ml_billing_nombre = "Cliente Test"

        self.dni = "12345678"
        self.ml_billing_documento = "12345678"

        self.telefono = "+5491123456789"

        self.autorizado_nombre = ""
        self.autorizado_dni = ""
        self.autorizado_telefono = ""

        self.items = [ItemFake(cantidad=3)]

        self.tiene_reclamo = False

        self.sku = "PP6040"
        self.cantidad = 1

def test_motor_bloqueo_pedido_completo_sin_errores():
    pedido = PedidoFake()

    resultado = motor_bloqueo(pedido)

    assert resultado == []

def test_motor_bloquea_pp6040_via_cargo_con_1_unidad():
    pedido = PedidoFake()
    pedido.items = [ItemFake(cantidad=1)]

    resultado = motor_bloqueo(pedido)

    assert any("PP6040 no puede enviarse por Vía Cargo" in error for error in resultado)    