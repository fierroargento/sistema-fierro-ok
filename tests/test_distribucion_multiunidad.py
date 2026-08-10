from decimal import Decimal
from pathlib import Path

import pytest

from services.distribucion_laboral import normalizar_asignaciones


def _fila(unidad, porcentaje, ubicacion="Taller", funcion="directa"):
    return {
        "unidad_negocio_id": unidad,
        "porcentaje_asignacion": porcentaje,
        "ubicacion_trabajo": ubicacion,
        "tipo_funcion": funcion,
    }


def test_acepta_distribucion_franco_setenta_treinta():
    filas = normalizar_asignaciones([
        _fila(1, "30", "Taller", "indirecta_productiva"),
        _fila(2, "70", "Salón de venta", "comercial_administrativa"),
    ])
    assert [fila["porcentaje_asignacion"] for fila in filas] == [
        Decimal("30"), Decimal("70"),
    ]


def test_descarta_unidades_en_cero_y_exige_total_exacto():
    assert len(normalizar_asignaciones([_fila(1, 100), _fila(2, 0, "")])) == 1
    with pytest.raises(ValueError, match="sumar 100"):
        normalizar_asignaciones([_fila(1, 60), _fila(2, 30)])


def test_no_admite_unidades_repetidas():
    with pytest.raises(ValueError, match="repetir"):
        normalizar_asignaciones([_fila(1, 50), _fila(1, 50)])


def test_panel_y_registro_siguen_modulares():
    template = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")
    servicio = Path("services/fuentes_costo_admin.py").read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")
    assert 'value="configurar_distribucion_laboral"' in template
    assert 'name="distribucion_porcentaje"' in template
    assert "Distribuir costos laborales entre unidades" in template
    assert 'formulario.getlist("distribucion_unidad_id")' in servicio
    assert "normalizar_asignaciones" not in app
