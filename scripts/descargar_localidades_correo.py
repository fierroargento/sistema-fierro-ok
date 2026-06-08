"""
Descarga localidades de Correo Argentino por provincia.

Uso:
    python scripts/descargar_localidades_correo.py

Genera:
    data/correo_localidades/B.json
    data/correo_localidades/H.json
    etc.

APB:
- Es herramienta manual/admin.
- No corre en producción automáticamente.
- No consulta CPA masivo.
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.cpa_correo import (  # noqa: E402
    PROVINCIA_NOMBRE_POR_CODIGO,
    descargar_localidades_correo,
    guardar_localidades_correo,
)


def main():
    total = 0
    errores = []

    for codigo, nombre in PROVINCIA_NOMBRE_POR_CODIGO.items():
        print(f"[CORREO] Descargando localidades {codigo} - {nombre}...")

        try:
            localidades = descargar_localidades_correo(codigo)
            guardar_localidades_correo(codigo, localidades)
            cantidad = len(localidades)
            total += cantidad
            print(f"[CORREO] OK {codigo} - {nombre}: {cantidad} localidades")

        except Exception as e:
            errores.append((codigo, nombre, str(e)))
            print(f"[CORREO] ERROR {codigo} - {nombre}: {e}")

        time.sleep(0.4)

    print(f"[CORREO] Total localidades descargadas: {total}")

    if errores:
        print("[CORREO] Errores:")
        for codigo, nombre, error in errores:
            print(f" - {codigo} - {nombre}: {error}")

        raise SystemExit(1)

    raise SystemExit(0)


if __name__ == "__main__":
    main()