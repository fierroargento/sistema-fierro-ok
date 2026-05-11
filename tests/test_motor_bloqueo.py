"""
tests/test_motor_bloqueo.py
────────────────────────────
Tests sobre motor_bloqueo, despacho_completo y requiere_contacto_cliente.
Son las validaciones APB más críticas del sistema.
"""

import pytest
from tests.fixtures.pedido_factory import PedidoFake, pedido_ml_acordas, pedido_ml_mercado_envios, ItemFake


# ── Funciones puras extraídas de app.py para testeo aislado ──────────────────

def es_via_cargo(valor):
    if not valor:
        return False
    return valor.strip().lower().replace('\u00ed', 'i') == 'via cargo'


def es_ml_acordas_entrega(pedido):
    return pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Acordás la Entrega"


def es_tnube_via_cargo(pedido):
    return pedido.canal == "Tienda Nube" and es_via_cargo(pedido.empresa_envio)


def es_mayorista_via_cargo(pedido):
    return pedido.canal not in ["Mercado Libre", "Tienda Nube"] and es_via_cargo(pedido.empresa_envio)


def usa_flujo_acordas_entrega(pedido):
    return es_ml_acordas_entrega(pedido) or es_tnube_via_cargo(pedido) or es_mayorista_via_cargo(pedido)


def hay_autorizado(pedido):
    return bool(
        getattr(pedido, "autorizado_nombre", "")
        or getattr(pedido, "autorizado_dni", "")
    )


def despacho_completo(pedido):
    """Versión con GPT's aplicar_default inline para test."""
    # Aplicar default si empresa_envio seteada y tipo_entrega vacío
    tipo = str(getattr(pedido, "tipo_entrega", "") or "").strip()
    if not tipo and es_via_cargo(getattr(pedido, "empresa_envio", "")):
        tipo = "Sucursal"

    if not pedido.empresa_envio or not tipo:
        return False

    if tipo == "Domicilio":
        return bool(
            pedido.direccion
            and pedido.codigo_postal
            and pedido.localidad
            and pedido.provincia
        )

    if tipo == "Sucursal":
        if not (pedido.sucursal_nombre and pedido.direccion and pedido.localidad and pedido.provincia):
            return False
        if hay_autorizado(pedido):
            return bool(
                pedido.autorizado_nombre
                and pedido.autorizado_dni
                and pedido.autorizado_telefono
            )
        return True

    return False


def requiere_contacto_cliente(pedido):
    return bool(usa_flujo_acordas_entrega(pedido) and not despacho_completo(pedido))


def siguiente_estado(e):
    flujo = {
        "Cargando Pedido": "Etiqueta Lista",
        "Etiqueta Lista": "Etiqueta Impresa",
        "Etiqueta Impresa": "Embalado",
        "Embalado": "Despachado",
        "Despachado": "Entregado",
        "Con demora de entrega": "Entregado",
        "Con reclamo en transporte": "Entregado",
        "Verificar llegada a destino": "Entregado",
        "Listo para retirar": "Entregado",
    }
    return flujo.get(e)


# ── Tests: es_via_cargo ───────────────────────────────────────────────────────

class TestEsViaCargo:
    def test_via_cargo_con_tilde(self):
        assert es_via_cargo("Vía Cargo") is True

    def test_via_cargo_sin_tilde(self):
        assert es_via_cargo("Via Cargo") is True

    def test_via_cargo_minusculas(self):
        assert es_via_cargo("vía cargo") is True

    def test_no_es_via_cargo(self):
        assert es_via_cargo("Andreani") is False
        assert es_via_cargo("Correo Argentino") is False
        assert es_via_cargo("Mercado Envíos") is False

    def test_vacio(self):
        assert es_via_cargo("") is False
        assert es_via_cargo(None) is False


# ── Tests: despacho_completo ──────────────────────────────────────────────────

class TestDespachoCompleto:

    def test_sucursal_completo(self):
        p = pedido_ml_acordas()
        assert despacho_completo(p) is True

    def test_sucursal_sin_tipo_entrega_pero_via_cargo(self):
        """Regla APB: Via Cargo sin tipo_entrega → infiere Sucursal."""
        p = pedido_ml_acordas(tipo_entrega="")
        assert despacho_completo(p) is True

    def test_sin_empresa_envio(self):
        p = pedido_ml_acordas(empresa_envio="", tipo_entrega="")
        assert despacho_completo(p) is False

    def test_sucursal_sin_nombre_sucursal(self):
        p = pedido_ml_acordas()
        p.sucursal_nombre = ""
        assert despacho_completo(p) is False

    def test_sucursal_sin_localidad(self):
        p = pedido_ml_acordas()
        p.localidad = ""
        assert despacho_completo(p) is False

    def test_domicilio_completo(self):
        p = PedidoFake(
            canal="Mercado Libre",
            ml_tipo="Acordás la Entrega",
            empresa_envio="Correo Argentino",
            tipo_entrega="Domicilio",
            direccion="Av. Corrientes 1234",
            codigo_postal="1043",
            localidad="Buenos Aires",
            provincia="Buenos Aires",
        )
        assert despacho_completo(p) is True

    def test_domicilio_sin_cp(self):
        p = PedidoFake(
            empresa_envio="Correo Argentino",
            tipo_entrega="Domicilio",
            direccion="Av. Corrientes 1234",
            codigo_postal="",
            localidad="Buenos Aires",
            provincia="Buenos Aires",
        )
        assert despacho_completo(p) is False

    def test_con_autorizado_completo(self):
        p = pedido_ml_acordas(
            autorizado_nombre="Pedro López",
            autorizado_dni="22334455",
            autorizado_telefono="5491155667788",
        )
        assert despacho_completo(p) is True

    def test_con_autorizado_incompleto(self):
        p = pedido_ml_acordas(
            autorizado_nombre="Pedro López",
            autorizado_dni="",
            autorizado_telefono="",
        )
        assert despacho_completo(p) is False

    def test_ml_mercado_envios_sin_datos_envio(self):
        """ME no usa flujo Acordás → despacho_completo no aplica esta lógica."""
        p = pedido_ml_mercado_envios()
        # ME tiene tipo_entrega="Domicilio" y empresa_envio="Mercado Envíos" en factory
        # No es Via Cargo → no infiere Sucursal
        # Pero tiene tipo_entrega seteado → evalúa normalmente
        # Necesita direccion/cp/localidad/provincia para Domicilio
        assert despacho_completo(p) is False  # faltan esos campos en factory


# ── Tests: requiere_contacto_cliente ─────────────────────────────────────────

class TestRequiereContactoCliente:

    def test_acordas_con_datos_completos_no_requiere(self):
        p = pedido_ml_acordas()
        assert requiere_contacto_cliente(p) is False

    def test_acordas_sin_datos_requiere(self):
        p = PedidoFake(
            canal="Mercado Libre",
            ml_tipo="Acordás la Entrega",
            empresa_envio="Vía Cargo",
            tipo_entrega="Sucursal",
            sucursal_nombre="",  # falta
        )
        assert requiere_contacto_cliente(p) is True

    def test_mercado_envios_no_requiere(self):
        """ME no usa flujo Acordás → nunca requiere contacto."""
        p = pedido_ml_mercado_envios()
        assert requiere_contacto_cliente(p) is False

    def test_via_cargo_tipo_entrega_vacio_no_requiere_si_sucursal_completa(self):
        """Si tipo_entrega está vacío pero empresa es Via Cargo y sucursal completa → no requiere."""
        p = pedido_ml_acordas(tipo_entrega="")
        assert requiere_contacto_cliente(p) is False


# ── Tests: siguiente_estado ───────────────────────────────────────────────────

class TestSiguienteEstado:

    def test_flujo_normal_completo(self):
        assert siguiente_estado("Cargando Pedido") == "Etiqueta Lista"
        assert siguiente_estado("Etiqueta Lista") == "Etiqueta Impresa"
        assert siguiente_estado("Etiqueta Impresa") == "Embalado"
        assert siguiente_estado("Embalado") == "Despachado"
        assert siguiente_estado("Despachado") == "Entregado"

    def test_estados_especiales(self):
        assert siguiente_estado("Con demora de entrega") == "Entregado"
        assert siguiente_estado("Listo para retirar") == "Entregado"
        assert siguiente_estado("Verificar llegada a destino") == "Entregado"

    def test_estado_terminal_no_avanza(self):
        assert siguiente_estado("Entregado") is None
        assert siguiente_estado("Finalizado") is None
        assert siguiente_estado("Cancelado") is None

    def test_estado_inexistente(self):
        assert siguiente_estado("EstadoRaro") is None

    def test_no_retrocede(self):
        """Nunca debe haber un estado que retroceda en el flujo."""
        flujo_orden = [
            "Cargando Pedido", "Etiqueta Lista", "Etiqueta Impresa",
            "Embalado", "Despachado", "Entregado"
        ]
        for i, estado in enumerate(flujo_orden[:-1]):
            siguiente = siguiente_estado(estado)
            assert siguiente == flujo_orden[i + 1], f"Falla en {estado} → esperaba {flujo_orden[i+1]}, obtuvo {siguiente}"
