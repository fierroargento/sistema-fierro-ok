from pathlib import Path

from services.auditoria_consumidores_pedidos import (
    auditar_consumidores_pedidos,
    auditar_fuentes_consumidores_pedidos,
)


def test_clasifica_consumidores_sin_importar_ni_ejecutar_codigo():
    resultado = auditar_fuentes_consumidores_pedidos([
        ("app.py", "x = Pedido.query.all()"),
        ("modules/automation/jobs/tarea.py", "Pedido.query.filter()"),
        ("services/ml_importacion.py", "Pedido.query.first()"),
        ("services/otro.py", "Pedido.query.get(1)"),
    ])
    assert resultado["total"] == 4
    assert resultado["archivos"] == 4
    assert resultado["por_grupo"] == {
        "legado_monolitico": 1,
        "automatizacion": 1,
        "importador": 1,
        "servicio": 1,
    }
    assert resultado["escrituras_realizadas"] == 0
    assert resultado["integraciones_habilitables"] is False


def test_separa_accesos_preparatorios_controlados():
    resultado = auditar_fuentes_consumidores_pedidos([
        ("services/acceso_tenant_pedidos.py", "Pedido.query.filter_by()"),
        ("services/asignacion_tenant_pedidos.py", "Pedido.query.filter()"),
        ("services/identidad_tenant_pedidos.py", "Pedido.query.all()"),
        ("services/operativo.py", "Pedido.query.all()"),
    ])
    assert resultado["total"] == 1
    assert resultado["permitidos_preparatorios"] == 3
    assert resultado["por_archivo"] == {"services/operativo.py": 1}
    assert resultado["aprobada"] is False


def test_ignora_tests_y_su_propio_archivo():
    resultado = auditar_fuentes_consumidores_pedidos([
        ("tests/test_algo.py", "Pedido.query.all()"),
        ("services/auditoria_consumidores_pedidos.py", "Pedido.query.all()"),
    ])
    assert resultado["total"] == 0
    assert resultado["aprobada"] is True


def test_inventario_real_encuentra_consumidores_pendientes():
    resultado = auditar_consumidores_pedidos(Path("."))
    assert resultado["total"] > 0
    assert resultado["archivos"] > 0
    assert resultado["permitidos_preparatorios"] > 0
    assert resultado["escrituras_realizadas"] == 0
    assert resultado["integraciones_habilitables"] is False
    assert resultado["por_grupo"].get("automatizacion", 0) == 0


def test_panel_muestra_bloqueo_y_conteos_separados():
    consultas = Path("services/estructura_consultas.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_estructura.html").read_text(encoding="utf-8")
    assert "auditar_consumidores_pedidos()" in consultas
    assert '"auditoria_consumidores_pedidos"' in consultas
    assert "Accesos pendientes" in panel
    assert "Accesos controlados" in panel
    assert "antes de habilitar integraciones" in panel


def test_auditor_no_contiene_transporte_ni_persistencia():
    texto = Path("services/auditoria_consumidores_pedidos.py").read_text(
        encoding="utf-8"
    ).lower()
    for prohibido in (
        "requests", "oauth", "webhook_url", "access_token", "db.session",
        ".commit(", ".add(", ".delete(",
    ):
        assert prohibido not in texto
