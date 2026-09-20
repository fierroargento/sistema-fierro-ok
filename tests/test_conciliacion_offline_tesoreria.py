import json
from datetime import date
from pathlib import Path
import pytest
from services.conciliacion_offline_tesoreria import leer_extracto,conciliar_extracto,exportar_conciliacion

class Obj:
    def __init__(self,**datos):self.__dict__.update(datos)

def proyeccion(i,tipo,importe,fecha,org=7,unidad=9,cuenta=3):
    return Obj(id=i,organizacion_id=org,unidad_negocio_id=unidad,cuenta_tesoreria_id=cuenta,tipo=tipo,
        importe_centavos=importe,fecha_prevista=fecha,estado="proyectado",confirmado=False,afecta_saldo=False)

def test_csv_normaliza_formatos_y_detecta_duplicados():
    datos="fecha;concepto;importe;referencia\n01/10/2026;Venta;1.234,50;A1\n01/10/2026;Venta;1.234,50;A1\n02/10/2026;Cargo;-50,25;B2\n".encode()
    filas,errores=leer_extracto(datos,"banco.csv")
    assert not errores and filas[0]["importe_centavos"]==123450 and filas[1]["duplicado_en_archivo"] is True
    assert filas[2]["tipo"]=="egreso" and filas[2]["importe_centavos"]==5025

def test_json_admite_credito_y_debito():
    datos=json.dumps([{"fecha":"2026-10-01","descripcion":"Cobro","credito":"100.00"},{"fecha":"2026-10-02","detalle":"Cargo","debito":"20"}]).encode()
    filas,errores=leer_extracto(datos,"billetera.json")
    assert not errores and [x["tipo"] for x in filas]==["ingreso","egreso"]

def test_conciliacion_propone_por_cuenta_tipo_importe_y_fecha():
    datos=b"fecha,concepto,importe,referencia\n2026-10-03,Cobro,100.00,X\n2026-10-20,Cargo,-50.00,Y\n"
    ps=[proyeccion(1,"ingreso",10000,date(2026,10,1)),proyeccion(2,"egreso",5000,date(2026,10,2))]
    r=conciliar_extracto(organizacion_id=7,unidad_negocio_id=9,cuenta_id=3,contenido=datos,nombre_archivo="x.csv",proyecciones=ps)
    assert r["movimientos"][0]["proyeccion_id"]==1 and r["movimientos"][0]["dias_diferencia"]==2
    assert r["movimientos"][1]["estado_conciliacion"]=="sin_coincidencia"

def test_excluye_proyecciones_ajenas_canceladas_o_con_impacto():
    datos=b"fecha,concepto,importe\n2026-10-03,Cobro,100.00\n"
    ps=[proyeccion(1,"ingreso",10000,date(2026,10,1),org=8),proyeccion(2,"ingreso",10000,date(2026,10,1))]
    ps[1].estado="cancelado"
    r=conciliar_extracto(organizacion_id=7,unidad_negocio_id=9,cuenta_id=3,contenido=datos,nombre_archivo="x.csv",proyecciones=ps)
    assert r["resumen"]["candidatos"]==0 and r["controles"]["persistencia"] is False

def test_limites_errores_y_firma_reproducible():
    with pytest.raises(ValueError):leer_extracto(b"x","extracto.txt")
    datos=b"fecha,concepto,importe\nmal,Dato,0\n2026-10-01,Valido,10\n"
    a=conciliar_extracto(organizacion_id=7,unidad_negocio_id=9,cuenta_id=3,contenido=datos,nombre_archivo="x.csv",proyecciones=[])
    b=conciliar_extracto(organizacion_id=7,unidad_negocio_id=9,cuenta_id=3,contenido=datos,nombre_archivo="x.csv",proyecciones=[])
    assert a["resumen"]=={"filas_validas":1,"errores":1,"duplicados":0,"candidatos":0,"sin_coincidencia":1}
    assert a["huella_conciliacion"]==b["huella_conciliacion"]==json.load(exportar_conciliacion(a))["huella_conciliacion"]

def test_ruta_visible_y_servicio_sin_efectos_reales():
    rutas=Path("modules/admin/tesoreria/routes.py").read_text(encoding="utf-8")
    panel=Path("templates/admin_tesoreria.html").read_text(encoding="utf-8")
    servicio=Path("services/conciliacion_offline_tesoreria.py").read_text(encoding="utf-8")
    assert 'route("/admin/tesoreria/conciliacion-offline",methods=["POST"])' in rutas
    assert "Generar conciliación propuesta" in panel
    for termino in ("requests.","urlopen","PagoObligacionCostoProductivo(","MovimientoLiquidacionCanal(","db.session"):
        assert termino not in servicio
