from pathlib import Path
from types import SimpleNamespace
import json

from services.certificacion_accesos_saas import certificar_accesos,exportar_certificacion


def obj(**kw): return SimpleNamespace(**kw)


def membresia(mid=1,uid=2,org=7,rol="admin",activa=True,predeterminada=True,usuario_activo=True):
    m=obj(id=mid,usuario_id=uid,organizacion_id=org,rol=rol,activa=activa,predeterminada=predeterminada)
    u=obj(id=uid,username=f"usuario{uid}",password_hash="hash-seguro",activo=usuario_activo,membresias_organizacion=[m]);m.usuario=u;return m


def test_certificacion_limpia_y_solo_lectura():
    m=membresia();r=certificar_accesos(organizacion_id=7,membresias=[m],usuario_actual=m.usuario);assert r["aprobada"] and r["resumen"]["administradores_activos"]==1 and r["controles"]["escrituras"]==0


def test_detecta_rol_credencial_e_identidad_global():
    m=membresia(rol="superadmin",usuario_activo=False);m.usuario.password_hash="";r=certificar_accesos(organizacion_id=7,membresias=[m],usuario_actual=m.usuario);assert {"rol_invalido","credencial_incompleta","identidad_global_inactiva","tenant_sin_admin","sesion_admin_inconsistente"}<={x["codigo"] for x in r["hallazgos"]}


def test_detecta_membresia_y_username_duplicados():
    a=membresia(mid=1);b=membresia(mid=2);b.usuario.username=a.usuario.username;r=certificar_accesos(organizacion_id=7,membresias=[a,b],usuario_actual=a.usuario);assert {"membresia_duplicada","username_duplicado"}<={x["codigo"] for x in r["hallazgos"]}


def test_detecta_predeterminado_ambiguo_multitenant():
    m=membresia();otra=obj(id=8,usuario_id=2,organizacion_id=9,rol="carga",activa=True,predeterminada=True,usuario=m.usuario);m.usuario.membresias_organizacion=[m,otra];r=certificar_accesos(organizacion_id=7,membresias=[m],usuario_actual=m.usuario);assert "tenant_predeterminado_invalido" in {x["codigo"] for x in r["hallazgos"]}


def test_excluye_membresia_ajena_y_exige_admin_local():
    m=membresia(org=9);r=certificar_accesos(organizacion_id=7,membresias=[m],usuario_actual=m.usuario);assert r["resumen"]["membresias"]==0 and not r["aprobada"]


def test_huella_estable_y_exportacion_utf8():
    m=membresia();a=certificar_accesos(organizacion_id=7,membresias=[m],usuario_actual=m.usuario);b=certificar_accesos(organizacion_id=7,membresias=[m],usuario_actual=m.usuario);assert a["huella_control"]==b["huella_control"] and json.loads(exportar_certificacion(a).read())["modo"]=="solo_lectura"


def test_panel_delega_y_servicio_no_muta():
    ruta=Path("modules/admin/usuarios/routes.py").read_text(encoding="utf-8");servicio=Path("services/certificacion_accesos_saas.py").read_text(encoding="utf-8").lower();html=Path("templates/admin_certificacion_accesos.html").read_text(encoding="utf-8");assert ".query" not in ruta and "certificar_accesos(" in ruta;assert not any(x in servicio for x in ("db.session","commit(","rollback(","password_hash =","requests","urlopen","send_mail","delete("));assert "No cambia roles, contraseñas, sesiones ni membresías" in html
