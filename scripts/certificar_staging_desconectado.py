"""Preflight sin red: imprime sólo diagnóstico saneado y devuelve 1 si falla."""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from services.certificacion_entorno_ensayo import certificar


def main():
    resultado = certificar()
    print(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if resultado["aprobado"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
