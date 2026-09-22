import io,json
from pathlib import Path
import pytest
from services.aceptacion_operativa_integral import evaluar,exportar,plantilla
def escenario(org=7,unidad=3):return plantilla(organizacion_id=org,unidad_negocio_id=unidad)
def test_aprueba_nueve_dominios_y_firma_sin_efectos():
 r=evaluar(escenario(),organizacion_id=7,unidad_negocio_id=3);assert r["aprobado"] and r["resumen"]["aprobados"]==9 and r["resumen"]["margen_bruto_centavos"]==20000 and len(r["huella_aceptacion"])==64;assert not r["controles"]["persistencia"]
def test_detecta_identidades_totales_stock_y_balance():
 d=json.loads(escenario().read());d["pedido"].update(producto_id=999,total_centavos=1);d["inventario"]["stock_final"]=99;d["contabilidad"]["haber_centavos"]=1;r=evaluar(io.BytesIO(json.dumps(d).encode()),organizacion_id=7,unidad_negocio_id=3);codigos={x["codigo"] for x in r["hallazgos"]};assert {"producto_pedido_inconsistente","total_pedido_inconsistente","ecuacion_stock_invalida","asiento_desbalanceado"}<=codigos
def test_bloquea_efectos_reales_y_exposicion_excesiva():
 d=json.loads(escenario().read());d["facturacion"]["emitida"]=True;d["tesoreria"]["cobrado"]=True;d["contabilidad"]["contabilizado"]=True;d["postventa"].update(ejecutada=True,cantidad_afectada=9,exposicion_centavos=999999);r=evaluar(io.BytesIO(json.dumps(d).encode()),organizacion_id=7,unidad_negocio_id=3);assert {"factura_real_emitida","cobro_real_registrado","asiento_real_contabilizado","postventa_ejecutada","postventa_supera_despacho","exposicion_supera_venta"}<={x["codigo"] for x in r["hallazgos"]}
def test_rechaza_contexto_y_dominios_faltantes():
 with pytest.raises(ValueError,match="otro tenant"):evaluar(escenario(org=8),organizacion_id=7,unidad_negocio_id=3)
 with pytest.raises(ValueError,match="otra unidad"):evaluar(escenario(unidad=4),organizacion_id=7,unidad_negocio_id=3)
 d=json.loads(escenario().read());d.pop("compras")
 with pytest.raises(ValueError,match="Faltan dominios"):evaluar(io.BytesIO(json.dumps(d).encode()),organizacion_id=7,unidad_negocio_id=3)
def test_exportacion_utf8_y_frontera_offline():
 r=evaluar(escenario(),organizacion_id=7,unidad_negocio_id=3);assert json.loads(exportar(r).read())["modo"]=="aceptacion_operativa_integral_offline";s=Path("services/aceptacion_operativa_integral.py").read_text(encoding="utf-8").lower();assert not any(x in s for x in ("db.session","commit(","requests.","urlopen","http://","https://"))
def test_ruta_admin_y_panel():
 r=Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8");h=Path("templates/admin_aceptacion_operativa_integral.html").read_text(encoding="utf-8");assert "evaluar_aceptacion_integral(" in r and "resolver_acceso()" in r;assert "sin crear pedidos, mover stock" in h

