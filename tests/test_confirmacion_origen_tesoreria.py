from pathlib import Path
import pytest
from services.confirmacion_origen_tesoreria import confirmar_candidato

class Obj:
    def __init__(self,**datos):self.__dict__.update(datos)
class Modelo:
    def __init__(self,**datos):self.__dict__.update(datos)
class Session:
    def __init__(self):self.items=[];self.commits=0
    def add(self,x):self.items.append(x)
    def commit(self):self.commits+=1

def candidato():return {"organizacion_id":7,"unidad_negocio_id":9,"origen":"obligacion_costo","origen_id":4,"tipo":"egreso","concepto":"Alquiler",
    "importe_centavos":75000,"fecha_prevista":"2026-10-10","clave_idempotencia":"a"*64,"ya_proyectado":False}

def test_confirma_como_proyeccion_sin_afectar_saldo():
    cuenta=Obj(id=2,organizacion_id=7,unidad_negocio_id=9);s=Session()
    mov=confirmar_candidato(candidato(),cuenta=cuenta,organizacion_id=7,unidad_negocio_id=9,Movimiento=Modelo,db_session=s,usuario_id=3)
    assert mov.origen=="obligacion_costo" and mov.referencia=="obligacion_costo:4"
    assert mov.confirmado is False and mov.afecta_saldo is False and mov.estado=="proyectado"
    assert s.commits==1

def test_admite_liquidacion_esperada_pero_no_otros_origenes():
    cuenta=Obj(id=2,organizacion_id=7,unidad_negocio_id=9);dato=candidato();dato.update(origen="liquidacion_canal_esperada",tipo="ingreso")
    assert confirmar_candidato(dato,cuenta=cuenta,organizacion_id=7,unidad_negocio_id=9,Movimiento=Modelo,db_session=Session()).tipo=="ingreso"
    dato["origen"]="factura_sin_vencimiento"
    with pytest.raises(ValueError):confirmar_candidato(dato,cuenta=cuenta,organizacion_id=7,unidad_negocio_id=9,Movimiento=Modelo,db_session=Session())

def test_bloquea_duplicado_y_cuenta_cruzada():
    cuenta=Obj(id=2,organizacion_id=7,unidad_negocio_id=9);dato=candidato();dato["ya_proyectado"]=True
    with pytest.raises(ValueError):confirmar_candidato(dato,cuenta=cuenta,organizacion_id=7,unidad_negocio_id=9,Movimiento=Modelo,db_session=Session())

def test_bloquea_origen_cruzado_aunque_la_cuenta_sea_valida():
    cuenta=Obj(id=2,organizacion_id=7,unidad_negocio_id=9);dato=candidato();dato["organizacion_id"]=8
    with pytest.raises(ValueError,match="origen.*contexto"):
        confirmar_candidato(dato,cuenta=cuenta,organizacion_id=7,unidad_negocio_id=9,Movimiento=Modelo,db_session=Session())
    dato["ya_proyectado"]=False;cuenta.organizacion_id=8
    with pytest.raises(ValueError):confirmar_candidato(dato,cuenta=cuenta,organizacion_id=7,unidad_negocio_id=9,Movimiento=Modelo,db_session=Session())

def test_valida_importe_fecha_y_tipo():
    cuenta=Obj(id=2,organizacion_id=7,unidad_negocio_id=9)
    for campo,valor in (("importe_centavos",0),("fecha_prevista","mal"),("tipo","transferencia")):
        dato=candidato();dato[campo]=valor
        with pytest.raises(ValueError):confirmar_candidato(dato,cuenta=cuenta,organizacion_id=7,unidad_negocio_id=9,Movimiento=Modelo,db_session=Session())

def test_panel_rederiva_origen_y_no_confia_en_importes_del_formulario():
    rutas=Path("modules/admin/tesoreria/routes.py").read_text(encoding="utf-8")
    panel=Path("templates/admin_tesoreria.html").read_text(encoding="utf-8")
    assert 'request.form.get("importe")' not in rutas.split('elif request.form.get("accion")=="confirmar_origen":')[1]
    assert "consolidar_origenes" in rutas and "confirmar_candidato" in rutas
    assert "Confirmar como proyección" in panel

def test_confirmacion_no_cobra_paga_contabiliza_ni_conecta():
    s=Path("services/confirmacion_origen_tesoreria.py").read_text(encoding="utf-8")
    for x in ("PagoObligacionCostoProductivo(","MovimientoLiquidacionCanal(","requests.","urlopen","http://","https://"):assert x not in s
