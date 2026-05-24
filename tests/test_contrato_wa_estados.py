import re
from pathlib import Path

import modules.whatsapp.config as wa_config


def test_todos_los_wa_estado_raw_estan_definidos_como_constantes():
    archivos = [
        Path("app.py"),
        *Path("modules/whatsapp").glob("*.py"),
    ]

    patron = re.compile(
        r'wa_estado\s*=\s*["\']([^"\']+)["\']'
    )

    estados_usados = set()

    for archivo in archivos:
        texto = archivo.read_text(encoding="utf-8")
        estados_usados.update(
            patron.findall(texto)
        )

    constantes_wa = {
        valor
        for nombre, valor in vars(wa_config).items()
        if nombre.startswith("WA_")
        and isinstance(valor, str)
    }

    faltantes = [
        estado
        for estado in sorted(estados_usados)
        if estado not in constantes_wa
    ]

    assert not faltantes, (
        "Hay wa_estado raw usados en el código que no existen "
        "como constantes WA_* en modules/whatsapp/config.py: "
        + ", ".join(faltantes)
    )