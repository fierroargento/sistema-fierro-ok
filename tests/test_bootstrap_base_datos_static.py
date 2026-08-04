from pathlib import Path


def _leer(ruta):
    return Path(ruta).read_text(
        encoding="utf-8"
    )


def test_app_delega_bootstrap_db():
    app = _leer("app.py")

    assert (
        "inicializar_base_datos_saas("
        in app
    )
    assert (
        "from services.bootstrap_base_datos import ("
        in app
    )
    assert "with app.app_context():" not in app
    assert "db.create_all()" not in app


def test_bootstrap_conserva_orden_critico():
    contenido = _leer(
        "services/bootstrap_base_datos.py"
    )

    referencias = (
        "db.create_all()",
        "asegurar_estructura_empresarial_inicial(",
        "asegurar_evento_fiscal_tenant(",
        "asegurar_movimiento_inventario_tenant(",
        "asegurar_identidad_canal_crm_tenant(",
        "asegurar_codigos_unicos_por_tenant(",
        "asegurar_modulos_iniciales(",
        "asegurar_columnas_producto_logistica(",
        "asegurar_membresias_organizacion_inicial(",
    )

    posiciones = [
        contenido.index(referencia)
        for referencia in referencias
    ]

    assert posiciones == sorted(posiciones)


def test_callbacks_legacy_son_explicitos():
    app = _leer("app.py")

    for nombre in (
        "asegurar_columnas_extra",
        "asegurar_columnas_integracion_ml",
        "backfill_ml_identidad_cuenta_pedidos",
        "asegurar_columnas_integracion_tn",
        "asegurar_usuarios_iniciales",
        "asegurar_configuracion_inicial",
    ):
        assert f'"{nombre}"' in app

    assert "locals()" not in app
    assert "globals()" not in app


def test_whatsapp_queda_fuera_del_bootstrap_db():
    app = _leer("app.py")
    bootstrap = _leer(
        "services/bootstrap_base_datos.py"
    )

    assert (
        "from modules.whatsapp import activar"
        in app
    )
    assert "activar(app)" in app
    assert "modules.whatsapp" not in bootstrap
