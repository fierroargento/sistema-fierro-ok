"""Marca una base vacía/exclusiva como staging tras el preflight sin secretos."""

import argparse
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from services.certificacion_entorno_ensayo import certificar
from services.marcador_base_entorno import crear_marcador_staging


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirmar", required=True)
    argumentos = parser.parse_args()
    if argumentos.confirmar != "MARCAR BASE STAGING AISLADA":
        raise SystemExit("Confirmación inválida; no se escribió la base.")
    resultado = certificar()
    if not resultado["aprobado"]:
        codigos = ", ".join(item["codigo"] for item in resultado["hallazgos"])
        raise SystemExit(f"Preflight rechazado: {codigos}")
    url = os.environ["DATABASE_URL"].strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(url, pool_pre_ping=True, connect_args={"sslmode": "require"})
    creado = crear_marcador_staging(engine, os.environ["STAGING_DATABASE_MARKER"])
    print("BASE_STAGING_MARCADA" if creado else "BASE_STAGING_YA_MARCADA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
