from pathlib import Path

from services.seguridad_entorno import operaciones_masivas_habilitadas


def _limpiar(monkeypatch):
    for nombre in (
        "SISTEMA_FIERRO_ENTORNO",
        "MODO_LABORATORIO_DESCONECTADO",
        "OPERACIONES_MASIVAS_HABILITADAS",
    ):
        monkeypatch.delenv(nombre, raising=False)


def _funcion(nombre):
    fuente = Path("app.py").read_text(encoding="utf-8-sig")
    bloque = fuente.split(f"def {nombre}(", 1)[1]
    return bloque.split("\n@app.route", 1)[0]


def test_operaciones_masivas_nacen_bloqueadas(monkeypatch):
    _limpiar(monkeypatch)
    assert operaciones_masivas_habilitadas() is False


def test_operaciones_masivas_solo_se_habilitan_en_staging(monkeypatch):
    _limpiar(monkeypatch)
    monkeypatch.setenv("OPERACIONES_MASIVAS_HABILITADAS", "true")
    monkeypatch.setenv("SISTEMA_FIERRO_ENTORNO", "produccion")
    assert operaciones_masivas_habilitadas() is False
    monkeypatch.setenv("SISTEMA_FIERRO_ENTORNO", "staging")
    assert operaciones_masivas_habilitadas() is True


def test_laboratorio_anula_operaciones_masivas(monkeypatch):
    _limpiar(monkeypatch)
    monkeypatch.setenv("SISTEMA_FIERRO_ENTORNO", "staging")
    monkeypatch.setenv("OPERACIONES_MASIVAS_HABILITADAS", "true")
    monkeypatch.setenv("MODO_LABORATORIO_DESCONECTADO", "true")
    assert operaciones_masivas_habilitadas() is False


def test_resets_exigen_candado_confirmacion_y_unidad():
    contratos = {
        "reset_prueba_tiendanube": "ELIMINAR PRUEBAS TN",
        "reset_prueba_mercadolibre": "ELIMINAR PRUEBAS ML",
        "reset_total_mercadolibre": "ELIMINAR TODO ML DE ESTA UNIDAD",
        "reset_ml_directo": "ELIMINAR TODO ML DE ESTA UNIDAD",
    }
    for nombre, frase in contratos.items():
        bloque = _funcion(nombre)
        assert "operaciones_masivas_habilitadas()" in bloque
        assert f'!= "{frase}"' in bloque
        if nombre == "reset_prueba_mercadolibre":
            assert "ml_borrar_pedidos_ml_cargando_importados()" in bloque
            continue
        assert "unidad_negocio_actual_o_403(membresia)" in bloque
        assert "Pedido.unidad_negocio_id == unidad.id" in bloque


def test_limpieza_de_prueba_ml_tambien_filtra_unidad():
    bloque = _funcion("ml_borrar_pedidos_ml_cargando_importados")
    assert "unidad_negocio_actual_o_403(membresia)" in bloque
    assert "Pedido.organizacion_id == membresia.organizacion_id" in bloque
    assert "Pedido.unidad_negocio_id == unidad.id" in bloque


def test_formularios_transportan_confirmacion_del_servidor():
    plantilla = Path("templates/admin_integraciones.html").read_text(
        encoding="utf-8-sig"
    )
    for frase in (
        "ELIMINAR PRUEBAS TN",
        "ELIMINAR PRUEBAS ML",
        "ELIMINAR TODO ML DE ESTA UNIDAD",
    ):
        assert f'name="confirmacion" value="{frase}"' in plantilla
