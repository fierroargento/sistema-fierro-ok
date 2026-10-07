from datetime import date
from pathlib import Path
import pytest
from services.contabilidad_nucleo import crear_cuenta,crear_borrador

class Obj:
    siguiente=1
    def __init__(self,**datos):self.__dict__.update(datos);self.id=getattr(self,"id",Obj.siguiente);Obj.siguiente+=1
class Session:
    def __init__(self):self.objetos=[];self.commits=0;self.rollbacks=0;self.flushes=0
    def add(self,x):self.objetos.append(x)
    def flush(self):self.flushes+=1
    def rollback(self):self.rollbacks+=1
    def commit(self):self.commits+=1

def test_cuenta_nace_inactiva_y_tenant():
    s=Session();c=crear_cuenta({"codigo":"1.1","nombre":"Caja","naturaleza":"activo"},organizacion_id=7,unidad_negocio_id=9,Cuenta=Obj,db_session=s,usuario_id=3)
    assert c.organizacion_id==7 and c.unidad_negocio_id==9 and c.activa is False and c.imputable is True and s.commits==1

def test_cuenta_rechaza_datos_invalidos():
    for datos in ({"codigo":"","nombre":"Caja","naturaleza":"activo"},{"codigo":"1","nombre":"Caja","naturaleza":"otro"}):
        with pytest.raises(ValueError):crear_cuenta(datos,organizacion_id=7,unidad_negocio_id=9,Cuenta=Obj,db_session=Session())

def test_borrador_nace_balanceado_y_sin_impacto():
    d=Obj(id=1,organizacion_id=7,unidad_negocio_id=9,imputable=True);h=Obj(id=2,organizacion_id=7,unidad_negocio_id=9,imputable=True);s=Session()
    a=crear_borrador({"fecha":"2026-10-01","concepto":"Compra","importe":"1.234,50","referencia":"X"},cuenta_debe=d,cuenta_haber=h,organizacion_id=7,unidad_negocio_id=9,Asiento=Obj,Linea=Obj,db_session=s,usuario_id=3)
    assert a.total_debe_centavos==a.total_haber_centavos==123450 and a.estado=="borrador"
    assert a.contabilizado is False and a.afecta_saldos is False and s.commits==1
    assert s.flushes==1 and len(s.objetos)==3
    lineas=s.objetos[1:]
    assert [(x.renglon,x.cuenta_contable_id,x.debe_centavos,x.haber_centavos) for x in lineas]==[(1,1,123450,0),(2,2,0,123450)]
    assert all(x.asiento_borrador_id==a.id and x.organizacion_id==7 and x.unidad_negocio_id==9 and not x.afecta_saldos for x in lineas)

def test_alta_manual_alimenta_diario_mayor_y_balance():
    from services.gestion_borradores_contables import generar_reportes
    d=Obj(id=1,codigo="UAT-CAJA",nombre="Caja",organizacion_id=1,unidad_negocio_id=3,imputable=True)
    h=Obj(id=2,codigo="UAT-CONTRAPARTIDA",nombre="Contrapartida",organizacion_id=1,unidad_negocio_id=3,imputable=True)
    s=Session()
    a=crear_borrador({"fecha":"2026-10-07","concepto":"Asiento sintetico UAT","importe":"1000","referencia":"UAT-ASIENTO-001"},cuenta_debe=d,cuenta_haber=h,organizacion_id=1,unidad_negocio_id=3,Asiento=Obj,Linea=Obj,db_session=s)
    r=generar_reportes(organizacion_id=1,unidad_negocio_id=3,cuentas=[d,h],asientos=[a],lineas=s.objetos[1:],desde="2026-10-07",hasta="2026-10-07")
    assert r["aprobado"] is True and r["hallazgos"]==[]
    assert r["totales"]=={"debe_centavos":100000,"haber_centavos":100000,"balanceado":True}
    assert len(r["diario_borrador"])==2 and len(r["mayor_auxiliar"])==2 and len(r["balance_sumas_saldos"])==2
    assert r["control_asientos"][0]["lineas"]==2 and r["control_asientos"][0]["integro"] is True
    assert r["controles"]=={"persistencia_reporte":False,"asientos_contabilizados":0,"libros_modificados":0,"saldos_modificados":0,"conexiones_externas":0}

def test_alta_manual_no_confirma_cabecera_si_falla_una_linea():
    d=Obj(id=1,organizacion_id=1,unidad_negocio_id=3,imputable=True)
    h=Obj(id=2,organizacion_id=1,unidad_negocio_id=3,imputable=True)
    class LineaFalla(Obj):
        def __init__(self,**datos):
            if datos["renglon"]==2:raise RuntimeError("Error al crear haber")
            super().__init__(**datos)
    s=Session()
    with pytest.raises(RuntimeError):
        crear_borrador({"fecha":"2026-10-07","concepto":"UAT","importe":"1000"},cuenta_debe=d,cuenta_haber=h,organizacion_id=1,unidad_negocio_id=3,Asiento=Obj,Linea=LineaFalla,db_session=s)
    assert s.commits==0 and s.rollbacks==1

def test_borrador_rechaza_cruces_y_cuentas_invalidas():
    base={"fecha":"2026-10-01","concepto":"X","importe":"10"};d=Obj(id=1,organizacion_id=7,unidad_negocio_id=9,imputable=True);h=Obj(id=2,organizacion_id=8,unidad_negocio_id=9,imputable=True)
    with pytest.raises(ValueError):crear_borrador(base,cuenta_debe=d,cuenta_haber=h,organizacion_id=7,unidad_negocio_id=9,Asiento=Obj,Linea=Obj,db_session=Session())
    h.organizacion_id=7;h.id=1
    with pytest.raises(ValueError):crear_borrador(base,cuenta_debe=d,cuenta_haber=h,organizacion_id=7,unidad_negocio_id=9,Asiento=Obj,Linea=Obj,db_session=Session())

def test_modelos_imponen_borrador_balanceado():
    texto=Path("models/contabilidad.py").read_text(encoding="utf-8")
    assert "total_debe_centavos = total_haber_centavos" in texto and "contabilizado = false AND afecta_saldos = false" in texto
    assert "uq_cuenta_contable_tenant_unidad" in texto and "uq_asiento_borrador_clave" in texto

def test_panel_y_registro_modular_visibles():
    rutas=Path("modules/admin/contabilidad/routes.py").read_text(encoding="utf-8");base=Path("templates/base.html").read_text(encoding="utf-8")
    boot=Path("services/bootstrap_modulos_web.py").read_text(encoding="utf-8")
    assert 'route("/admin/contabilidad")' in rutas and "admin_contabilidad.panel" in base and "crear_blueprint_contabilidad" in boot

def test_frontera_preparatoria_sin_integraciones():
    textos="".join(Path(x).read_text(encoding="utf-8") for x in ("services/contabilidad_nucleo.py","services/contabilidad_consultas.py","modules/admin/contabilidad/routes.py"))
    for termino in ("requests.","urlopen","http://","https://","LibroDiario","ARCA","AFIP"):assert termino not in textos
