from pathlib import Path
from types import SimpleNamespace
import json
from services.certificacion_eventos_operativos import certificar_eventos,exportar_certificacion

def evento(eid=1,pedido_id=4,tipo="mensaje",procesado=False):return SimpleNamespace(id=eid,pedido_id=pedido_id,tipo_evento=tipo,procesado=procesado)
def test_certifica_evento_del_tenant_y_firma():
 c=certificar_eventos(7,[evento()],{4:SimpleNamespace(id=4,organizacion_id=7)});assert c["aprobado"] and len(c["firma_sha256"])==64 and c["eventos_modificados"]==0
def test_detecta_huerfano_cruce_y_tipo_vacio():
 c=certificar_eventos(7,[evento(1,4,""),evento(2,5)],{4:SimpleNamespace(organizacion_id=8)})
 codigos={x["codigo"] for x in c["observaciones"]};assert {"pedido_tenant_cruzado","pedido_huerfano_o_ajeno","tipo_evento_vacio"}<=codigos
def test_exporta_json_utf8():
 c=certificar_eventos(7,[],{});assert json.loads(exportar_certificacion(c).getvalue())["firma_sha256"]==c["firma_sha256"]
def test_rutas_y_vista_presentes():
 a=Path("app.py").read_text(encoding="utf-8");h=Path("templates/admin_certificacion_eventos_operativos.html").read_text(encoding="utf-8");assert "admin_auditoria_eventos" in a and "Descargar certificación firmada" in h
def test_servicio_solo_lectura_y_sin_red():
 s=Path("services/certificacion_eventos_operativos.py").read_text(encoding="utf-8").lower();assert not any(x in s for x in ("db.session","commit(","rollback(","delete(","update(","requests","urlopen"))
