import json
from pathlib import Path

from services.control_integral_compras import controlar_compras, exportar_control


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


def datos():
    item_orden = Obj(id=2, cantidad="2", subtotal_centavos=20000, precio_unitario_centavos=10000, insumo_id=5)
    linea = Obj(orden_compra_item_id=2, cantidad_recibida="2", orden_item=item_orden)
    recepcion = Obj(id=3, estado="preparatoria", subtotal_centavos=20000, items=[linea])
    orden = Obj(id=1, total_centavos=20000, items=[item_orden], recepciones=[recepcion])
    factura = Obj(id=4, proveedor_id=7, tipo_comprobante="A", punto_venta="00001", numero="1",
                  estado="conciliada", diferencia_centavos=0, impacta_fiscal=False, obligacion_creada=False)
    mapeo = Obj(insumo_id=5, activo=True)
    propuesta = Obj(id=6, tipo="stock", estado="preparada", ejecutada=False, recepcion_item=linea)
    return [orden], [recepcion], [factura], [mapeo], [propuesta]


def controlar(*partes):
    return controlar_compras(
        organizacion_id=10, unidad_negocio_id=20, ordenes=partes[0],
        recepciones=partes[1], facturas=partes[2], mapeos=partes[3], propuestas=partes[4],
    )


def test_circuito_coherente_aprueba_y_firma():
    resultado = controlar(*datos())
    assert resultado["aprobado"] is True and len(resultado["huella_control"]) == 64
    assert resultado["controles"]["escrituras"] == 0


def test_detecta_sobre_recepcion_y_factura_observada():
    partes = datos()
    partes[0][0].items[0].cantidad = "1"
    partes[2][0].estado = "observada"
    resultado = controlar(*partes)
    assert resultado["aprobado"] is False
    assert any(item["codigo"] == "cantidad_sobre_recibida" for item in resultado["hallazgos"])


def test_detecta_factura_duplicada_y_propuesta_ejecutada():
    partes = datos()
    partes[2].append(Obj(**partes[2][0].__dict__))
    partes[2][1].id = 8
    partes[4][0].ejecutada = True
    codigos = {item["codigo"] for item in controlar(*partes)["hallazgos"]}
    assert {"factura_duplicada", "propuesta_ejecutada"} <= codigos


def test_exportacion_es_json_reproducible():
    primero = controlar(*datos())
    segundo = controlar(*datos())
    assert primero["huella_control"] == segundo["huella_control"]
    assert json.load(exportar_control(primero))["huella_control"] == primero["huella_control"]


def test_ruta_exige_contexto_tenant_y_exporta_json():
    rutas = Path("modules/admin/compras/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_compras.html").read_text(encoding="utf-8")
    assert '@blueprint.route("/admin/compras/control-integral")' in rutas
    assert "organizacion.id" in rutas and "unidad.id" in rutas
    assert "Descargar control integral" in panel


def test_servicio_es_exclusivamente_de_lectura():
    servicio = Path("services/control_integral_compras.py").read_text(encoding="utf-8")
    for prohibido in ("db.session", "requests.", "urlopen", "http://", "https://"):
        assert prohibido not in servicio
