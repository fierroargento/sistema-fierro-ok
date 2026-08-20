from pathlib import Path
from types import SimpleNamespace

from services.inventario_disponibilidad_comercial import (
    calcular_cantidad_publicable,
    construir_vista_previa_disponibilidad,
)


def _politica(**cambios):
    catalogo = SimpleNamespace(id=20, nombre="Fierro")
    inclusion = SimpleNamespace(
        id=30, catalogo_id=20, catalogo=catalogo, sku_comercial="PP6040H"
    )
    datos = {
        "id": 1,
        "organizacion_id": 3,
        "catalogo_producto_id": 30,
        "sucursal_operativa_id": 5,
        "vinculo_canal_comercial_id": 50,
        "catalogo_producto": inclusion,
        "activa": True,
        "permite_sin_stock": False,
        "umbral_publicacion": 2,
        "maximo_publicable": 6,
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def _item(**cambios):
    datos = {
        "id": 40,
        "catalogo_producto_id": 30,
        "sku": "PP6040H",
        "activo": True,
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def _existencia(**cambios):
    datos = {
        "sucursal_operativa_id": 5,
        "item_inventario_id": 40,
        "stock_actual": 12,
        "stock_reservado": 2,
        "stock_bloqueado": 1,
        "control_activo": True,
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def _vinculo(**cambios):
    datos = {
        "organizacion_id": 3,
        "id": 50,
        "catalogo_id": 20,
        "canal": "mercado_libre",
        "nombre": "Fierro ML",
        "estado": "activo",
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def test_resta_reservas_bloqueos_umbral_y_aplica_maximo():
    resultado = calcular_cantidad_publicable(
        politica=_politica(),
        existencia=_existencia(),
        item=_item(),
        vinculo=_vinculo(),
    )
    assert resultado["disponible_fisico"] == 9
    assert resultado["cantidad_propuesta"] == 6
    assert resultado["estado"] == "publicable"
    assert resultado["puede_publicar"] is False


def test_controles_inactivos_y_falta_de_canal_publican_cero():
    resultado = calcular_cantidad_publicable(
        politica=_politica(),
        existencia=_existencia(control_activo=False),
        item=_item(),
        vinculo=None,
    )
    assert resultado["cantidad_propuesta"] == 0
    assert "Control de existencia desactivado" in resultado["motivos"]
    assert "Sin canal empresarial vinculado" in resultado["motivos"]


def test_umbral_evitar_publicar_stock_de_seguridad():
    resultado = calcular_cantidad_publicable(
        politica=_politica(umbral_publicacion=4),
        existencia=_existencia(stock_actual=5, stock_reservado=1),
        item=_item(),
        vinculo=_vinculo(),
    )
    assert resultado["cantidad_propuesta"] == 0
    assert resultado["estado"] == "bloqueado"


def test_expande_por_cuenta_y_mantiene_aislamiento():
    filas = construir_vista_previa_disponibilidad(
        [_politica()],
        items_inventario=[_item()],
        existencias=[_existencia()],
        vinculos=[
            _vinculo(),
            _vinculo(id=51, canal="tienda_nube", nombre="Fierro TN"),
        ],
    )
    assert [fila["canal"] for fila in filas] == ["mercado_libre"]
    assert all(fila["puede_publicar"] is False for fila in filas)


def test_politica_sin_cuenta_exacta_queda_bloqueada():
    filas = construir_vista_previa_disponibilidad(
        [_politica(vinculo_canal_comercial_id=None)],
        items_inventario=[_item()],
        existencias=[_existencia()],
        vinculos=[_vinculo()],
    )
    assert len(filas) == 1
    assert filas[0]["cantidad_propuesta"] == 0
    assert "Sin canal empresarial vinculado" in filas[0]["motivos"]


def test_interfaz_corrige_campos_y_declara_vista_previa():
    panel = Path("templates/admin_inventario.html").read_text(encoding="utf-8")
    servicio = Path(
        "services/inventario_disponibilidad_comercial.py"
    ).read_text(encoding="utf-8")
    assert "Vista previa desconectada" in panel
    assert "dias_cobertura" not in panel
    assert "accion_sin_stock" not in panel
    assert '"puede_publicar": False' in servicio
    assert "requests" not in servicio
