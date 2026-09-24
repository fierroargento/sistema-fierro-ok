"""Genera archivos sintéticos de UAT sin abrir bases ni usar la red."""

import argparse
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from services.paquete_datos_uat import construir_paquete_uat


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--salida", required=True)
    parser.add_argument("--sobrescribir", action="store_true")
    argumentos = parser.parse_args()
    destino = Path(argumentos.salida).expanduser().resolve()
    if destino.suffix.lower() != ".zip":
        raise SystemExit("La salida debe terminar en .zip")
    if destino.exists() and not argumentos.sobrescribir:
        raise SystemExit("La salida ya existe; use --sobrescribir de forma explícita.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    modo = "wb" if argumentos.sobrescribir else "xb"
    with destino.open(modo) as archivo:
        archivo.write(construir_paquete_uat().read())
    print(f"PAQUETE_UAT_GENERADO {destino.name}")


if __name__ == "__main__":
    main()
