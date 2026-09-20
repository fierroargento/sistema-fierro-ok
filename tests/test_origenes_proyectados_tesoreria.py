import json
from datetime import date,datetime
from pathlib import Path
from services.origenes_proyectados_tesoreria import consolidar_origenes,exportar_origenes

class Obj:
    def __init__(self,**datos):self.__dict__.update(datos)

def fuentes():
    costo=Obj(unidad_negocio_id=9,nombre="Alquiler")
    obligacion=Obj(id=1,organizacion_id=7,costo_fijo=costo,estado="parcial",importe_centavos=100000,
        fecha_vencimiento=date(2026,10,10),pagos=[Obj(importe_centavos=25000,anulado=False)])
    factura=Obj(id=2,organizacion_id=7,unidad_negocio_id=9,estado="conciliada",obligacion_creada=False,total_centavos=50000)
    venta=Obj(id=3,organizacion_id=7,unidad_negocio_id=9,estado="confirmada",liquidacion_esperada_centavos=80000,
        cuenta_codigo="ML-1",referencia_venta="V-1",fecha_venta=datetime(2026,10,2,12,0))
    return obligacion,factura,venta

def test_consolida_saldos_e_ingresos_sin_persistir():
    o,f,v=fuentes();r=consolidar_origenes(organizacion_id=7,unidad_negocio_id=9,obligaciones=[o],facturas=[f],ventas=[v],proyecciones_existentes=[])
    assert len(r["candidatos"])==2
    assert r["candidatos"][1]["importe_centavos"]==75000
    assert {x["tipo"] for x in r["candidatos"]}=={"ingreso","egreso"}
    assert r["hallazgos"][0]["codigo"]=="factura_sin_vencimiento"

def test_detecta_duplicado_por_clave_idempotente():
    o,f,v=fuentes();uno=consolidar_origenes(organizacion_id=7,unidad_negocio_id=9,obligaciones=[o],facturas=[],ventas=[v],proyecciones_existentes=[])
    existente=Obj(organizacion_id=7,clave_idempotencia=uno["candidatos"][0]["clave_idempotencia"])
    dos=consolidar_origenes(organizacion_id=7,unidad_negocio_id=9,obligaciones=[o],facturas=[],ventas=[v],proyecciones_existentes=[existente])
    assert dos["resumen"]["duplicados"]==1

def test_excluye_pagadas_anuladas_canceladas_y_saldos_cero():
    o,f,v=fuentes();o.estado="pagada";f.estado="anulada";v.estado="cancelada"
    r=consolidar_origenes(organizacion_id=7,unidad_negocio_id=9,obligaciones=[o],facturas=[f],ventas=[v],proyecciones_existentes=[])
    assert r["candidatos"]==[] and r["hallazgos"]==[]

def test_rechaza_atribucion_cruzada():
    o,f,v=fuentes();o.organizacion_id=8;f.unidad_negocio_id=8;v.organizacion_id=8
    r=consolidar_origenes(organizacion_id=7,unidad_negocio_id=9,obligaciones=[o],facturas=[f],ventas=[v],proyecciones_existentes=[])
    assert {x["codigo"] for x in r["hallazgos"]}=={"obligacion_fuera_tenant","factura_fuera_contexto","venta_fuera_contexto"}

def test_firma_reproducible_ruta_y_panel():
    o,f,v=fuentes();a=consolidar_origenes(organizacion_id=7,unidad_negocio_id=9,obligaciones=[o],facturas=[f],ventas=[v],proyecciones_existentes=[]);b=consolidar_origenes(organizacion_id=7,unidad_negocio_id=9,obligaciones=[o],facturas=[f],ventas=[v],proyecciones_existentes=[])
    assert a["huella_origenes"]==b["huella_origenes"] and json.load(exportar_origenes(a))["huella_origenes"]==a["huella_origenes"]
    assert 'route("/admin/tesoreria/origenes")' in Path("modules/admin/tesoreria/routes.py").read_text(encoding="utf-8")
    assert "obligaciones, facturas y liquidaciones" in Path("templates/admin_tesoreria.html").read_text(encoding="utf-8")

def test_servicio_no_persiste_cobra_paga_ni_conecta():
    s=Path("services/origenes_proyectados_tesoreria.py").read_text(encoding="utf-8")
    for x in ("db.session",".commit(",".add(","requests.","urlopen","http://","https://"):assert x not in s
