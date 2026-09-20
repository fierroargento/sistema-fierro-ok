import json
from datetime import date
from pathlib import Path
import pytest
from services.gestion_proyecciones_tesoreria import cancelar_proyeccion
from services.control_liquidez_tesoreria import controlar_liquidez,exportar_liquidez

class Obj:
    def __init__(self,**datos):self.__dict__.update(datos)
class Session:
    def __init__(self):self.commits=0
    def commit(self):self.commits+=1

def movimiento(i,tipo,importe,fecha):return Obj(id=i,organizacion_id=7,unidad_negocio_id=9,cuenta_tesoreria_id=1,
    tipo=tipo,importe_centavos=importe,fecha_prevista=fecha,estado="proyectado",confirmado=False,afecta_saldo=False)

def test_cancelacion_conserva_registro_y_no_afecta_saldo():
    m=movimiento(1,"egreso",100,date(2026,10,1));s=Session()
    cancelar_proyeccion(m,organizacion_id=7,unidad_negocio_id=9,motivo="Ya no corresponde",db_session=s)
    assert m.estado=="cancelado" and "Ya no corresponde" in m.observacion and s.commits==1
    assert m.confirmado is False and m.afecta_saldo is False

def test_cancelacion_rechaza_contexto_estado_impacto_y_motivo():
    base=movimiento(1,"egreso",100,date(2026,10,1))
    for cambio in ("tenant","estado","impacto","motivo"):
        m=Obj(**base.__dict__);org=7;motivo="Motivo valido"
        if cambio=="tenant":org=8
        if cambio=="estado":m.estado="cancelado"
        if cambio=="impacto":m.afecta_saldo=True
        if cambio=="motivo":motivo="no"
        with pytest.raises(ValueError):cancelar_proyeccion(m,organizacion_id=org,unidad_negocio_id=9,motivo=motivo,db_session=Session())

def test_liquidez_calcula_base_y_tensiones():
    cuenta=Obj(id=1,organizacion_id=7,unidad_negocio_id=9,saldo_inicial_centavos=1000)
    movimientos=[movimiento(1,"ingreso",500,date(2026,10,5)),movimiento(2,"egreso",1200,date(2026,10,7))]
    r=controlar_liquidez(organizacion_id=7,unidad_negocio_id=9,cuentas=[cuenta],movimientos=movimientos)
    assert [x["nombre"] for x in r["escenarios"]]==["base","tension_moderada","tension_alta"]
    assert r["escenarios"][0]["saldo_final_centavos"]==300
    assert r["escenarios"][1]["primera_fecha_negativa"] is not None

def test_liquidez_detecta_cruces_e_impactos_incompatibles():
    cuenta=Obj(id=1,organizacion_id=7,unidad_negocio_id=9,saldo_inicial_centavos=0)
    m=movimiento(1,"ingreso",100,date(2026,10,1));m.confirmado=True
    r=controlar_liquidez(organizacion_id=7,unidad_negocio_id=9,cuentas=[cuenta],movimientos=[m])
    assert r["hallazgos"][0]["codigo"]=="proyeccion_con_impacto"
    cuenta.organizacion_id=8
    assert controlar_liquidez(organizacion_id=7,unidad_negocio_id=9,cuentas=[cuenta],movimientos=[])["hallazgos"][0]["codigo"]=="cuenta_fuera_contexto"

def test_control_firmado_reproducible_y_rutas_visibles():
    c=Obj(id=1,organizacion_id=7,unidad_negocio_id=9,saldo_inicial_centavos=100)
    a=controlar_liquidez(organizacion_id=7,unidad_negocio_id=9,cuentas=[c],movimientos=[]);b=controlar_liquidez(organizacion_id=7,unidad_negocio_id=9,cuentas=[c],movimientos=[])
    assert a["huella_liquidez"]==b["huella_liquidez"] and json.load(exportar_liquidez(a))["huella_liquidez"]==a["huella_liquidez"]
    rutas=Path("modules/admin/tesoreria/routes.py").read_text(encoding="utf-8");panel=Path("templates/admin_tesoreria.html").read_text(encoding="utf-8")
    assert 'route("/admin/tesoreria/liquidez")' in rutas and "Cancelar proyección" in panel

def test_control_no_mueve_dinero_contabiliza_o_conecta():
    textos="".join(Path(x).read_text(encoding="utf-8") for x in ("services/gestion_proyecciones_tesoreria.py","services/control_liquidez_tesoreria.py"))
    for x in ("PagoObligacionCostoProductivo(","MovimientoLiquidacionCanal(","requests.","urlopen","http://","https://"):assert x not in textos
