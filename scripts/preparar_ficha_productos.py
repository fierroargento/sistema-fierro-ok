"""Preparación explícita de staging, sin importar app.py ni iniciar jobs.

Uso: python -m scripts.preparar_ficha_productos --staging
No modifica Producto ni configura productos existentes.
"""
import argparse
import os
from sqlalchemy import create_engine, inspect, text

DDL = """CREATE TABLE producto_ficha_maestra (
    producto_id INTEGER PRIMARY KEY REFERENCES producto(id) ON DELETE CASCADE,
    organizacion_id INTEGER NOT NULL REFERENCES organizacion(id),
    nombre VARCHAR(200) NOT NULL, linea VARCHAR(120) NOT NULL,
    unidad_medida VARCHAR(30) NOT NULL,
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('simple','produccion','combo')),
    activo BOOLEAN NOT NULL, habilita_compra BOOLEAN NOT NULL,
    habilita_venta BOOLEAN NOT NULL, habilita_insumo BOOLEAN NOT NULL,
    habilita_componente BOOLEAN NOT NULL,
    insumo_id INTEGER UNIQUE REFERENCES insumo_productivo(id),
    revision INTEGER NOT NULL CHECK (revision > 0)
)"""


def preparar(engine):
    with engine.begin() as conexion:
        inspector = inspect(conexion)
        if inspector.has_table("producto_ficha_maestra"):
            from services.producto_habilitaciones import CAMPOS_FICHA
            columnas = {c["name"] for c in inspector.get_columns("producto_ficha_maestra")}
            if not set(CAMPOS_FICHA) | {"producto_id", "organizacion_id", "revision"} <= columnas:
                raise ValueError("La ficha existente tiene otro esquema; requiere revisión. No se modificó.")
            return "Ficha ya preparada. Sin cambios."
        if not all(inspector.has_table(t) for t in ("producto", "organizacion", "insumo_productivo")):
            raise ValueError("Faltan tablas base. No se preparó la ficha.")
        conexion.execute(text(DDL))
        conexion.execute(text("CREATE INDEX ix_producto_ficha_maestra_organizacion_id ON producto_ficha_maestra(organizacion_id)"))
    return "Ficha preparada. Productos existentes conservados, sin asignar tipos ni habilitaciones."


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", action="store_true", required=True)
    parser.parse_args()
    if os.environ.get("MODO_LABORATORIO_DESCONECTADO", "").lower() not in {"true", "1", "si"}:
        raise SystemExit("Solo se permite preparar la ficha en laboratorio desconectado.")
    rama = os.environ.get("RENDER_GIT_BRANCH", "")
    if rama and rama != "integracion-saas-2026-09":
        raise SystemExit("La rama del servicio no es la de integración.")
    url_servicio = os.environ.get("RENDER_EXTERNAL_URL", "")
    if url_servicio and "staging" not in url_servicio:
        raise SystemExit("El servicio no se identifica como staging.")
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("No se encontró la base del servicio.")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    print(preparar(create_engine(url)))


if __name__ == "__main__":
    main()
