from pathlib import Path

import pytest
from services.catalogos_comerciales import importe_a_centavos
import services.marcador_base_entorno as marcador_base
from services.seguridad_entorno import exigir_entorno_explicito
from services.tenant_context import asegurar_membresias_organizacion_inicial
from services.usuarios_admin import validar_password


def test_entorno_invalido_falla_cerrado_con_postgresql():
    with pytest.raises(RuntimeError):
        exigir_entorno_explicito({
            "DATABASE_URL": "postgresql://u:p@db/base",
            "SISTEMA_FIERRO_ENTORNO": "stagging",
        })


def test_entorno_local_sqlite_puede_ser_desarrollo():
    assert exigir_entorno_explicito({"DATABASE_URL": "sqlite:///local.db"}) == "desarrollo"


def test_marcador_rechaza_base_con_datos(monkeypatch):
    class Inspector:
        def get_schema_names(self): return ["main"]
        def get_table_names(self, schema=None): return ["pedido"]
    monkeypatch.setattr(marcador_base, "inspect", lambda _engine: Inspector())
    with pytest.raises(RuntimeError, match="no está vacía"):
        marcador_base.crear_marcador_staging(
            object(), "marcador-seguro-de-prueba-con-longitud-suficiente"
        )


def test_backfill_no_agrega_usuario_que_ya_pertenece_a_otro_tenant():
    class Membresia:
        def __init__(self, **datos): self.__dict__.update(datos)
    class Sesion:
        def __init__(self): self.agregados = []; self.commits = 0
        def add(self, objeto): self.agregados.append(objeto)
        def commit(self): self.commits += 1
    usuario = type("Usuario", (), {"id": 9, "activo": True, "rol": "admin"})()
    sesion = Sesion()
    creadas = asegurar_membresias_organizacion_inicial(
        UsuarioSistema=object,
        UsuarioOrganizacion=Membresia,
        organizacion_id=1,
        db_session=sesion,
        usuarios=[usuario],
        buscar_membresia_fn=lambda *_: None,
        buscar_cualquier_membresia_fn=lambda _usuario_id: object(),
        logger_fn=None,
    )
    assert creadas == 0
    assert sesion.agregados == []


def test_edicion_completa_usa_lista_blanca_y_excluye_ownership():
    fuente = Path("app.py").read_text(encoding="utf-8")
    assert "ADMIN_PEDIDO_CAMPOS_EDITABLES" in fuente
    assert "campo not in ADMIN_PEDIDO_CAMPOS_EDITABLES" in fuente
    bloque = fuente.split("ADMIN_PEDIDO_CAMPOS_EDITABLES =", 1)[1].split("})", 1)[0]
    for prohibido in ("organizacion_id", "unidad_negocio_id", "ml_cuenta_id"):
        assert f'"{prohibido}"' not in bloque


def test_xss_no_usa_safe_y_csp_no_admite_script_inline():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "script-src 'self' 'unsafe-inline'" not in app
    assert "'nonce-" in app
    for plantilla in Path("templates").glob("*.html"):
        contenido = plantilla.read_text(encoding="utf-8")
        assert "error|safe" not in contenido


def test_ready_exige_version_commit_marcador_y_sin_tokens():
    fuente = Path("app.py").read_text(encoding="utf-8")
    bloque = fuente.split("def readiness():", 1)[1].split("@app.errorhandler", 1)[0]
    for control in (
        "schema_version_saas", "SISTEMA_FIERRO_COMMIT_ESPERADO",
        "verificar_marcador_staging", "access_token", "refresh_token",
    ):
        assert control in bloque


def test_password_debil_y_dinero_ambiguo_se_rechazan():
    with pytest.raises(ValueError):
        validar_password("1")
    with pytest.raises(ValueError, match="ambiguo|válido"):
        importe_a_centavos("1.500")
    assert importe_a_centavos("1.500,50") == 150050
