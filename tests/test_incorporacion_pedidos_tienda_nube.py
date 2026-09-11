import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.incorporacion_pedidos_tienda_nube import incorporar


class Consulta:
    resultado = None
    def filter_by(self, **_filtros): return self
    def first(self): return self.resultado


class Pedido:
    query = Consulta()
    def __init__(self, **datos): self.id=None; vars(self).update(datos)


class Item:
    def __init__(self, **datos): vars(self).update(datos)


class Resultado:
    query = Consulta()
    def __init__(self, **datos): self.id=None; vars(self).update(datos)


class Sesion:
    def __init__(self): self.agregados=[]; self.commits=0; self.rollbacks=0; self.siguiente=100
    def add(self, valor): self.agregados.append(valor)
    def flush(self):
        if getattr(self.agregados[-1], "id", None) is None:
            self.agregados[-1].id=self.siguiente; self.siguiente+=1
    def commit(self): self.commits+=1
    def rollback(self): self.rollbacks+=1


def lote(estado="certificado", tenant=2, unidad=3, bloqueos=None):
    fila={"propuesta_id":1,"order_id":"TN-10","numero":"10","bloqueos":bloqueos or [],"snapshot":{"order_id":"TN-10","estado_pago":"paid","items":[{"sku":"PP6040","nombre":"Parrilla","cantidad":2,"estado":"vinculado","producto_id":7}]}}
    evidencia={"firma_contenido":"f"*64,"filas":[fila]}
    return SimpleNamespace(id=5,organizacion_id=tenant,unidad_negocio_id=unidad,tienda_nube_cuenta_id=8,estado=estado,puede_ejecutar=False,firma_contenido="f"*64,evidencia_json=json.dumps(evidencia))


def ejecutar(objeto=None, confirmacion="INCORPORAR"):
    return incorporar(
        objeto or lote(),confirmacion=confirmacion,organizacion_id=2,unidad_negocio_id=3,
        usuario=SimpleNamespace(id=4,username="admin"),Pedido=Pedido,PedidoItem=Item,
        ResultadoIncorporacionTiendaNube=Resultado,db_session=Sesion(),
    )


def test_crea_pedido_items_y_resultado_en_una_transaccion():
    Pedido.query.resultado=Resultado.query.resultado=None
    sesion=Sesion()
    resultado,creado=incorporar(lote(),confirmacion="INCORPORAR",organizacion_id=2,unidad_negocio_id=3,usuario=SimpleNamespace(id=4,username="admin"),Pedido=Pedido,PedidoItem=Item,ResultadoIncorporacionTiendaNube=Resultado,db_session=sesion)
    pedido=sesion.agregados[0]
    assert creado and resultado.pedidos_creados==1 and resultado.items_creados==1
    assert pedido.organizacion_id==2 and pedido.unidad_negocio_id==3 and pedido.tn_cuenta_id==8
    assert pedido.estado=="Cargando Pedido" and pedido.telefono=="" and pedido.contacto_iniciado is False
    assert resultado.acciones_externas==0 and sesion.commits==1


def test_es_idempotente_por_resultado_del_lote():
    previo=SimpleNamespace(id=9,pedidos_creados=1)
    Resultado.query.resultado=previo
    resultado,creado=ejecutar()
    assert resultado is previo and creado is False
    Resultado.query.resultado=None


@pytest.mark.parametrize("confirmacion",["","incorpora","SI"])
def test_exige_confirmacion_literal(confirmacion):
    with pytest.raises(ValueError): ejecutar(confirmacion=confirmacion)


@pytest.mark.parametrize("objeto",[lote(tenant=9),lote(unidad=9),lote(estado="observado")])
def test_exige_expediente_certificado_del_tenant(objeto):
    with pytest.raises(ValueError): ejecutar(objeto)


def test_revalida_duplicado_antes_de_escribir():
    Pedido.query.resultado=SimpleNamespace(id=77)
    sesion=Sesion()
    with pytest.raises(ValueError):
        incorporar(lote(),confirmacion="INCORPORAR",organizacion_id=2,unidad_negocio_id=3,usuario=None,Pedido=Pedido,PedidoItem=Item,ResultadoIncorporacionTiendaNube=Resultado,db_session=sesion)
    assert not sesion.agregados
    Pedido.query.resultado=None


def test_bloquea_items_no_vinculados_y_lotes_observados():
    with pytest.raises(ValueError): ejecutar(lote(bloqueos=["pedido_existente"]))
    objeto=lote();datos=json.loads(objeto.evidencia_json);datos["filas"][0]["snapshot"]["items"][0]["producto_id"]=None;objeto.evidencia_json=json.dumps(datos)
    with pytest.raises(ValueError): ejecutar(objeto)


def test_contrato_estatico_sin_efectos_externos():
    raiz=Path(__file__).resolve().parents[1]
    fuente=(raiz/"services/incorporacion_pedidos_tienda_nube.py").read_text(encoding="utf-8")
    modelo=(raiz/"models/resultado_incorporacion_tienda_nube.py").read_text(encoding="utf-8")
    ruta=(raiz/"modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    for prohibido in ("requests.","urlopen","access_token","client_secret","enviar_mensaje","generar_etiqueta","reservar_inventario"):
        assert prohibido not in fuente
    assert "acciones_externas = 0" in modelo
    assert "incorporar_expediente_tienda_nube_comercial" in ruta
