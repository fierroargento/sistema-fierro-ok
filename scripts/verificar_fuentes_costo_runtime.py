"""Verifica en SQLite las fuentes historicas del costo productivo."""

from datetime import datetime
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from flask import Flask
from sqlalchemy import inspect

from extensions import db
from models.fuentes_costo_productivo import (
    CostoFijoProductivo,
    CostoFijoVersion,
    EmpleadoCostoVersion,
    EmpleadoProductivo,
    InsumoPrecioVersion,
    InsumoProductivo,
)
from models.organizacion import Organizacion
from models.unidad_negocio import UnidadNegocio
from models.usuario_sistema import UsuarioSistema
from services.fuentes_costo_productivo import (
    crear_costo_fijo,
    crear_empleado,
    crear_insumo,
    registrar_costo_empleado,
    registrar_importe_costo_fijo,
    registrar_precio_insumo,
)


def main():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()
        tablas = set(inspect(db.engine).get_table_names())
        esperadas = {
            "insumo_productivo", "insumo_precio_version",
            "empleado_productivo", "empleado_costo_version",
            "costo_fijo_productivo", "costo_fijo_version",
        }
        assert esperadas.issubset(tablas)

        organizacion = Organizacion(nombre="Grupo Fierro", slug="grupo-fierro")
        db.session.add(organizacion)
        db.session.flush()
        unidad = UnidadNegocio(
            organizacion_id=organizacion.id,
            codigo="fierro",
            nombre="Fierro 100% Argento",
        )
        db.session.add(unidad)
        db.session.commit()

        comunes = {
            "organizacion_id": organizacion.id,
            "unidad_negocio_id": unidad.id,
            "Organizacion": Organizacion,
            "UnidadNegocio": UnidadNegocio,
            "db_session": db.session,
        }
        insumo = crear_insumo(
            **comunes,
            codigo="hierro-6mm",
            nombre="Hierro redondo 6 mm",
            tipo="materia_prima",
            unidad_medida="metro",
            InsumoProductivo=InsumoProductivo,
        )
        precio_uno = registrar_precio_insumo(
            insumo,
            moneda="ARS",
            precio_unitario_centavos=49273,
            vigente_desde=datetime(2026, 8, 1),
            InsumoPrecioVersion=InsumoPrecioVersion,
            db_session=db.session,
        )
        precio_dos = registrar_precio_insumo(
            insumo,
            moneda="ARS",
            precio_unitario_centavos=55000,
            vigente_desde=datetime(2026, 9, 1),
            InsumoPrecioVersion=InsumoPrecioVersion,
            db_session=db.session,
        )
        assert precio_uno.vigente is False
        assert precio_uno.vigente_hasta == datetime(2026, 9, 1)
        assert precio_dos.numero_version == 2

        empleado = crear_empleado(
            **comunes,
            codigo="soldador-1",
            nombre="Soldador de prueba",
            sector="Herreria",
            puesto="Soldador",
            EmpleadoProductivo=EmpleadoProductivo,
        )
        tarifa = registrar_costo_empleado(
            empleado,
            moneda="ARS",
            sueldo_base_centavos=80000000,
            cargas_sociales_centavos=20000000,
            horas_mensuales="176",
            horas_productivas="160",
            EmpleadoCostoVersion=EmpleadoCostoVersion,
            db_session=db.session,
        )
        assert tarifa.costo_mensual_total_centavos == 100000000
        assert tarifa.costo_hora_productiva_centavos == 625000
        assert tarifa.costo_minuto_productivo_centavos == 10417

        costo_fijo = crear_costo_fijo(
            **comunes,
            codigo="alquiler-galpon",
            nombre="Alquiler del galpon",
            categoria="Infraestructura",
            integra_costo_produccion=True,
            criterio_distribucion="horas_productivas",
            CostoFijoProductivo=CostoFijoProductivo,
        )
        importe = registrar_importe_costo_fijo(
            costo_fijo,
            moneda="ARS",
            importe_mensual_centavos=150000000,
            CostoFijoVersion=CostoFijoVersion,
            db_session=db.session,
        )
        assert importe.numero_version == 1
        assert importe.vigente is True

        db.session.remove()
        db.drop_all()

    print("Runtime SQLite de fuentes de costo OK")


if __name__ == "__main__":
    main()
