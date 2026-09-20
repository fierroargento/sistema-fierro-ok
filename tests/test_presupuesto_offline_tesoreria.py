import json
from datetime import date
from pathlib import Path
import pytest
from services.presupuesto_offline_tesoreria import leer_presupuesto,comparar_presupuesto,exportar_presupuesto

class Obj:
    def __init__(self,**datos):self.__dict__.update(datos)

def mov(i,tipo,importe,fecha,org=7,unidad=9):
    return Obj(id=i,organizacion_id=org,unidad_negocio_id=unidad,tipo=tipo,importe_centavos=importe,
        fecha_prevista=fecha,estado="proyectado",confirmado=False,afecta_saldo=False)

def test_lee_csv_y_json_con_importes_locales():
    csv=b"mes;tipo;categoria;importe\n2026-10;ingreso;ventas;1.234,50\n2026-10;egreso;compras;500\n"
    filas,errores=leer_presupuesto(csv,"plan.csv")
    assert not errores and filas[0]["importe_centavos"]==123450
    filas_json,errores=leer_presupuesto(json.dumps([{"mes":"2026-11","tipo":"egreso","categoria":"fijos","importe":"20"}]).encode(),"plan.json")
    assert not errores and filas_json[0]["importe_centavos"]==2000

def test_detecta_partidas_invalidas_y_duplicadas():
    datos=b"mes,tipo,categoria,importe\n2026-13,ingreso,x,10\n2026-10,egreso,x,20\n2026-10,egreso,x,30\n"
    filas,errores=leer_presupuesto(datos,"plan.csv")
    assert len(filas)==1 and len(errores)==2

def test_compara_meses_desvios_y_deficit():
    datos=b"mes,tipo,categoria,importe\n2026-10,ingreso,ventas,100\n2026-10,egreso,gastos,50\n2026-11,egreso,gastos,20\n"
    ps=[mov(1,"ingreso",8000,date(2026,10,2)),mov(2,"egreso",9000,date(2026,10,3)),mov(3,"egreso",2000,date(2026,11,3))]
    r=comparar_presupuesto(organizacion_id=7,unidad_negocio_id=9,contenido=datos,nombre_archivo="p.csv",proyecciones=ps)
    assert r["meses"][0]["desvio_neto_centavos"]==-6000 and r["primer_mes_deficit"]=="2026-10"

def test_excluye_otro_tenant_y_estados_no_proyectados():
    p1=mov(1,"ingreso",100,date(2026,10,1),org=8);p2=mov(2,"ingreso",100,date(2026,10,1));p2.estado="cancelado"
    r=comparar_presupuesto(organizacion_id=7,unidad_negocio_id=9,contenido=b"mes,tipo,categoria,importe\n2026-10,ingreso,x,1\n",nombre_archivo="p.csv",proyecciones=[p1,p2])
    assert r["proyecciones_ajenas_excluidas"]==1 and r["meses"][0]["proyectado_ingresos_centavos"]==0

def test_firma_reproducible_y_control_sin_impacto():
    datos=b"mes,tipo,categoria,importe\n2026-10,ingreso,x,1\n"
    a=comparar_presupuesto(organizacion_id=7,unidad_negocio_id=9,contenido=datos,nombre_archivo="p.csv",proyecciones=[])
    b=comparar_presupuesto(organizacion_id=7,unidad_negocio_id=9,contenido=datos,nombre_archivo="p.csv",proyecciones=[])
    assert a["huella_presupuesto"]==b["huella_presupuesto"]==json.load(exportar_presupuesto(a))["huella_presupuesto"]
    assert a["controles"]["persistencia"] is False

def test_ruta_visible_y_sin_operaciones_reales():
    rutas=Path("modules/admin/tesoreria/routes.py").read_text(encoding="utf-8");panel=Path("templates/admin_tesoreria.html").read_text(encoding="utf-8")
    servicio=Path("services/presupuesto_offline_tesoreria.py").read_text(encoding="utf-8")
    assert 'route("/admin/tesoreria/presupuesto-offline",methods=["POST"])' in rutas and "Comparar presupuesto" in panel
    for termino in ("requests.","urlopen","db.session","PagoObligacionCostoProductivo(","MovimientoLiquidacionCanal("):assert termino not in servicio
