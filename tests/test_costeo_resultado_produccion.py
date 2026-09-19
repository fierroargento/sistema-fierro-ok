import json
from pathlib import Path
import pytest
from services.costeo_resultado_produccion import costear_resultado, exportar_costeo

class Obj:
    def __init__(self,**datos): self.__dict__.update(datos)

def orden():
    parte=Obj(estado="informado",cantidad_buena="8",cantidad_rechazada="2",minutos_reales="100")
    lote=Obj(id=3,organizacion_id=7,unidad_negocio_id=9,codigo="L-1",cantidad="8",estado="aprobado_interno")
    return Obj(id=1,numero="OP-1",organizacion_id=7,unidad_negocio_id=9,cantidad_planificada="10",
               costo_planificado_centavos=100000,costo_unitario_centavos=10000,
               partes_informados=[parte],lotes_preparatorios=[lote])

def test_calcula_costo_efectivo_rechazo_y_desvio():
    resultado=costear_resultado(orden(),organizacion_id=7,unidad_negocio_id=9)
    assert resultado["costos"]["absorbido_avance_centavos"]==100000
    assert resultado["costos"]["rechazo_absorbido_centavos"]==20000
    assert resultado["costos"]["unitario_efectivo_centavos"]==12500
    assert resultado["costos"]["desvio_unitario_centavos"]==2500
    assert resultado["lotes"][0]["costo_teorico_centavos"]==100000

def test_costea_avance_parcial_proporcionalmente():
    item=orden();item.partes_informados[0].cantidad_buena="4";item.partes_informados[0].cantidad_rechazada="1"
    item.lotes_preparatorios[0].cantidad="4"
    resultado=costear_resultado(item,organizacion_id=7,unidad_negocio_id=9)
    assert resultado["costos"]["absorbido_avance_centavos"]==50000
    assert resultado["costos"]["unitario_efectivo_centavos"]==12500

def test_detecta_sin_buenas_y_lotes_excedidos():
    item=orden();item.partes_informados[0].cantidad_buena="0";item.partes_informados[0].cantidad_rechazada="2"
    codigos={x["codigo"] for x in costear_resultado(item,organizacion_id=7,unidad_negocio_id=9)["hallazgos"]}
    assert {"sin_unidades_buenas","lotes_superan_produccion_buena"} <= codigos

def test_rechaza_contexto_y_firma_reproducible():
    with pytest.raises(ValueError): costear_resultado(orden(),organizacion_id=8,unidad_negocio_id=9)
    uno=costear_resultado(orden(),organizacion_id=7,unidad_negocio_id=9)
    dos=costear_resultado(orden(),organizacion_id=7,unidad_negocio_id=9)
    assert uno["huella_costeo"]==dos["huella_costeo"]
    assert json.load(exportar_costeo(uno))["huella_costeo"]==uno["huella_costeo"]

def test_ruta_y_panel_exponen_costeo_tenant():
    rutas=Path("modules/admin/produccion/routes.py").read_text(encoding="utf-8")
    panel=Path("templates/admin_produccion.html").read_text(encoding="utf-8")
    assert 'route("/admin/produccion/orden/<int:orden_id>/costeo-resultado")' in rutas
    assert "Costeo del resultado" in panel

def test_costeo_no_modifica_costos_precios_stock_o_contabilidad():
    texto=Path("services/costeo_resultado_produccion.py").read_text(encoding="utf-8")
    for prohibido in ("db.session",".commit(",".add(","MovimientoInventario","CostoProductoVersion(",
                       "requests.","urlopen","http://","https://"):
        assert prohibido not in texto
