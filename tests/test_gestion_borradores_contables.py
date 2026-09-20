import json
from datetime import date
from pathlib import Path
import pytest
from services.gestion_borradores_contables import anular_borrador,generar_reportes,exportar_reportes

class Obj:
    def __init__(self,**datos):self.__dict__.update(datos)
class Session:
    def __init__(self):self.commits=0
    def commit(self):self.commits+=1

def datos():
    cuentas=[Obj(id=1,codigo="1.1",nombre="Caja",organizacion_id=7,unidad_negocio_id=9),Obj(id=2,codigo="4.1",nombre="Ventas",organizacion_id=7,unidad_negocio_id=9)]
    asiento=Obj(id=10,referencia="A",fecha=date(2026,10,1),estado="borrador",contabilizado=False,afecta_saldos=False,total_debe_centavos=10000,total_haber_centavos=10000,organizacion_id=7,unidad_negocio_id=9)
    lineas=[Obj(id=1,asiento_borrador_id=10,renglon=1,cuenta_contable_id=1,concepto="Venta",debe_centavos=10000,haber_centavos=0,afecta_saldos=False),Obj(id=2,asiento_borrador_id=10,renglon=2,cuenta_contable_id=2,concepto="Venta",debe_centavos=0,haber_centavos=10000,afecta_saldos=False)]
    return cuentas,[asiento],lineas

def test_anulacion_conserva_registro_y_bloqueos():
    _,asientos,_=datos();s=Session();a=anular_borrador(asientos[0],organizacion_id=7,unidad_negocio_id=9,motivo="Carga incorrecta",db_session=s)
    assert a.estado=="anulado" and "Carga incorrecta" in a.referencia and not a.contabilizado and not a.afecta_saldos and s.commits==1

def test_anulacion_rechaza_contexto_estado_y_motivo():
    _,asientos,_=datos();a=asientos[0]
    with pytest.raises(ValueError):anular_borrador(a,organizacion_id=8,unidad_negocio_id=9,motivo="Motivo valido",db_session=Session())
    with pytest.raises(ValueError):anular_borrador(a,organizacion_id=7,unidad_negocio_id=9,motivo="no",db_session=Session())
    a.estado="anulado"
    with pytest.raises(ValueError):anular_borrador(a,organizacion_id=7,unidad_negocio_id=9,motivo="Motivo valido",db_session=Session())

def test_diario_y_balance_borrador_balanceados():
    c,a,l=datos();r=generar_reportes(organizacion_id=7,unidad_negocio_id=9,cuentas=c,asientos=a,lineas=l)
    assert len(r["diario_borrador"])==2 and len(r["mayor_auxiliar"])==2 and len(r["balance_sumas_saldos"])==2
    assert r["totales"]=={"debe_centavos":10000,"haber_centavos":10000,"balanceado":True}
    assert r["aprobado"] is True and r["control_asientos"][0]["integro"] is True

def test_excluye_anulados_y_detecta_impactos_o_cruces():
    c,a,l=datos();a[0].estado="anulado"
    assert generar_reportes(organizacion_id=7,unidad_negocio_id=9,cuentas=c,asientos=a,lineas=l)["diario_borrador"]==[]
    a[0].estado="borrador";l[0].afecta_saldos=True
    r=generar_reportes(organizacion_id=7,unidad_negocio_id=9,cuentas=c,asientos=a,lineas=l)
    assert r["hallazgos"][0]["codigo"]=="impacto_no_permitido"

def test_reporte_firmado_reproducible_y_no_persistente():
    c,a,l=datos();x=generar_reportes(organizacion_id=7,unidad_negocio_id=9,cuentas=c,asientos=a,lineas=l);y=generar_reportes(organizacion_id=7,unidad_negocio_id=9,cuentas=c,asientos=a,lineas=l)
    assert x["huella_reporte"]==y["huella_reporte"]==json.load(exportar_reportes(x))["huella_reporte"]
    assert x["controles"]["persistencia_reporte"] is False

def test_rutas_visibles_y_sin_registracion_real():
    rutas=Path("modules/admin/contabilidad/routes.py").read_text(encoding="utf-8");panel=Path("templates/admin_contabilidad.html").read_text(encoding="utf-8")
    servicio=Path("services/gestion_borradores_contables.py").read_text(encoding="utf-8")
    assert 'route("/admin/contabilidad/reportes-borrador")' in rutas and "Anular sin borrar" in panel
    for termino in ("requests.","urlopen","LibroDiario(","contabilizado=True","afecta_saldos=True"):assert termino not in servicio

def test_periodo_filtra_y_valida_limites():
    c,a,l=datos();r=generar_reportes(organizacion_id=7,unidad_negocio_id=9,cuentas=c,asientos=a,lineas=l,desde="2026-10-01",hasta="2026-10-31")
    assert len(r["diario_borrador"])==2 and r["periodo"]=={"desde":"2026-10-01","hasta":"2026-10-31"}
    assert generar_reportes(organizacion_id=7,unidad_negocio_id=9,cuentas=c,asientos=a,lineas=l,desde="2026-11-01")["diario_borrador"]==[]
    with pytest.raises(ValueError):generar_reportes(organizacion_id=7,unidad_negocio_id=9,cuentas=c,asientos=a,lineas=l,desde="2026-11-01",hasta="2026-10-01")

def test_control_detecta_totales_de_cabecera_inconsistentes():
    c,a,l=datos();a[0].total_debe_centavos=999;a[0].total_haber_centavos=999
    r=generar_reportes(organizacion_id=7,unidad_negocio_id=9,cuentas=c,asientos=a,lineas=l)
    assert r["aprobado"] is False and "totales_inconsistentes" in r["control_asientos"][0]["hallazgos"]
