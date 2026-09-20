import json
from pathlib import Path
import services.expediente_habilitacion_produccion as servicio

class Obj:
    def __init__(self,**datos): self.__dict__.update(datos)

def orden():
    parte=Obj(estado="informado",cantidad_buena="8",cantidad_rechazada="0",minutos_reales="10")
    return Obj(id=1,numero="OP-1",organizacion_id=7,unidad_negocio_id=9,producto_id=30,
               estado="aprobada",cantidad_planificada="10",partes_informados=[parte])

def instalar_falsos(monkeypatch, aprobado=True):
    monkeypatch.setattr(servicio,"planificar_materiales",lambda **k:{"aprobado":aprobado,"huella_plan":"m"*64})
    monkeypatch.setattr(servicio,"planificar_capacidad",lambda **k:{"aprobado":aprobado,"huella_capacidad":"c"*64})
    monkeypatch.setattr(servicio,"evidencia_calidad",lambda **k:{"aprobado":aprobado,"huella_calidad":"q"*64})
    monkeypatch.setattr(servicio,"preparar_propuesta_inventario",lambda *a,**k:{"aprobada":aprobado,"huella_propuesta":"i"*64})
    monkeypatch.setattr(servicio,"costear_resultado",lambda *a,**k:{"aprobado":aprobado,"huella_costeo":"e"*64})

def ejecutar():
    return servicio.construir_expediente(organizacion_id=7,unidad_negocio_id=9,ordenes=[orden()],
        mapeos_insumo=[],existencias_producto=[Obj(producto_id=30)],versiones_empleado=[],
        versiones_maquina=[],lotes=[])

def test_consolida_cinco_controles_y_no_habilita(monkeypatch):
    instalar_falsos(monkeypatch)
    resultado=ejecutar()
    assert resultado["apto_para_ensayo"] is True
    assert resultado["habilitacion_ejecucion"] is False
    assert set(resultado["componentes"])=={"materiales","capacidad","calidad"}
    assert resultado["ordenes"][0]["inventario_aprobado"] is True
    assert resultado["ordenes"][0]["costeo_aprobado"] is True

def test_un_componente_observado_bloquea_aptitud(monkeypatch):
    instalar_falsos(monkeypatch,aprobado=False)
    resultado=ejecutar();codigos={x["codigo"] for x in resultado["hallazgos"]}
    assert resultado["apto_para_ensayo"] is False
    assert {"materiales_no_apto","capacidad_no_apto","calidad_no_apto","inventario_no_apto","costeo_no_apto"}<=codigos

def test_orden_revision_no_simula_cierre(monkeypatch):
    instalar_falsos(monkeypatch);item=orden();item.estado="en_revision";item.partes_informados=[]
    resultado=servicio.construir_expediente(organizacion_id=7,unidad_negocio_id=9,ordenes=[item],
        mapeos_insumo=[],existencias_producto=[],versiones_empleado=[],versiones_maquina=[],lotes=[])
    assert resultado["ordenes"][0]["inventario_aprobado"] is None
    assert resultado["ordenes"][0]["costeo_aprobado"] is None

def test_expediente_es_reproducible(monkeypatch):
    instalar_falsos(monkeypatch)
    uno=ejecutar();dos=ejecutar()
    assert uno["huella_expediente"]==dos["huella_expediente"]
    assert json.load(servicio.exportar_expediente(uno))["huella_expediente"]==uno["huella_expediente"]

def test_ruta_y_panel_exponen_expediente_tenant():
    rutas=Path("modules/admin/produccion/routes.py").read_text(encoding="utf-8")
    panel=Path("templates/admin_produccion.html").read_text(encoding="utf-8")
    assert 'route("/admin/produccion/expediente-habilitacion")' in rutas
    assert "expediente integral de habilitación" in panel

def test_expediente_no_persiste_ni_ejecuta():
    texto=Path("services/expediente_habilitacion_produccion.py").read_text(encoding="utf-8")
    for prohibido in ("db.session",".commit(",".add(","MovimientoInventario","requests.","urlopen","http://","https://"):
        assert prohibido not in texto
