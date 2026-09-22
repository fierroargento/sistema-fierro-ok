import json
from pathlib import Path
from types import SimpleNamespace

from services.exportacion_respaldo_integral import construir_respaldo, exportar


class Columna:
    def __init__(self, nombre): self.name = nombre


class Consulta:
    def __init__(self, filas): self.filas = filas
    def filter_by(self, **filtros): return Consulta([x for x in self.filas if all(getattr(x, k) == v for k, v in filtros.items())])
    def order_by(self, *_): return self
    def all(self): return self.filas


def modelo(nombre, columnas, filas):
    return type(nombre, (), {"__table__": SimpleNamespace(columns=[Columna(x) for x in columnas]), "query": Consulta(filas), "id": SimpleNamespace(asc=lambda: None)})


def modelos():
    fila = SimpleNamespace(id=1, organizacion_id=7, unidad_negocio_id=3, nombre="Dato", access_token="secreto", catalogo_id=1, costo_producto_version_id=1, pedido_id=1, orden_compra_id=1, recepcion_compra_id=1, orden_produccion_id=1)
    columnas = ["id", "organizacion_id", "unidad_negocio_id", "nombre", "access_token", "catalogo_id", "costo_producto_version_id", "pedido_id", "orden_compra_id", "recepcion_compra_id", "orden_produccion_id"]
    from services.exportacion_respaldo_integral import MODELOS_HIJO_POR_CONJUNTO, MODELOS_POR_CONJUNTO
    resultado = {nombre: modelo(nombre, columnas, [fila]) for nombres in MODELOS_POR_CONJUNTO.values() for nombre in nombres}
    for especificaciones in MODELOS_HIJO_POR_CONJUNTO.values():
        for nombre, _padre, _clave in especificaciones:
            resultado[nombre] = modelo(nombre, columnas, [fila])
    return resultado


def test_exporta_doce_conjuntos_aislados_y_firmados():
    resultado = construir_respaldo(organizacion_id=7, unidad_negocio_id=3, modelos=modelos())
    assert len(resultado["conjuntos"]) == 12 and len(resultado["huella_respaldo"]) == 64
    assert all(item["registros"] for item in resultado["manifiesto"].values())
    assert resultado["restauracion_automatica_habilitada"] is False
    assert resultado["respaldo_reconstruible"] is True


def test_excluye_secretos_y_otro_tenant_unidad():
    resultado = construir_respaldo(organizacion_id=7, unidad_negocio_id=3, modelos=modelos())
    serializado = json.dumps(resultado["conjuntos"]).lower()
    assert "access_token" not in serializado and "secreto" not in serializado
    assert '"organizacion_id": 7' in serializado and '"unidad_negocio_id": 3' in serializado


def test_omite_modelos_sin_identidad_tenant():
    sin_tenant = modelo("SinTenant", ["id", "nombre"], [SimpleNamespace(id=1, nombre="x")])
    fuentes = modelos(); fuentes["Pedido"] = sin_tenant
    resultado = construir_respaldo(organizacion_id=7, unidad_negocio_id=3, modelos=fuentes)
    assert any(x["modelo"] == "Pedido" and x["motivo"] == "modelo_sin_identidad_tenant" for x in resultado["seguridad"]["modelos_omitidos"])
    assert resultado["respaldo_reconstruible"] is False


def test_json_compatible_con_ensayo_y_utf8():
    resultado = construir_respaldo(organizacion_id=7, unidad_negocio_id=3, modelos=modelos())
    documento = json.loads(exportar(resultado).read())
    assert documento["origen"] == "exportacion_controlada_sistema_fierro"
    assert "postventa" in documento["conjuntos"] and "auditoria" in documento["conjuntos"]


def test_exporta_hijos_solo_desde_cabeceras_tenant():
    resultado = construir_respaldo(organizacion_id=7, unidad_negocio_id=3, modelos=modelos())
    nombres = {x["_modelo"] for x in resultado["conjuntos"]["compras"]}
    assert {"OrdenCompraItem", "RecepcionCompraItem"} <= nombres
    assert "PedidoItem" in {x["_modelo"] for x in resultado["conjuntos"]["pedidos"]}
    assert "CostoProductoDetalle" in {x["_modelo"] for x in resultado["conjuntos"]["costos"]}


def test_servicio_es_solo_lectura_y_sin_red():
    fuente = Path("services/exportacion_respaldo_integral.py").read_text(encoding="utf-8").lower()
    assert not any(x in fuente for x in ("db.session", "commit(", "rollback(", "delete(", "requests.", "urlopen", "http://", "https://"))
    assert "campos_prohibidos" in fuente and '"conexiones_externas": 0' in fuente


def test_ruta_es_admin_y_panel_declara_exclusion():
    rutas = Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_exportacion_respaldo_integral.html").read_text(encoding="utf-8")
    assert "construir_respaldo_integral(" in rutas and "resolver_acceso()" in rutas
    assert "Excluye contraseñas, tokens, secretos, credenciales y sesiones" in panel
