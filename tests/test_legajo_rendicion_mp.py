import hashlib
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from services.legajo_rendicion_mp import construir_legajo_rendicion, exportar_legajo_zip


def venta(id=1, tenant=2):
    return SimpleNamespace(id=id,organizacion_id=tenant,unidad_negocio_id=3,cuenta_codigo="MP",referencia_venta=f"V{id}",referencia_pago=f"P{id}",estado="confirmada",liquidacion_esperada_centavos=900,piso_unitario_snapshot_centavos=800,cantidad=1,importe_bruto_centavos=1000)


def movimiento(id=1, importe=900, tipo="liquidacion_neta", tenant=2):
    return SimpleNamespace(id=id,organizacion_id=tenant,unidad_negocio_id=3,cuenta_codigo="MP",referencia_venta=f"V{id}",referencia_pago=f"P{id}",referencia_movimiento=f"M{id}",impacta_saldo=True,estado="confirmado",importe_centavos=importe,direccion="credito",tipo=tipo)


def cierre(id=1, estado="cerrado", tenant=2):
    snap={"filas":[{"esperado":900,"real":900,"diferencia":0}],"ventas_ids":[1],"movimientos_ids":[1],"gestiones_ids":[]}
    return SimpleNamespace(id=id,organizacion_id=tenant,unidad_negocio_id=3,estado=estado,fecha_creacion=datetime(2026,1,id),snapshot_json=json.dumps(snap),certificacion_json=json.dumps({"aprobada":True}))


def test_legajo_filtra_tenant_y_consolida_importes():
    legajo=construir_legajo_rendicion([venta(),venta(9,8)],[movimiento(),movimiento(9,999,tenant=8)],[],[cierre(),cierre(9,tenant=8)],organizacion_id=2,unidad_negocio_id=3)
    assert legajo["resumen"]["ventas"]==1 and legajo["resumen"]["liquidacion_esperada_centavos"]==900
    assert legajo["resumen"]["liquidacion_real_centavos"]==900 and legajo["tenant"]["organizacion_id"]==2


def test_legajo_bloquea_casos_y_cierres_abiertos():
    legajo=construir_legajo_rendicion([venta()],[movimiento(1,700)],[],[cierre(1,"revision")],organizacion_id=2,unidad_negocio_id=3)
    assert legajo["resumen"]["casos_pendientes"]==1 and len(legajo["bloqueos"])==2
    assert legajo["lista_para_archivar"] is False and legajo["puede_ejecutar"] is False


def test_legajo_conforme_queda_listo_para_archivar():
    legajo=construir_legajo_rendicion([venta()],[movimiento()],[],[cierre()],organizacion_id=2,unidad_negocio_id=3)
    assert legajo["lista_para_archivar"] is True and legajo["bloqueos"]==[]
    assert legajo["resumen"]["acciones_externas"]==0


def test_zip_contiene_legajo_completo_y_manifiesto_valido():
    legajo=construir_legajo_rendicion([venta()],[movimiento()],[],[cierre()],organizacion_id=2,unidad_negocio_id=3)
    with zipfile.ZipFile(exportar_legajo_zip(legajo)) as paquete:
        nombres=set(paquete.namelist())
        assert {"resumen.csv","casos.csv","periodos.csv","evidencia.json","manifiesto.json","LEEME.txt"}==nombres
        manifiesto=json.loads(paquete.read("manifiesto.json"))
        assert manifiesto["archivos"]["evidencia.json"]==hashlib.sha256(paquete.read("evidencia.json")).hexdigest()
        assert paquete.read("resumen.csv").startswith(b"\xef\xbb\xbf")


def test_exportacion_es_en_memoria_y_no_muta_el_legajo():
    legajo=construir_legajo_rendicion([],[],[],[],organizacion_id=2,unidad_negocio_id=3)
    antes=json.dumps(legajo,sort_keys=True)
    archivo=exportar_legajo_zip(legajo)
    assert isinstance(archivo,io.BytesIO) and json.dumps(legajo,sort_keys=True)==antes


def test_panel_integra_resumen_y_descarga():
    ruta=Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    html=Path("templates/admin_conciliacion_canal.html").read_text(encoding="utf-8")
    assert "construir_legajo_rendicion" in ruta and "legajo_rendicion_mp=legajo_rendicion_mp" in ruta
    assert 'value="exportar_legajo_rendicion_mp"' in html and "Legajo de rendición MP" in html


def test_contrato_desconectado_y_sin_persistencia():
    fuente=Path("services/legajo_rendicion_mp.py").read_text(encoding="utf-8").lower()
    prohibidas=("requests","urlopen","access_token","client_secret","http://","https://","db.session","commit(")
    assert not any(texto in fuente for texto in prohibidas)
    assert '"puede_ejecutar": false' in fuente
