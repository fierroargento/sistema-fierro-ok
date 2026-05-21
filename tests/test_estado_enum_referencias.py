import re
from pathlib import Path

from domain.estados import Estado


def test_todas_las_referencias_estado_existen():
    app_py = Path("app.py").read_text(encoding="utf-8")

    referencias = set(re.findall(r"Estado\.([A-Z_]+)", app_py))

    faltantes = [
        nombre
        for nombre in sorted(referencias)
        if not hasattr(Estado, nombre)
    ]

    assert not faltantes, (
        "Hay referencias Estado.X en app.py que no existen en domain/estados.py: "
        + ", ".join(faltantes)
    )