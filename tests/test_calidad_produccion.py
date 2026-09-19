import json
from pathlib import Path
import pytest
from services.calidad_produccion import crear_lote, registrar_control, evidencia_calidad, exportar_evidencia

class Obj:
    def __init__(self,**datos): self.__dict__.update(datos)
class Session:
    def __init__(self): self.agregados=[];self.commits=0
    def add(self,item): self.agregados.append(item)
    def commit(self): self.commits+=1
class Modelo:
    def __init__(self,**datos): self.__dict__.update(datos)

def base():
    orden=Obj(id=1,organizacion_id=7,unidad_negocio_id=9)
    parte=Obj(id=2,organizacion_id=7,unidad_negocio_id=9,orden_produccion_id=1,estado="informado",
              cantidad_buena="10",lotes_preparatorios=[])
    return orden,parte

def test_lote_nace_en_cuarentena_sin_stock():
    orden,parte=base();sesion=Session()
    lote=crear_lote({"codigo":"L-1","cantidad":"8"},orden=orden,parte=parte,organizacion_id=7,
        unidad_negocio_id=9,LoteProduccion=Modelo,db_session=sesion,usuario_id=4)
    assert lote.estado=="cuarentena" and lote.liberado_inventario is False and lote.movimiento_creado is False
    assert sesion.commits==1

def test_no_permite_superar_parte_ni_cruzar_tenant():
    orden,parte=base();parte.lotes_preparatorios=[Obj(cantidad="8")]
    with pytest.raises(ValueError): crear_lote({"codigo":"L-2","cantidad":"3"},orden=orden,parte=parte,
        organizacion_id=7,unidad_negocio_id=9,LoteProduccion=Modelo,db_session=Session())
    orden.organizacion_id=8
    with pytest.raises(ValueError): crear_lote({"codigo":"L-2","cantidad":"1"},orden=orden,parte=parte,
        organizacion_id=7,unidad_negocio_id=9,LoteProduccion=Modelo,db_session=Session())

def test_control_balancea_muestra_y_no_libera():
    lote=Obj(id=3,organizacion_id=7,unidad_negocio_id=9,cantidad="8",estado="cuarentena")
    sesion=Session();control=registrar_control({"numero":"C-1","muestra":"5","aprobadas":"5","rechazadas":"0"},
        lote=lote,organizacion_id=7,unidad_negocio_id=9,ControlCalidadProduccion=Modelo,db_session=sesion)
    assert control.resultado=="aprobado_interno" and control.libera_stock is False
    assert lote.estado=="aprobado_interno"
    with pytest.raises(ValueError): registrar_control({"numero":"C-2","muestra":"5","aprobadas":"4","rechazadas":"0"},
        lote=lote,organizacion_id=7,unidad_negocio_id=9,ControlCalidadProduccion=Modelo,db_session=Session())

def test_evidencia_es_firmada_y_reproducible():
    control=Obj(id=5,numero="C-1",muestra="5",aprobadas="5",rechazadas="0",resultado="aprobado_interno")
    lote=Obj(id=3,organizacion_id=7,unidad_negocio_id=9,codigo="L-1",orden_produccion_id=1,
             parte_produccion_id=2,cantidad="8",estado="aprobado_interno",liberado_inventario=False,
             movimiento_creado=False,controles_calidad=[control])
    uno=evidencia_calidad(organizacion_id=7,unidad_negocio_id=9,lotes=[lote]);dos=evidencia_calidad(organizacion_id=7,unidad_negocio_id=9,lotes=[lote])
    assert uno["huella_calidad"]==dos["huella_calidad"]
    assert json.load(exportar_evidencia(uno))["huella_calidad"]==uno["huella_calidad"]

def test_modelos_rutas_y_panel_exponen_calidad_tenant():
    modelos=Path("models/produccion.py").read_text(encoding="utf-8")
    rutas=Path("modules/admin/produccion/routes.py").read_text(encoding="utf-8")
    panel=Path("templates/admin_produccion.html").read_text(encoding="utf-8")
    assert "class LoteProduccion" in modelos and "class ControlCalidadProduccion" in modelos
    assert 'route("/admin/produccion/evidencia-calidad")' in rutas
    assert "Lotes y calidad" in panel and "Stock: bloqueado" in panel

def test_calidad_no_contiene_consumidor_de_stock_o_conexiones():
    texto=Path("services/calidad_produccion.py").read_text(encoding="utf-8")
    for prohibido in ("MovimientoInventario","requests.","urlopen","http://","https://"):
        assert prohibido not in texto
