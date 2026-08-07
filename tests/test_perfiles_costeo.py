from decimal import Decimal
from pathlib import Path
import subprocess
import sys

from services.perfiles_costeo import filas_exportables_combos, filas_exportables_perfiles


class Objeto:
    def __init__(self, **datos):
        self.__dict__.update(datos)


def test_contrato_exportable_excel_y_pdf_es_neutral():
    perfil = Objeto(
        unidad_negocio=Objeto(nombre="Fierro"),
        producto=Objeto(sku="PP6040H", descripcion="Parrilla"),
        tipo="produccion", activo=True, observacion=None,
    )
    assert filas_exportables_perfiles([perfil]) == [{
        "unidad": "Fierro", "sku": "PP6040H", "producto": "Parrilla",
        "tipo": "produccion", "activo": "Si", "observacion": "",
    }]


def test_contrato_exportable_combo():
    componente = Objeto(
        producto=Objeto(sku="FUNDA"), tipo="simple",
    )
    combo = Objeto(
        producto=Objeto(sku="COMBO-1"),
        componentes_combo=[Objeto(
            componente=componente, cantidad=Decimal("1"), observacion=None,
        )],
    )
    assert filas_exportables_combos([combo])[0]["sku_componente"] == "FUNDA"


def test_runtime_sqlite_perfiles_costeo():
    resultado = subprocess.run(
        [sys.executable, "scripts/verificar_perfiles_costeo_runtime.py"],
        cwd=Path.cwd(), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "Runtime SQLite de perfiles de costeo OK" in resultado.stdout


def test_app_solo_registra_modelos():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "from models.perfil_costeo_producto import (" in app
    assert "services.perfiles_costeo import" not in app


def test_panel_expone_tipos_y_combos_sin_canales():
    plantilla = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")
    servicio = Path("services/perfiles_costeo.py").read_text(encoding="utf-8")
    for tipo in ('value="simple"', 'value="produccion"', 'value="combo"'):
        assert tipo in plantilla
    assert "agregar_componente_combo" in servicio
    assert "filas_exportables_perfiles" in servicio
    for prohibido in ("MercadoLibre", "TiendaNube", "Pedido", "ListaPrecio"):
        assert prohibido not in servicio
