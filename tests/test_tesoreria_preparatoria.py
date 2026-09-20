import json
from datetime import date
from pathlib import Path
import pytest
from services.tesoreria_nucleo import crear_cuenta,crear_proyeccion
from services.tesoreria_consultas import exportar_flujo,archivo_flujo

class Obj:
    def __init__(self,**datos):self.__dict__.update(datos)
class Modelo:
    def __init__(self,**datos):self.__dict__.update(datos)
class Session:
    def __init__(self):self.items=[];self.commits=0
    def add(self,x):self.items.append(x)
    def commit(self):self.commits+=1

def test_cuenta_nace_desconectada_e_inactiva():
    s=Session();c=crear_cuenta({"codigo":"CAJA","nombre":"Caja taller","tipo":"caja"},organizacion_id=7,unidad_negocio_id=9,CuentaTesoreria=Modelo,db_session=s,usuario_id=2)
    assert c.activa is False and c.conexion_externa is False and c.saldo_inicial_centavos==0 and s.commits==1

def test_proyeccion_es_idempotente_y_no_afecta_saldo():
    cuenta=Obj(id=3,organizacion_id=7,unidad_negocio_id=9)
    datos={"tipo":"egreso","concepto":"Alquiler","importe":"1.200,50","fecha_prevista":"2026-10-01","referencia":"ALQ-10"}
    a=crear_proyeccion(datos,cuenta=cuenta,organizacion_id=7,unidad_negocio_id=9,Movimiento=Modelo,db_session=Session())
    b=crear_proyeccion(datos,cuenta=cuenta,organizacion_id=7,unidad_negocio_id=9,Movimiento=Modelo,db_session=Session())
    assert a.importe_centavos==120050 and a.clave_idempotencia==b.clave_idempotencia
    assert a.confirmado is False and a.afecta_saldo is False

def test_rechaza_cuenta_cruzada_e_importe_invalido():
    cuenta=Obj(id=3,organizacion_id=8,unidad_negocio_id=9)
    with pytest.raises(ValueError):crear_proyeccion({"tipo":"ingreso","concepto":"X","importe":"10","fecha_prevista":"2026-10-01"},cuenta=cuenta,organizacion_id=7,unidad_negocio_id=9,Movimiento=Modelo,db_session=Session())
    cuenta.organizacion_id=7
    with pytest.raises(ValueError):crear_proyeccion({"tipo":"ingreso","concepto":"X","importe":"0","fecha_prevista":"2026-10-01"},cuenta=cuenta,organizacion_id=7,unidad_negocio_id=9,Movimiento=Modelo,db_session=Session())

def test_flujo_calcula_saldos_solo_proyectados():
    cuenta=Obj(id=1,organizacion_id=7,unidad_negocio_id=9,saldo_inicial_centavos=10000)
    movimientos=[Obj(id=1,organizacion_id=7,unidad_negocio_id=9,cuenta_tesoreria_id=1,tipo="ingreso",concepto="Venta",importe_centavos=5000,fecha_prevista=date(2026,10,1),estado="proyectado"),Obj(id=2,organizacion_id=7,unidad_negocio_id=9,cuenta_tesoreria_id=1,tipo="egreso",concepto="Compra",importe_centavos=3000,fecha_prevista=date(2026,10,2),estado="proyectado")]
    r=exportar_flujo(organizacion_id=7,unidad_negocio_id=9,cuentas=[cuenta],movimientos=movimientos)
    assert r["saldos_finales"][1]==12000 and len(r["huella_flujo"])==64
    assert json.load(archivo_flujo(r))["huella_flujo"]==r["huella_flujo"]

def test_modelos_blueprint_navegacion_y_tenant():
    assert "class CuentaTesoreria" in Path("models/tesoreria.py").read_text(encoding="utf-8")
    rutas=Path("modules/admin/tesoreria/routes.py").read_text(encoding="utf-8")
    assert 'Blueprint("admin_tesoreria"' in rutas and "organizacion_id=o.id,unidad_negocio_id=u.id" in rutas
    assert "admin_tesoreria.panel" in Path("templates/base.html").read_text(encoding="utf-8")

def test_sin_bancos_cobros_pagos_contabilidad_o_conexiones():
    textos="".join(Path(x).read_text(encoding="utf-8") for x in ("services/tesoreria_nucleo.py","services/tesoreria_consultas.py"))
    for prohibido in ("requests.","urlopen","http://","https://","PagoObligacionCostoProductivo(","MovimientoLiquidacionCanal("):
        assert prohibido not in textos
