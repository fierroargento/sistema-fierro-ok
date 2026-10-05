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
                           organizacion_id=10, unidad_negocio_id=20,
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


def preparar_upsert(monkeypatch, continuar, p, lookup=None):
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
    scope = {
             "ml_vinculo_activo_cuenta": lambda *a, **k: SimpleNamespace(organizacion_id=10, unidad_negocio_id=20),"MercadoLibreCuenta": object,
             "db": SimpleNamespace(session=SimpleNamespace(delete=lambda i: pytest.fail("Sin borrar"))),
             "PedidoItem": SimpleNamespace,
             "ml_obtener_shipment": lambda *a, **k: {"id": 50},
             "ml_prevalidar_importacion_order_service": lambda *a: {
                 "continuar": continuar, "motivo": "Mercado Envíos ya enviado"},
             "ml_pedido_existente_operativo": lookup or (lambda *a, **k: p),
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
        "actualizar_estado_automatico": lambda p: setattr(p, "estado", "Etiqueta Lista"),
        "ml_intentar_contacto_inicial_acordas_service": lambda *a: None,
        "es_ml_acordas_entrega": lambda *a: False,
        "ml_auto_enviar_contacto_inicial_acordas": lambda *a: None,
        "ml_nombre_cliente": lambda *a: "",
        "ml_aplicar_datos_envio": lambda *a: None,
        "ml_aplicar_apb_en_pedido": lambda *a: None,
    })
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(source), "exec"), scope)
    return scope[fn.name], datos, scope


@pytest.mark.parametrize("vinculo_ids", [(10, 20), (11, 20), (10, 21)])
def test_ruta_resync_resuelve_order_y_rechaza_vinculo_ajeno(vinculo_ids):
    p = pedido()
    p.id, p.canal = 7, "Mercado Libre"
    antes = deepcopy(p)
    datos = datos_pack()
    llamadas, importadas, transacciones = [], [], []
    def get(path):
        llamadas.append(path)
        return datos[path]
    def upsert(order, *, cuenta_ml, organizacion_id):
        assert cuenta_ml is cuenta
        assert organizacion_id == 10
        importadas.append(order["id"])
        return p, False, ""
    cuenta = object()
    source = Path(__file__).resolve().parents[1] / "app.py"
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "resync_ml_pedido")
    fn.decorator_list = []
    scope = {
        "pedido_tenant_actual_o_404": lambda id: p,
        "puede_operar_whatsapp": lambda p: True,
        "ml_api_contexto_de_pedido": lambda p: SimpleNamespace(
            cuenta=cuenta, get=get, seller_id=9,
        ),
        "ml_vinculo_activo_cuenta": lambda *a, **k: SimpleNamespace(
            organizacion_id=vinculo_ids[0], unidad_negocio_id=vinculo_ids[1],
        ),
        "ml_upsert_pedido_desde_order": upsert,
        "ml_sync_mensajes_pedido": lambda p: (False, 0),
        "ml_obtener_claim_de_pedido": lambda *a: None,
        "ml_marcar_claim_en_pedido": lambda *a: None,
        "db": SimpleNamespace(session=SimpleNamespace(
            commit=lambda: transacciones.append("commit"),
            rollback=lambda: transacciones.append("rollback"),
        )),
        "redirect": lambda url: url,
        "url_for": lambda ruta, **k: k,
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(source), "exec"), scope)
    resultado = scope[fn.name](7)
    if vinculo_ids == (10, 20):
        assert importadas == [1]
        assert "/packs/100" in llamadas and "/orders/100" not in llamadas
        assert transacciones == ["commit"] and "ok" in resultado
    else:
        assert not llamadas and not importadas
        assert transacciones == ["rollback"] and "error" in resultado
    assert p == antes


@pytest.mark.parametrize("continuar", [False, True])
@pytest.mark.parametrize("estado", ["Despachado", "Cargando Pedido", "Embalado"])
def test_upsert_completa_pack_sin_cambiar_estado(monkeypatch, continuar, estado):
    p = pedido()
    p.estado = estado
    upsert, datos, scope = preparar_upsert(monkeypatch, continuar, p)
    def preparar(*a, **k):
        p.estado = "Etiqueta Lista"
        p.etiqueta_archivo = "nueva.pdf"
        return p, False
    scope["ml_preparar_pedido_base_importacion_service"] = preparar
    for i in [1, 4, 2, 1]:
        result, creado, motivo = upsert(datos[f"/orders/{i}"])
    assert result is p and not creado
    assert len(p.items) == 4 and p.estado == estado
    assert p.etiqueta_archivo == "etiqueta.pdf"


@pytest.mark.parametrize("continuar", [False, True])
@pytest.mark.parametrize("organizacion,unidad", [(11, 20), (10, 21)])
def test_upsert_rechaza_objeto_ajeno_antes_de_mutar(monkeypatch, continuar, organizacion, unidad):
    p = pedido()
    p.organizacion_id, p.unidad_negocio_id = organizacion, unidad
    antes = deepcopy(p)
    upsert, datos, _ = preparar_upsert(monkeypatch, continuar, p)
    with pytest.raises(ValueError, match="no pertenece"):
        upsert(datos["/orders/1"])
    assert p == antes


@pytest.mark.parametrize("continuar", [False, True])
def test_upsert_pack_con_ids_iguales_solo_completa_tenant_destino(monkeypatch, continuar):
    from services.ml_importacion import ml_pedido_existente_operativo_service

    class Query:
        def __init__(self, filas):
            self.filas = filas
        def filter_by(self, **filtros):
            return Query([p for p in self.filas if all(
                getattr(p, k) == v for k, v in filtros.items()
            )])
        def order_by(self, *a):
            return self
        def first(self):
            return self.filas[0] if self.filas else None

    destino, otra_org, otra_unidad = pedido(), pedido(), pedido()
    otra_org.organizacion_id = 11
    otra_unidad.unidad_negocio_id = 21
    for p in [destino, otra_org, otra_unidad]:
        p.canal = "Mercado Libre"
    antes = deepcopy([otra_org, otra_unidad])
    modelo = SimpleNamespace(
        query=Query([otra_org, otra_unidad, destino]),
        id=SimpleNamespace(asc=lambda: None),
    )
    def lookup(order, shipment, *, organizacion_id, unidad_negocio_id):
        return ml_pedido_existente_operativo_service(
            order, shipment, organizacion_id, unidad_negocio_id, modelo,
            lambda *a: True, lambda *a: pytest.fail("Pack encontrado"),
        )
    upsert, datos, _ = preparar_upsert(monkeypatch, continuar, destino, lookup)
    assert upsert(datos["/orders/1"])[0] is destino
    assert len(destino.items) == 4
    assert [otra_org, otra_unidad] == antes
