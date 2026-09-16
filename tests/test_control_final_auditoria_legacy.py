from pathlib import Path
from types import SimpleNamespace
import json
from services.control_final_auditoria_legacy import controlar_asignaciones, exportar_control


def p(pid=1, estado="aplicada", tenant=7, evidencia_tenant=7):
    evidencia={"estado":"asignable","organizacion_propuesta_id":evidencia_tenant}
    return SimpleNamespace(id=pid,auditoria_id=pid+10,organizacion_propuesta_id=7,estado=estado,
                           evidencia_json=json.dumps(evidencia),auditoria=SimpleNamespace(organizacion_id=tenant))


def test_control_aprueba_asignacion_coherente_y_firma():
    control=controlar_asignaciones(7,[p()])
    assert control["aprobado"] is True and len(control["firma_sha256"])==64
    assert control["auditorias_modificadas"]==0 and control["solo_lectura"] is True


def test_detecta_aplicacion_evidencia_y_flujo_inconsistentes():
    control=controlar_asignaciones(7,[p(1,tenant=None),p(2,estado="aprobada",tenant=7),p(3,evidencia_tenant=8)])
    codigos={x["codigo"] for x in control["observaciones"]}
    assert {"aplicacion_inconsistente","asignacion_fuera_del_flujo","evidencia_tenant_inconsistente"} <= codigos
    assert control["aprobado"] is False


def test_exportacion_utf8_reproducible():
    control=controlar_asignaciones(7,[p()]); contenido=exportar_control(control).getvalue()
    assert json.loads(contenido)["firma_sha256"]==control["firma_sha256"]


def test_rutas_y_vista_declaran_control_final():
    app=Path("app.py").read_text(encoding="utf-8")
    vista=Path("templates/admin_control_auditoria_legacy.html").read_text(encoding="utf-8")
    assert "admin_auditoria_legacy_control" in app and "obtener_control_tenant(" in app
    assert "Descargar control firmado" in vista and "control.asignaciones" in vista


def test_servicio_es_estrictamente_de_lectura():
    servicio=Path("services/control_final_auditoria_legacy.py").read_text(encoding="utf-8").lower()
    assert not any(x in servicio for x in ("db.session","commit(","rollback(","delete(","update(","requests","urlopen"))
