import json
from pathlib import Path
import pytest
from services.precontabilidad_offline import leer_borrador,validar_borrador,exportar_validacion

def test_lee_csv_local_y_partida_doble():
    datos="asiento;fecha;cuenta;concepto;debe;haber\nA1;01/10/2026;1.1.1;Caja;1.234,50;0\nA1;01/10/2026;4.1.1;Venta;0;1.234,50\n".encode()
    lineas,errores=leer_borrador(datos,"diario.csv")
    assert not errores and lineas[0]["debe_centavos"]==123450 and lineas[1]["haber_centavos"]==123450

def test_json_y_errores_por_linea():
    datos=json.dumps([{"asiento":"A","fecha":"2026-10-01","cuenta":"1","concepto":"x","debe":"10","haber":"0"},
        {"asiento":"B","fecha":"mal","cuenta":"2","concepto":"y","debe":"0","haber":"10"}]).encode()
    lineas,errores=leer_borrador(datos,"x.json")
    assert len(lineas)==1 and len(errores)==1

def test_valida_balance_y_detecta_incompleto():
    datos=b"asiento,fecha,cuenta,concepto,debe,haber\nA,2026-10-01,1,Caja,100,0\nA,2026-10-01,4,Venta,0,100\nB,2026-10-02,5,Gasto,50,0\n"
    r=validar_borrador(organizacion_id=7,unidad_negocio_id=9,contenido=datos,nombre_archivo="x.csv")
    assert r["asientos"][0]["apto_como_borrador"] is True
    assert set(r["asientos"][1]["hallazgos"])=={"desbalanceado","partida_incompleta"}

def test_detecta_fechas_y_lineas_duplicadas():
    datos=b"asiento,fecha,cuenta,concepto,debe,haber\nA,2026-10-01,1,Caja,100,0\nA,2026-10-01,1,Caja,100,0\nA,2026-10-02,4,Venta,0,200\n"
    r=validar_borrador(organizacion_id=7,unidad_negocio_id=9,contenido=datos,nombre_archivo="x.csv")
    assert "lineas_duplicadas" in r["asientos"][0]["hallazgos"] and "fechas_inconsistentes" in r["asientos"][0]["hallazgos"]

def test_firma_reproducible_y_cero_contabilizacion():
    datos=b"asiento,fecha,cuenta,concepto,debe,haber\nA,2026-10-01,1,Caja,1,0\nA,2026-10-01,4,Venta,0,1\n"
    a=validar_borrador(organizacion_id=7,unidad_negocio_id=9,contenido=datos,nombre_archivo="x.csv")
    b=validar_borrador(organizacion_id=7,unidad_negocio_id=9,contenido=datos,nombre_archivo="x.csv")
    assert a["huella_precontable"]==b["huella_precontable"]==json.load(exportar_validacion(a))["huella_precontable"]
    assert a["controles"]["asientos_contabilizados"]==0

def test_ruta_visible_y_sin_persistencia_o_conexiones():
    rutas=Path("modules/admin/tesoreria/routes.py").read_text(encoding="utf-8");panel=Path("templates/admin_tesoreria.html").read_text(encoding="utf-8")
    servicio=Path("services/precontabilidad_offline.py").read_text(encoding="utf-8")
    assert 'route("/admin/tesoreria/precontabilidad-offline",methods=["POST"])' in rutas and "Validar borrador contable" in panel
    for termino in ("requests.","urlopen","db.session","LibroDiario(","AsientoContable("):assert termino not in servicio
