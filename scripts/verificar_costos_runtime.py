"""
Verificacion runtime aislada del dominio de costos.

Se ejecuta en un proceso independiente para utilizar Flask-SQLAlchemy
real sin los stubs generales de tests/conftest.py.
"""

from datetime import datetime
from decimal import Decimal

from flask import Flask
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.costo_producto_detalle import (
    CostoProductoDetalle,
)
from models.costo_producto_version import (
    CostoProductoVersion,
)
from models.organizacion import Organizacion
from models.producto import Producto
from models.unidad_negocio import UnidadNegocio
from models.usuario_sistema import UsuarioSistema
from services.costos_productos import (
    activar_version_costo,
    crear_version_costo,
    historial_costos,
)


def detalles_base(costo=1000):
    return [
        {
            "tipo": "insumo",
            "codigo": "CHAPA",
            "concepto": "Chapa",
            "cantidad": "2.500000",
            "unidad_medida": "kg",
            "costo_unitario_centavos": costo,
            "porcentaje_merma": "10",
            "orden": 0,
        },
        {
            "tipo": "mano_obra",
            "concepto": "Soldadura",
            "cantidad": "1.25",
            "unidad_medida": "hora",
            "costo_unitario_centavos": 2000,
            "porcentaje_merma": "0",
            "orden": 1,
        },
    ]


def crear(contexto, **cambios):
    datos = {
        "organizacion_id": (
            contexto["organizacion"].id
        ),
        "unidad_negocio_id": (
            contexto["unidad"].id
        ),
        "producto_id": contexto["producto"].id,
        "moneda": "ars",
        "tipo": "calculado",
        "detalles": detalles_base(),
        "creado_por_usuario_id": (
            contexto["usuario"].id
        ),
        "creado_por_username": "admin-costos",
        "Organizacion": Organizacion,
        "UnidadNegocio": UnidadNegocio,
        "Producto": Producto,
        "CostoProductoVersion": (
            CostoProductoVersion
        ),
        "CostoProductoDetalle": (
            CostoProductoDetalle
        ),
        "db_session": db.session,
    }
    datos.update(cambios)
    return crear_version_costo(**datos)


def cargar_contexto():
    organizacion = Organizacion(
        nombre="Grupo Fierro",
        slug="grupo-fierro-runtime",
    )
    otra_organizacion = Organizacion(
        nombre="Otra",
        slug="otra-runtime",
    )
    producto = Producto(
        sku="RUNTIME-001",
        descripcion="Producto runtime",
    )
    usuario = UsuarioSistema(
        username="admin-runtime-costos",
        password_hash="test",
        nombre="Admin",
        rol="admin",
    )

    db.session.add_all([
        organizacion,
        otra_organizacion,
        producto,
        usuario,
    ])
    db.session.flush()

    unidad = UnidadNegocio(
        organizacion_id=organizacion.id,
        nombre="Fierro",
        codigo="fierro-runtime",
    )
    unidad_ajena = UnidadNegocio(
        organizacion_id=otra_organizacion.id,
        nombre="Ajena",
        codigo="ajena-runtime",
    )

    db.session.add_all([
        unidad,
        unidad_ajena,
    ])
    db.session.commit()

    return {
        "organizacion": organizacion,
        "otra_organizacion": otra_organizacion,
        "unidad": unidad,
        "unidad_ajena": unidad_ajena,
        "producto": producto,
        "usuario": usuario,
    }


def verificar_creacion_e_historial(contexto):
    primera = crear(contexto)
    segunda = crear(
        contexto,
        detalles=detalles_base(costo=1200),
    )

    assert primera.id != segunda.id
    assert primera.numero_version == 1
    assert segunda.numero_version == 2
    assert primera.estado == "preparatorio"
    assert primera.vigente is False
    assert primera.costo_total_centavos == 5250
    assert len(primera.detalles) == 2
    assert (
        primera.detalles[0].cantidad
        == Decimal("2.500000")
    )
    assert (
        primera.detalles[0].porcentaje_merma
        == Decimal("10.000000")
    )

    historial = historial_costos(
        organizacion_id=contexto["organizacion"].id,
        unidad_negocio_id=contexto["unidad"].id,
        producto_id=contexto["producto"].id,
        moneda="ARS",
        CostoProductoVersion=(
            CostoProductoVersion
        ),
    )

    assert [
        version.numero_version
        for version in historial
    ] == [2, 1]

    return primera, segunda


def verificar_vigencia(primera, segunda):
    momento_uno = datetime(2026, 8, 6, 12, 0, 0)
    momento_dos = datetime(2026, 8, 6, 13, 0, 0)

    activar_version_costo(
        primera,
        CostoProductoVersion=(
            CostoProductoVersion
        ),
        db_session=db.session,
        ahora_fn=lambda: momento_uno,
    )
    activar_version_costo(
        segunda,
        CostoProductoVersion=(
            CostoProductoVersion
        ),
        db_session=db.session,
        ahora_fn=lambda: momento_dos,
    )

    assert primera.vigente is False
    assert primera.estado == "archivado"
    assert primera.vigente_hasta == momento_dos
    assert segunda.vigente is True
    assert segunda.estado == "vigente"
    assert segunda.vigente_desde == momento_dos


def verificar_unicidad_vigente(contexto):
    tercera = crear(contexto)
    tercera.vigente = True
    tercera.estado = "vigente"

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    else:
        raise AssertionError(
            "La base permitio dos costos vigentes."
        )


def verificar_alcances(contexto):
    general = crear(
        contexto,
        unidad_negocio_id=None,
    )

    assert general.numero_version == 1
    assert general.unidad_negocio_id is None

    try:
        crear(
            contexto,
            unidad_negocio_id=(
                contexto["unidad_ajena"].id
            ),
        )
    except ValueError as error:
        assert "no pertenece" in str(error)
    else:
        raise AssertionError(
            "Se acepto una unidad de otra organizacion."
        )


def main():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///:memory:"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()

        tablas = set(
            db.inspect(db.engine).get_table_names()
        )

        assert "costo_producto_version" in tablas
        assert "costo_producto_detalle" in tablas

        contexto = cargar_contexto()
        primera, segunda = (
            verificar_creacion_e_historial(
                contexto
            )
        )
        verificar_vigencia(primera, segunda)
        verificar_unicidad_vigente(contexto)
        verificar_alcances(contexto)

        db.session.remove()
        db.drop_all()

    print("Runtime SQLite de costos OK")


if __name__ == "__main__":
    main()
