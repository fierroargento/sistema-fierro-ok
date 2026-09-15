from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timedelta
from services.auditoria_tenant import diagnosticar_auditorias_tenant

def obj(**kw):return SimpleNamespace(**kw)
def test_modelo_declara_tenant_nullable():
 s=Path("models/auditoria.py").read_text(encoding="utf-8");assert "organizacion_id = db.Column(" in s and 'db.ForeignKey("organizacion.id")' in s and "nullable=True" in s
def test_registro_nuevo_copia_tenant_activo():
 s=Path("app.py").read_text(encoding="utf-8");bloque=s.split("def registrar_auditoria(",1)[1].split("\n\ndef ",1)[0];assert "organizacion_id=" in bloque and "membresia_actual()" in bloque
def test_panel_filtra_y_no_incluye_legacy():
 s=Path("app.py").read_text(encoding="utf-8");bloque=s.split("def admin_auditoria():",1)[1].split("\n\nfrom modules.admin.integraciones",1)[0];assert "obtener_auditorias_tenant(" in bloque and "Auditoria.query" not in bloque
def test_migracion_es_aditiva_y_sin_backfill():
 s=Path("services/migraciones_saas.py").read_text(encoding="utf-8");bloque=s.split("def asegurar_identidad_tenant_auditoria_preparatoria",1)[1].split("\ndef ",1)[0];assert "ALTER TABLE auditoria ADD COLUMN organizacion_id INTEGER" in bloque and "CREATE INDEX IF NOT EXISTS" in bloque and "UPDATE auditoria" not in bloque and "DROP " not in bloque
def test_diagnostico_excluye_otro_tenant_y_firma():
 ahora=datetime(2026,1,2);filas=[obj(id=2,organizacion_id=7,accion="Alta",fecha=ahora),obj(id=1,organizacion_id=7,accion="Cambio",fecha=ahora-timedelta(seconds=1)),obj(id=3,organizacion_id=9,accion="Ajena",fecha=ahora)];r=diagnosticar_auditorias_tenant(7,filas);assert r["resumen"]["registros"]==2 and r["resumen"]["legacy_sin_tenant_incluidos"]==0 and len(r["huella"])==64
def test_diagnostico_detecta_accion_y_secuencia():
 ahora=datetime(2026,1,2);filas=[obj(id=1,organizacion_id=7,accion="",fecha=ahora),obj(id=2,organizacion_id=7,accion="X",fecha=ahora+timedelta(seconds=1))];r=diagnosticar_auditorias_tenant(7,filas);assert {"accion_vacia","secuencia_temporal_invalida"}<={x["codigo"] for x in r["hallazgos"]}
def test_servicio_sin_escrituras_o_conexiones():
 s=Path("services/auditoria_tenant.py").read_text(encoding="utf-8").lower();assert not any(x in s for x in ("db.session","commit(","rollback(","requests","urlopen","delete(","update("))
