import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.lotes_incorporacion_tienda_nube import certificar, exportar, guardar


def propuesta(id=1, order_id="TN-1", cuenta=8, tenant=2, unidad=3, estado="aprobada"):
    snapshot = {"order_id": order_id, "total_centavos": 125000, "items": [{"sku": "PP6040", "cantidad": 1}]}
    return SimpleNamespace(
        id=id, organizacion_id=tenant, unidad_negocio_id=unidad,
        tienda_nube_cuenta_id=cuenta, tn_order_id=order_id,
        tn_order_number=order_id, estado=estado, puede_crear_pedido=False,
        snapshot_json=json.dumps(snapshot),
    )


def pedido(order_id="TN-1", tenant=2, unidad=3):
    return SimpleNamespace(tn_order_id=order_id, organizacion_id=tenant, unidad_negocio_id=unidad)


def test_certifica_aprobadas_del_mismo_tenant_y_cuenta():
    resultado = certificar([propuesta(), propuesta(2, "TN-2")], [], organizacion_id=2, unidad_negocio_id=3)
    assert resultado["estado"] == "certificado"
    assert resultado["resumen"] == {"propuestas": 2, "bloqueadas": 0, "total_centavos": 250000}
    assert resultado["puede_ejecutar"] is False
    assert resultado["pedidos_creados"] == resultado["acciones_externas"] == 0


def test_firma_es_estable_sin_importar_orden_de_seleccion():
    a, b = propuesta(), propuesta(2, "TN-2")
    primero = certificar([a, b], [], organizacion_id=2, unidad_negocio_id=3)
    segundo = certificar([b, a], [], organizacion_id=2, unidad_negocio_id=3)
    assert primero["firma_contenido"] == segundo["firma_contenido"]


def test_revalida_pedidos_existentes_y_observa_lote():
    resultado = certificar([propuesta()], [pedido()], organizacion_id=2, unidad_negocio_id=3)
    assert resultado["estado"] == "observado"
    assert resultado["resumen"]["bloqueadas"] == 1
    assert resultado["filas"][0]["bloqueos"] == ["pedido_existente"]


@pytest.mark.parametrize("seleccion", [[], [propuesta(tenant=9)], [propuesta(estado="preparada")], [propuesta(cuenta=8), propuesta(2, "TN-2", cuenta=9)]])
def test_bloquea_selecciones_invalidas(seleccion):
    with pytest.raises(ValueError):
        certificar(seleccion, [], organizacion_id=2, unidad_negocio_id=3)


def test_bloquea_snapshot_adulterado():
    item = propuesta()
    item.snapshot_json = json.dumps({"order_id": "OTRA"})
    with pytest.raises(ValueError):
        certificar([item], [], organizacion_id=2, unidad_negocio_id=3)


class Consulta:
    existente = None
    def filter_by(self, **_filtros): return self
    def first(self): return self.existente


class Registro:
    query = Consulta()
    def __init__(self, **datos): self.id = None; vars(self).update(datos)


class Item:
    def __init__(self, **datos): vars(self).update(datos)


class Evento:
    def __init__(self, **datos): vars(self).update(datos)


class Sesion:
    def __init__(self): self.agregados=[]; self.commits=0; self.rollbacks=0
    def add(self, valor): self.agregados.append(valor)
    def flush(self): self.agregados[-1].id=41
    def commit(self): self.commits+=1
    def rollback(self): self.rollbacks+=1


def test_guarda_lote_items_y_evento_de_forma_atomica():
    Registro.query.existente = None
    resultado = certificar([propuesta(), propuesta(2, "TN-2")], [], organizacion_id=2, unidad_negocio_id=3)
    sesion = Sesion()
    lote, creado = guardar(
        resultado, usuario=SimpleNamespace(id=7, username="admin"),
        LoteIncorporacionTiendaNube=Registro, ItemLoteIncorporacionTiendaNube=Item,
        EventoLoteIncorporacionTiendaNube=Evento, db_session=sesion,
    )
    assert creado and lote.id == 41 and lote.puede_ejecutar is False
    assert len(sesion.agregados) == 4 and sesion.commits == 1


def test_guardado_idempotente():
    existente = SimpleNamespace(id=9)
    Registro.query.existente = existente
    lote, creado = guardar(
        certificar([propuesta()], [], organizacion_id=2, unidad_negocio_id=3), usuario=None,
        LoteIncorporacionTiendaNube=Registro, ItemLoteIncorporacionTiendaNube=Item,
        EventoLoteIncorporacionTiendaNube=Evento, db_session=Sesion(),
    )
    assert lote is existente and creado is False
    Registro.query.existente = None


def test_exportacion_revalida_tenant_y_mantiene_bloqueo():
    datos = certificar([propuesta()], [], organizacion_id=2, unidad_negocio_id=3)
    lote = SimpleNamespace(id=4, organizacion_id=2, unidad_negocio_id=3, estado="certificado", evidencia_json=json.dumps(datos))
    salida = json.loads(exportar(lote, organizacion_id=2, unidad_negocio_id=3).getvalue().decode("utf-8"))
    assert salida["control"]["puede_ejecutar"] is False
    assert salida["control"]["pedidos_creados"] == salida["control"]["acciones_externas"] == 0
    with pytest.raises(ValueError): exportar(lote, organizacion_id=9, unidad_negocio_id=3)


def test_integracion_estatica_desconectada():
    raiz = Path(__file__).resolve().parents[1]
    servicio = (raiz / "services/lotes_incorporacion_tienda_nube.py").read_text(encoding="utf-8")
    modelo = (raiz / "models/lote_incorporacion_tienda_nube.py").read_text(encoding="utf-8")
    rutas = (raiz / "modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    html = (raiz / "templates/admin_propuestas_pedidos_tienda_nube.html").read_text(encoding="utf-8")
    for prohibido in ("requests.", "urlopen", "access_token", "client_secret", "Pedido(", "PedidoItem("):
        assert prohibido not in servicio
    assert "puede_ejecutar = false" in modelo
    assert "certificar_lote" in rutas and "Certificar lote aprobado" in html
