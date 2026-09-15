import json
from pathlib import Path
from types import SimpleNamespace

from services.certificacion_offline_facturacion import certificar_facturacion, exportar_certificacion


def datos():
    entidad=SimpleNamespace(id=1,organizacion_id=7,cuit="30-12345678-9",activa=True,facturacion_habilitada=False)
    config=SimpleNamespace(id=2,organizacion_id=7,entidad_fiscal_id=1,ambiente="homologacion",certificado_env="ARCA_CERT_1",clave_privada_env="ARCA_KEY_1",token_env="")
    punto=SimpleNamespace(id=3,organizacion_id=7,entidad_fiscal_id=1,configuracion_fiscal_id=2,numero=4,emision_real_habilitada=False)
    tipo=SimpleNamespace(id=4,punto_venta_fiscal_id=3,codigo_arca=6,punto_venta=punto)
    item=SimpleNamespace(neto_centavos=10000,iva_centavos=2100)
    borrador=SimpleNamespace(id=5,organizacion_id=7,entidad_fiscal_id=1,punto_venta_fiscal_id=3,estado="borrador",items=[item],neto_centavos=10000,iva_centavos=2100,otros_tributos_centavos=0,total_centavos=12100,cae=None,numero_autorizado=None)
    evento=SimpleNamespace(id=6,organizacion_id=7)
    return entidad,config,punto,tipo,borrador,evento


def ejecutar(**cambios):
    entidad,config,punto,tipo,borrador,evento=datos()
    base={"organizacion_id":7,"modulo":SimpleNamespace(estado="prueba"),"entidades":[entidad],"configuraciones":[config],"puntos":[punto],"tipos":[tipo],"borradores":[borrador],"eventos":[evento]}
    base.update(cambios)
    return certificar_facturacion(**base)


def test_certifica_cadena_fiscal_coherente_sin_emision():
    resultado=ejecutar()
    assert resultado["aprobada"] and resultado["resumen"]["bloqueos"]==0
    assert resultado["emision_real"] is False
    assert resultado["acciones_externas"]==resultado["escrituras"]==0


def test_detecta_cuit_invalido_y_entidad_inactiva():
    entidad,*resto=datos();entidad.cuit="123";entidad.activa=False;entidad.facturacion_habilitada=True
    resultado=ejecutar(entidades=[entidad])
    assert not resultado["aprobada"]
    assert {x["codigo"] for x in resultado["hallazgos"]}>={"cuit_invalido","entidad_inactiva"}


def test_detecta_secretos_persistidos_y_ambiente_invalido():
    _,config,*_=datos();config.ambiente="otro";config.clave_privada_env="-----BEGIN PRIVATE KEY-----"
    resultado=ejecutar(configuraciones=[config])
    assert {x["codigo"] for x in resultado["hallazgos"]}>={"ambiente_invalido","secreto_persistido"}


def test_bloquea_emision_real_y_cadenas_ajenas():
    _,_,punto,tipo,_,_=datos();punto.emision_real_habilitada=True;punto.entidad_fiscal_id=99
    resultado=ejecutar(puntos=[punto],tipos=[tipo])
    assert {x["codigo"] for x in resultado["hallazgos"]}>={"emision_real_habilitada","punto_venta_ajeno"}


def test_recalcula_y_detecta_totales_inconsistentes():
    *_,borrador,_=datos();borrador.total_centavos=999
    resultado=ejecutar(borradores=[borrador])
    assert resultado["borradores"][0]["total_centavos"]==12100
    assert "totales_inconsistentes" in resultado["borradores"][0]["bloqueos"]


def test_bloquea_autorizacion_impropia_y_listo_sin_items():
    *_,borrador,_=datos();borrador.estado="listo";borrador.items=[];borrador.neto_centavos=borrador.iva_centavos=borrador.total_centavos=0;borrador.cae="CAE-ILEGITIMO"
    resultado=ejecutar(borradores=[borrador])
    codigos={x["codigo"] for x in resultado["hallazgos"]}
    assert {"borrador_listo_sin_items","autorizacion_impropia"}<=codigos


def test_excluye_registros_de_otro_tenant():
    entidad,config,punto,tipo,borrador,evento=datos()
    for objeto in (entidad,config,punto,borrador,evento):objeto.organizacion_id=99
    resultado=ejecutar(entidades=[entidad],configuraciones=[config],puntos=[punto],tipos=[tipo],borradores=[borrador],eventos=[evento])
    assert resultado["resumen"]["entidades"]==resultado["resumen"]["borradores"]==0


def test_firma_y_exportacion_utf8_son_estables():
    primero=ejecutar();segundo=ejecutar()
    assert primero["firma_certificacion"]==segundo["firma_certificacion"]
    salida=json.loads(exportar_certificacion(primero).getvalue().decode("utf-8"))
    assert salida["firma_certificacion"]==primero["firma_certificacion"]


def test_panel_y_servicio_permanecen_desconectados():
    raiz=Path(__file__).resolve().parents[1]
    servicio=(raiz/"services/certificacion_offline_facturacion.py").read_text(encoding="utf-8")
    ruta=(raiz/"modules/admin/facturacion/routes.py").read_text(encoding="utf-8")
    html=(raiz/"templates/admin_certificacion_facturacion_offline.html").read_text(encoding="utf-8")
    for prohibido in ("requests.","urlopen","db.session","access_token","client_secret",".commit(","Pedido.query"):
        assert prohibido not in servicio
    assert "certificacion_offline" in ruta
    assert "La emisión real permanece deshabilitada" in html
