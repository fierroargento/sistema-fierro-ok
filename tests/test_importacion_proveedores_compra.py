from pathlib import Path
from types import SimpleNamespace

from services.importacion_proveedores_compra import (
    previsualizar_proveedores, resumir_proveedores, sugerir_mapeo_proveedores,
)


def filas(*valores):
    return [
        {"numero": indice + 2, "valores": list(fila)}
        for indice, fila in enumerate(valores)
    ]


def test_mapeo_reutiliza_el_maestro_de_compras():
    assert sugerir_mapeo_proveedores(
        ["Código", "Razón Social", "CUIT", "Correo"]
    ) == {"0": "codigo", "1": "razon_social", "2": "cuit", "3": "email"}


def test_vista_crea_actualiza_y_detecta_sin_cambios():
    existente = SimpleNamespace(
        id=4, codigo="CODIMAT", razon_social="Codimat SRL",
        cuit="30-71234567-8", email=None, telefono=None,
        estado="activo", observacion=None,
    )
    vista = previsualizar_proveedores(
        filas(
            ("CODIMAT", "Codimat SRL", "30-71234567-8"),
            ("NUEVO", "Nuevo SA", "30-70000000-1"),
        ), {"0": "codigo", "1": "razon_social", "2": "cuit"},
        proveedores=[existente],
    )
    assert [item["accion"] for item in vista] == ["sin_cambios", "crear"]
    assert resumir_proveedores(vista)["crear"] == 1


def test_rechaza_duplicados_y_conflicto_codigo_cuit():
    primero = SimpleNamespace(id=1, codigo="A", cuit="30711111111")
    segundo = SimpleNamespace(id=2, codigo="B", cuit="30722222222")
    vista = previsualizar_proveedores(
        filas(
            ("A", "Proveedor", "30-72222222-2"),
            ("A", "Repetido", "30-73333333-3"),
        ), {"0": "codigo", "1": "razon_social", "2": "cuit"},
        proveedores=[primero, segundo],
    )
    assert vista[0]["accion"] == "rechazado"
    assert "proveedores distintos" in vista[0]["errores"][0]
    assert "Codigo duplicado" in " ".join(vista[1]["errores"])


def test_importador_se_integra_en_compras_sin_tabla_duplicada():
    rutas = Path("modules/admin/compras/routes.py").read_text(encoding="utf-8")
    plantilla = Path("templates/admin_importacion_proveedores.html").read_text(encoding="utf-8")
    modelo = Path("models/compras.py").read_text(encoding="utf-8")
    assert 'tipo_lote = "proveedores_compra"' in rutas
    assert 'modelos["ProveedorCompra"]' in rutas
    assert "IMPORTAR PROVEEDORES" not in rutas and "Escribí <strong>IMPORTAR PROVEEDORES</strong>" not in plantilla
    assert plantilla.count('method="post"') == plantilla.count('name="_csrf_token"')
    assert "No crea órdenes, recepciones, pagos ni conexiones externas" in plantilla
    assert modelo.count("class ProveedorCompra") == 1


def test_importacion_antigua_preserva_domicilio_y_contacto():
    from types import SimpleNamespace
    proveedor=SimpleNamespace(id=1,codigo="UAT",razon_social="Proveedor",cuit=None,email=None,telefono=None,estado="activo",observacion=None,domicilio="Calle 123",localidad="Viedma",provincia="Río Negro",codigo_postal="8500",persona_contacto="Contacto UAT")
    vista=previsualizar_proveedores([{"numero":2,"valores":["UAT","Proveedor"]}],{"0":"codigo","1":"razon_social"},proveedores=[proveedor])
    assert vista[0]["accion"] == "sin_cambios"
    assert vista[0]["datos"]["domicilio"] == "Calle 123"
    assert vista[0]["datos"]["persona_contacto"] == "Contacto UAT"
