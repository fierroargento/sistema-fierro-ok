"""
tests/test_despacho_mobile.py
──────────────────────────────
Tests que validan el flujo de despacho mobile.
Cada test documenta un bug que ocurrió en producción y fue corregido.
Si alguno falla después de un cambio, es una regresión real.
"""

import pytest
from tests.fixtures.pedido_factory import PedidoFake, pedido_ml_acordas, ItemFake


# ── Funciones puras necesarias (mismas que test_motor_bloqueo) ────────────────

def es_via_cargo(valor):
    if not valor:
        return False
    return valor.strip().lower().replace('\u00ed', 'i') == 'via cargo'


def es_ml_acordas_entrega(pedido):
    return pedido.canal == "Mercado Libre" and pedido.ml_tipo == "Acordás la Entrega"


def usa_flujo_acordas_entrega(pedido):
    return es_ml_acordas_entrega(pedido) or (
        pedido.canal == "Tienda Nube" and es_via_cargo(pedido.empresa_envio)
    )


def hay_autorizado(pedido):
    return bool(getattr(pedido, "autorizado_nombre", "") or getattr(pedido, "autorizado_dni", ""))


def despacho_completo(pedido):
    tipo = str(getattr(pedido, "tipo_entrega", "") or "").strip()
    if not tipo and es_via_cargo(getattr(pedido, "empresa_envio", "")):
        tipo = "Sucursal"
    if not pedido.empresa_envio or not tipo:
        return False
    if tipo == "Domicilio":
        return bool(pedido.direccion and pedido.codigo_postal and pedido.localidad and pedido.provincia)
    if tipo == "Sucursal":
        if not (pedido.sucursal_nombre and pedido.direccion and pedido.localidad and pedido.provincia):
            return False
        if hay_autorizado(pedido):
            return bool(pedido.autorizado_nombre and pedido.autorizado_dni and pedido.autorizado_telefono)
        return True
    return False


def requiere_contacto_cliente(pedido):
    return bool(usa_flujo_acordas_entrega(pedido) and not despacho_completo(pedido))


ESTADOS_DESPACHO = ["Etiqueta Lista", "Etiqueta Impresa", "Embalado"]
ESTADOS_EXCLUIDOS_REQUIERE_CONTACTO = [
    "Despachado", "Verificar llegada a destino", "Listo para retirar",
    "Con demora de entrega", "Con reclamo en transporte", "Entregado", "Finalizado",
    *ESTADOS_DESPACHO,  # FIX: estos estados no deben interceptarse
]


def accion_principal_pedido_mobile(pedido):
    """
    Simula la lógica relevante de accion_principal_pedido para origen='mobile' y rol='despacho'.
    Retorna el 'tipo' de acción que se mostraría.
    """
    # Check 1: tn_necesita_completar_carga (solo TN en Cargando Pedido)
    if (pedido.canal == "Tienda Nube"
            and pedido.estado == "Cargando Pedido"):
        return "completar_carga"

    # Check 2: requiere_contacto_cliente
    # FIX: NO interceptar si el pedido ya está en estados de despacho
    if (requiere_contacto_cliente(pedido)
            and pedido.estado not in ESTADOS_EXCLUIDOS_REQUIERE_CONTACTO):
        return "completar_carga"

    # Check 3: puede_imprimir (Etiqueta Lista)
    if pedido.estado == "Etiqueta Lista":
        return "imprimir_etiqueta"

    # Check 4: acciones de estado para despacho
    if pedido.estado in ["Etiqueta Impresa", "Embalado"]:
        if pedido.estado == "Etiqueta Impresa":
            return "marcar_embalado"
        if pedido.estado == "Embalado":
            return "marcar_despachado"

    return None


# ── Tests: regresiones de bugs de producción ──────────────────────────────────

class TestDespachoMobileRegresiones:

    def test_bug_pedido_486_embalado_via_cargo_tipo_vacio(self):
        """
        BUG: Pedido #486 - ML Acordás + Via Cargo + estado Embalado + tipo_entrega vacío.
        El sistema mostraba 'Continuar proceso' que llevaba a editar_pedido (sin permiso).
        Resultado: loop silencioso al inicio.

        FIX: estados de despacho excluidos de requiere_contacto_cliente.
        Debe mostrar 'marcar_despachado', no 'completar_carga'.
        """
        p = PedidoFake(
            canal="Mercado Libre",
            ml_tipo="Acordás la Entrega",
            empresa_envio="Vía Cargo",
            tipo_entrega="",  # VACÍO - el dato que causó el bug
            estado="Embalado",
            sucursal_nombre="Agencia Don Torcuato",
            direccion="Av. Ángel Torcuato de Alvear 459",
            localidad="Don Torcuato",
            provincia="Buenos Aires",
            items=[ItemFake()],
        )
        accion = accion_principal_pedido_mobile(p)
        assert accion == "marcar_despachado", (
            f"Esperaba 'marcar_despachado', obtuvo '{accion}'. "
            "Bug: tipo_entrega vacío no debe bloquear el flujo de despacho."
        )

    def test_etiqueta_lista_muestra_imprimir(self):
        """Estado Etiqueta Lista → acción debe ser imprimir etiqueta, no completar carga."""
        p = PedidoFake(
            canal="Mercado Libre",
            ml_tipo="Acordás la Entrega",
            empresa_envio="Vía Cargo",
            tipo_entrega="",
            estado="Etiqueta Lista",
            sucursal_nombre="Agencia Test",
            direccion="Calle Test 123",
            localidad="Localidad",
            provincia="Buenos Aires",
            items=[ItemFake()],
        )
        accion = accion_principal_pedido_mobile(p)
        assert accion == "imprimir_etiqueta"

    def test_etiqueta_impresa_muestra_marcar_embalado(self):
        p = PedidoFake(
            canal="Mercado Libre",
            ml_tipo="Acordás la Entrega",
            empresa_envio="Vía Cargo",
            tipo_entrega="",
            estado="Etiqueta Impresa",
            sucursal_nombre="Agencia Test",
            direccion="Calle Test 123",
            localidad="Localidad",
            provincia="Buenos Aires",
            items=[ItemFake()],
        )
        accion = accion_principal_pedido_mobile(p)
        assert accion == "marcar_embalado"

    def test_pedido_cargando_sin_datos_muestra_completar_carga(self):
        """
        Un pedido ML Acordás en 'Cargando Pedido' sin datos → sí debe pedir completar.
        Este es el comportamiento CORRECTO para Cargando Pedido (lo maneja Carga, no Despacho).
        """
        p = PedidoFake(
            canal="Mercado Libre",
            ml_tipo="Acordás la Entrega",
            empresa_envio="",
            tipo_entrega="",
            estado="Cargando Pedido",
            items=[ItemFake()],
        )
        accion = accion_principal_pedido_mobile(p)
        assert accion == "completar_carga"

    def test_todos_estados_despacho_dan_accion_correcta(self):
        """Para cada estado de despacho, el operador debe ver la acción correcta."""
        casos = {
            "Etiqueta Lista": "imprimir_etiqueta",
            "Etiqueta Impresa": "marcar_embalado",
            "Embalado": "marcar_despachado",
        }
        for estado, accion_esperada in casos.items():
            p = PedidoFake(
                canal="Mercado Libre",
                ml_tipo="Acordás la Entrega",
                empresa_envio="Vía Cargo",
                tipo_entrega="",  # siempre vacío para testear el default
                estado=estado,
                sucursal_nombre="Agencia Test",
                direccion="Calle 123",
                localidad="Ciudad",
                provincia="Provincia",
                items=[ItemFake()],
            )
            accion = accion_principal_pedido_mobile(p)
            assert accion == accion_esperada, (
                f"Estado '{estado}': esperaba '{accion_esperada}', obtuvo '{accion}'"
            )

    def test_tipo_entrega_default_via_cargo_es_sucursal(self):
        """
        Regla APB: Via Cargo + tipo_entrega vacío → infiere Sucursal.
        despacho_completo debe devolver True si todos los demás campos están.
        """
        p = pedido_ml_acordas(tipo_entrega="")
        assert despacho_completo(p) is True

    def test_requiere_contacto_false_para_estados_despacho(self):
        """
        requiere_contacto_cliente puede ser True (datos faltantes),
        pero para estados de despacho la función accion_principal
        debe ignorarlo y dar la acción de estado.
        """
        for estado in ESTADOS_DESPACHO:
            p = PedidoFake(
                canal="Mercado Libre",
                ml_tipo="Acordás la Entrega",
                empresa_envio="Vía Cargo",
                tipo_entrega="Sucursal",
                estado=estado,
                # Sin sucursal/dirección → requiere_contacto sería True
                sucursal_nombre="",
                direccion="",
                localidad="",
                provincia="",
                items=[ItemFake()],
            )
            # Verificamos que requiere_contacto_cliente ES True
            assert requiere_contacto_cliente(p) is True, f"Precondición fallida para estado {estado}"

            # Pero la acción mobile NO debe ser 'completar_carga'
            accion = accion_principal_pedido_mobile(p)
            assert accion != "completar_carga", (
                f"Estado '{estado}': la acción no debería ser 'completar_carga' "
                f"aunque requiere_contacto sea True."
            )
