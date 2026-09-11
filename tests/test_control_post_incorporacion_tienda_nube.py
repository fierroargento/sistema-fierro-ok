import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.control_post_incorporacion_tienda_nube import construir_control, exportar_control


def resultado(ids=(10,), tenant=2, unidad=3):
    return SimpleNamespace(id=5,lote_id=4,organizacion_id=tenant,unidad_negocio_id=unidad,pedido_ids_json=json.dumps(ids))


def pedido(id=10, order="TN-10", tenant=2, unidad=3, cliente="Juan", telefono="2920", direccion="Mitre 1"):
    return SimpleNamespace(id=id,organizacion_id=tenant,unidad_negocio_id=unidad,canal="Tienda Nube",origen="tiendanube_offline_certificado",tn_order_id=order,tn_order_number="10",tn_cuenta_id=8,cliente=cliente,telefono=telefono,direccion=direccion,estado="Cargando Pedido")


def item(pedido_id=10,sku="PP6040",cantidad=1):
    return SimpleNamespace(pedido_id=pedido_id,sku=sku,cantidad=cantidad)


def test_certifica_trazabilidad_completa_de_solo_lectura():
    control=construir_control(resultado(),[pedido()],[item()],organizacion_id=2,unidad_negocio_id=3)
    assert control["aprobado"] and control["solo_lectura"]
    assert control["resumen"]=={"esperados":1,"encontrados":1,"listos":1,"requieren_revision":0,"bloqueados":0,"items":1}
    assert control["acciones_externas"]==control["escrituras"]==0


def test_detecta_pedido_ausente_o_ajeno():
    control=construir_control(resultado(),[pedido(tenant=9)],[item()],organizacion_id=2,unidad_negocio_id=3)
    assert not control["aprobado"] and control["resumen"]["bloqueados"]==1
    assert control["filas"][0]["bloqueos"]==["pedido_ausente_o_ajeno"]


def test_separa_faltantes_operativos_de_bloqueos_estructurales():
    control=construir_control(resultado(),[pedido(cliente="Cliente Tienda Nube 10",telefono="",direccion="")],[item()],organizacion_id=2,unidad_negocio_id=3)
    fila=control["filas"][0]
    assert fila["estado"]=="requiere_revision" and not fila["bloqueos"]
    assert set(fila["pendientes"])=={"completar_cliente","completar_telefono","revisar_entrega"}
    assert control["aprobado"]


@pytest.mark.parametrize("cambio",["canal","origen","identidad","items"])
def test_bloquea_inconsistencias_del_maestro(cambio):
    p=pedido();items=[item()]
    if cambio=="canal":p.canal="Presencial"
    if cambio=="origen":p.origen="manual"
    if cambio=="identidad":p.tn_order_id=""
    if cambio=="items":items=[]
    control=construir_control(resultado(),[p],items,organizacion_id=2,unidad_negocio_id=3)
    assert control["resumen"]["bloqueados"]==1 and not control["aprobado"]


def test_bloquea_identidades_de_resultado_duplicadas():
    with pytest.raises(ValueError): construir_control(resultado((10,10)),[pedido()],[item()],organizacion_id=2,unidad_negocio_id=3)


def test_firma_y_exportacion_son_estables_utf8():
    primero=construir_control(resultado(),[pedido()],[item()],organizacion_id=2,unidad_negocio_id=3)
    segundo=construir_control(resultado(),[pedido()],[item()],organizacion_id=2,unidad_negocio_id=3)
    assert primero["firma_control"]==segundo["firma_control"]
    assert json.loads(exportar_control(primero).getvalue().decode("utf-8"))["firma_control"]==primero["firma_control"]


def test_revalida_tenant_y_contrato_estatico():
    with pytest.raises(ValueError): construir_control(resultado(tenant=9),[],[],organizacion_id=2,unidad_negocio_id=3)
    raiz=Path(__file__).resolve().parents[1]
    fuente=(raiz/"services/control_post_incorporacion_tienda_nube.py").read_text(encoding="utf-8")
    ruta=(raiz/"modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    html=(raiz/"templates/admin_control_post_incorporacion_tn.html").read_text(encoding="utf-8")
    for prohibido in ("db.session","requests.","urlopen","access_token","client_secret",".commit(",".add("):
        assert prohibido not in fuente
    assert "control_post_incorporacion_tienda_nube_comercial" in ruta
    assert "Diagnóstico de solo lectura" in html
