from pathlib import Path
from types import SimpleNamespace
import json
import pytest
from services.importacion_borradores_fiscales import previsualizar_borradores, exportar_previsualizacion

def objetos(tenant=7):
    e=SimpleNamespace(id=1,organizacion_id=tenant,cuit="30712345678")
    p=SimpleNamespace(id=2,organizacion_id=tenant,entidad_fiscal_id=1,numero=4)
    t=SimpleNamespace(id=3,punto_venta_fiscal_id=2,codigo_arca=6,punto_venta=p)
    return e,p,t
def archivo(ref="FAC-1",entidad="30712345678",punto="4",tipo="6",precio="121,00",iva="21"):
    return ("referencia;entidad_fiscal;punto_venta;codigo_arca;receptor;documento;condicion_iva;descripcion;sku;cantidad;precio_unitario;alicuota_iva\n"+f"{ref};{entidad};{punto};{tipo};Cliente Ñ;20123456789;Consumidor final;Producto;SKU-1;2;{precio};{iva}\n").encode("utf-8")
def ejecutar(contenido=None,tenant=7,existentes=()):
    e,p,t=objetos();return previsualizar_borradores(contenido or archivo(),organizacion_id=tenant,entidades=[e],puntos=[p],tipos=[t],referencias_existentes=existentes)
def test_agrupa_y_calcula_importes_en_centavos():
    r=ejecutar();c=r["comprobantes"][0]
    assert r["resumen"]=={"comprobantes":1,"lineas":1,"preparados":1,"rechazados":0,"acciones_externas":0,"escrituras":0}
    assert (c["neto_centavos"],c["iva_centavos"],c["total_centavos"])==(20000,4200,24200)
def test_agrupa_varias_lineas_por_referencia():
    contenido=archivo()+archivo().decode("utf-8").split("\n",1)[1].encode("utf-8")
    r=ejecutar(contenido);assert r["resumen"]["comprobantes"]==1 and r["resumen"]["lineas"]==2
def test_rechaza_cadena_fiscal_ajena():
    r=ejecutar(archivo(entidad="999",punto="8",tipo="11"));assert r["resumen"]["rechazados"]==1 and len(r["comprobantes"][0]["errores"])==3
def test_rechaza_referencia_existente():
    assert ejecutar(existentes=["FAC-1"])["comprobantes"][0]["estado"]=="rechazado"
def test_rechaza_cabecera_inconsistente():
    segunda=archivo().decode("utf-8").split("\n",1)[1].replace("Cliente Ñ","Otro")
    r=ejecutar(archivo()+segunda.encode("utf-8"));assert any("cabecera" in e for e in r["comprobantes"][0]["errores"])
def test_valida_cantidad_precio_e_iva():
    r=ejecutar(archivo(precio="-1",iva="121"));assert r["resumen"]["rechazados"]==1
def test_huellas_estables_y_exportacion_utf8():
    a=ejecutar();b=ejecutar();assert a["huella_plan"]==b["huella_plan"] and "Cliente Ñ" in exportar_previsualizacion(a).read().decode("utf-8")
def test_limites_y_columnas_obligatorias():
    with pytest.raises(ValueError): ejecutar(b"referencia;entidad\n1;2\n")
def test_panel_y_contrato_desconectado():
    ruta=Path("modules/admin/facturacion/routes.py").read_text(encoding="utf-8");html=Path("templates/admin_importacion_borradores_fiscales.html").read_text(encoding="utf-8");fuente=Path("services/importacion_borradores_fiscales.py").read_text(encoding="utf-8").lower()
    assert "importacion_offline" in ruta and "Previsualizar archivo" in html and "no crea borradores" in html.lower()
    assert not any(x in fuente for x in ("requests","urlopen","http://","https://","access_token","client_secret"))
    assert "db_session.commit()" in fuente and "db_session.rollback()" in fuente
