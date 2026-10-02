import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace, ModuleType

import pytest

from services.ml_pack_items import (
    ml_completar_order_pack, ml_obtener_order_para_pedido,
)
from services.ml_items import ml_sincronizar_items_pedido_service


def datos_pack():
    skus = ["M3-025-10", "M3-023-10", "M3-010-10", "M3-034-6"]
    datos = {"/packs/100": {"id": 100, "orders": [{"id": i} for i in range(1, 5)]}}
    for i, sku in enumerate(skus, 1):
        datos[f"/orders/{i}"] = {
            "id": i, "pack_id": 100, "seller": {"id": 9}, "status": "paid",
            "shipping": {"id": 50},
            "order_items": [{"item": {"seller_sku": sku, "id": f"MLA{i}",
                                     "title": sku}, "quantity": 1}],
        }
    return datos


def pedido():
    return SimpleNamespace(id_venta="100", ml_pack_id="100", ml_shipping_id="50",
                           estado="Despachado", etiqueta_archivo="etiqueta.pdf",
                           items=[SimpleNamespace(sku=s, descripcion=s, cantidad=1)
                                  for s in ["M3-010-10", "M3-023-10"]])


def sincronizar(p, order):
    return ml_sincronizar_items_pedido_service(
        p, order, {}, SimpleNamespace,
        SimpleNamespace(session=SimpleNamespace(delete=lambda i: pytest.fail("No borrar"))),
        lambda *args: True,
    )


def test_pack_cuatro_ordenes_completa_dos_faltantes_y_repeticion_no_duplica():
    datos = datos_pack()
    p = pedido()
    for i in [1, 2, 3, 4, 1]:
        order = ml_completar_order_pack(datos[f"/orders/{i}"], datos.__getitem__, 9, 50)
        sincronizar(p, order)
    assert len(p.items) == 4
    assert {i.sku for i in p.items} == {"M3-025-10", "M3-023-10", "M3-010-10", "M3-034-6"}
    assert all(i.cantidad == 1 for i in p.items)
    assert p.estado == "Despachado" and p.etiqueta_archivo == "etiqueta.pdf"


def test_sku_repetido_suma_cantidades_entre_ordenes_sin_acumular_reintento():
    datos = datos_pack()
    datos["/orders/4"]["order_items"] = deepcopy(datos["/orders/1"]["order_items"])
    datos["/orders/4"]["order_items"][0]["quantity"] = 2
    p = pedido()
    for _ in range(2):
        sincronizar(p, ml_completar_order_pack(datos["/orders/1"], datos.__getitem__, 9, 50))
    assert next(i.cantidad for i in p.items if i.sku == "M3-025-10") == 3
    assert len(p.items) == 3


@pytest.mark.parametrize("campo,valor", [
    ("id", 99), ("pack_id", 101), ("seller", {"id": 10}),
    ("shipping", {"id": 51}), ("status", "payment_required"),
    ("order_items", []),
])
def test_pack_invalido_no_modifica_items(campo, valor):
    datos = datos_pack()
    datos["/orders/4"][campo] = valor
    p = pedido()
    antes = deepcopy(p)
    with pytest.raises(ValueError):
        sincronizar(p, ml_completar_order_pack(datos["/orders/1"], datos.__getitem__, 9, 50))
    assert p == antes


def test_error_api_no_guarda_pack_parcial():
    datos = datos_pack()
    def get(path):
        if path == "/orders/4":
            raise TimeoutError("ML no disponible")
        return datos[path]
    p = pedido()
    antes = deepcopy(p)
    with pytest.raises(TimeoutError):
        sincronizar(p, ml_completar_order_pack(datos["/orders/1"], get, 9, 50))
    assert p == antes


def test_orden_cancelada_excluida_y_referencia_duplicada_no_suma_dos_veces():
    datos = datos_pack()
    datos["/orders/4"]["status"] = "cancelled"
    datos["/packs/100"]["orders"].append({"id": 1})
    order = ml_completar_order_pack(datos["/orders/1"], datos.__getitem__, 9, 50)
    assert len(order["order_items"]) == 3
    assert sum(i["quantity"] for i in order["order_items"]) == 3


def test_resync_resuelve_pack_a_order_real_no_consulta_orders_pack_id():
    datos = datos_pack()
    llamadas = []
    def get(path):
        llamadas.append(path)
        return datos[path]
    order = ml_obtener_order_para_pedido(pedido(), get, 9)
    assert order["id"] == 1
    assert "/orders/100" not in llamadas


def test_order_sin_pack_conserva_consulta_directa():
    datos = datos_pack()
    p = pedido()
    p.id_venta = "1"
    p.ml_pack_id = ""
    assert ml_obtener_order_para_pedido(p, datos.__getitem__, 9) == datos["/orders/1"]
    order = {"id": 1}
    assert ml_completar_order_pack(order, lambda p: pytest.fail("Sin consulta"), 9) is order


@pytest.mark.parametrize("continuar", [False, True])
def test_upsert_completa_pack_sin_cambiar_estado(monkeypatch, continuar):
    # Ejecutar la función real sin iniciar Flask, scheduler ni conexiones.
    cuentas = ModuleType("services.ml_importacion_cuentas")
    cuentas.ml_resolver_cuenta_desde_order_service = lambda *a, **k: object()
    cuentas.ml_asignar_cuenta_ml_a_pedido_service = lambda *a, **k: True
    monkeypatch.setitem(__import__("sys").modules, cuentas.__name__, cuentas)
    contexto = ModuleType("services.ml_api_context")
    datos = datos_pack()
    contexto.ml_api_contexto = lambda *a, **k: SimpleNamespace(get=datos.__getitem__, seller_id="9")
    monkeypatch.setitem(__import__("sys").modules, contexto.__name__, contexto)
    source = Path(__file__).resolve().parents[1] / "app.py"
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "ml_upsert_pedido_desde_order")
    p = pedido()
    scope = {"MercadoLibreCuenta": object,
             "db": SimpleNamespace(session=SimpleNamespace(delete=lambda i: pytest.fail("Sin borrar"))),
             "PedidoItem": SimpleNamespace,
             "ml_obtener_shipment": lambda *a, **k: {"id": 50},
             "ml_prevalidar_importacion_order_service": lambda *a: {
                 "continuar": continuar, "motivo": "Mercado Envíos ya enviado"},
             "ml_pedido_existente_operativo": lambda *a: p,
             "ml_sincronizar_items_pedido_service": ml_sincronizar_items_pedido_service,
             "ml_es_mercado_envios_order": lambda *a: True}
    for name in ["ml_pedido_esta_ignorado", "ml_order_esta_entregado",
                 "ml_registrar_order_ignorado", "ml_marcar_pedido_finalizado_por_entrega",
                 "ml_order_debe_omitirse", "ml_borrar_pedido_importado_si_corresponde",
                 "ml_envio_ya_despachado"]:
        scope[name] = lambda *a: None
    scope.update({
        "Pedido": SimpleNamespace,
        "ml_obtener_billing_info": lambda *a, **k: {},
        "ml_preparar_pedido_base_importacion_service": lambda *a, **k: (p, False),
        "actualizar_estado_automatico": lambda *a: None,
        "ml_intentar_contacto_inicial_acordas_service": lambda *a: None,
        "es_ml_acordas_entrega": lambda *a: False,
        "ml_auto_enviar_contacto_inicial_acordas": lambda *a: None,
        "ml_nombre_cliente": lambda *a: "",
        "ml_aplicar_datos_envio": lambda *a: None,
        "ml_aplicar_apb_en_pedido": lambda *a: None,
    })
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(source), "exec"), scope)
    result, creado, motivo = scope[fn.name](datos["/orders/1"])
    assert result is p and not creado
    assert len(p.items) == 4 and p.estado == "Despachado"
    assert p.etiqueta_archivo == "etiqueta.pdf"
