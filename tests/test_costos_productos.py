from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
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
    calcular_subtotal_detalle,
    crear_version_costo,
    historial_costos,
)


@pytest.fixture()
def contexto_db():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///:memory:"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()

        organizacion = Organizacion(
            nombre="Grupo Fierro",
            slug="grupo-fierro-test",
        )
        otra_organizacion = Organizacion(
            nombre="Otra",
            slug="otra-test",
        )
        producto = Producto(
            sku="TEST-001",
            descripcion="Producto de prueba",
        )
        usuario = UsuarioSistema(
            username="admin-costos",
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
            codigo="fierro-test",
        )
        unidad_ajena = UnidadNegocio(
            organizacion_id=otra_organizacion.id,
            nombre="Ajena",
            codigo="ajena-test",
        )
        db.session.add_all([
            unidad,
            unidad_ajena,
        ])
        db.session.commit()

        yield {
            "organizacion": organizacion,
            "otra_organizacion": otra_organizacion,
            "unidad": unidad,
            "unidad_ajena": unidad_ajena,
            "producto": producto,
            "usuario": usuario,
        }

        db.session.remove()
        db.drop_all()


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


def test_calculo_usa_decimal_y_merma():
    assert calcular_subtotal_detalle(
        cantidad="2.5",
        costo_unitario_centavos=1000,
        porcentaje_merma="10",
    ) == 2750


def test_crea_version_con_snapshot(contexto_db):
    version = crear(contexto_db)

    assert version.numero_version == 1
    assert version.moneda == "ARS"
    assert version.estado == "preparatorio"
    assert version.vigente is False
    assert version.costo_total_centavos == 5250
    assert len(version.detalles) == 2
    assert version.detalles[0].cantidad == Decimal(
        "2.500000"
    )
    assert (
        version.detalles[0].porcentaje_merma
        == Decimal("10.000000")
    )


def test_historial_no_sobrescribe(contexto_db):
    primera = crear(contexto_db)
    segunda = crear(
        contexto_db,
        detalles=detalles_base(costo=1200),
    )

    assert primera.id != segunda.id
    assert primera.numero_version == 1
    assert segunda.numero_version == 2

    historial = historial_costos(
        organizacion_id=(
            contexto_db["organizacion"].id
        ),
        unidad_negocio_id=(
            contexto_db["unidad"].id
        ),
        producto_id=contexto_db["producto"].id,
        moneda="ARS",
        CostoProductoVersion=(
            CostoProductoVersion
        ),
    )

    assert [
        version.numero_version
        for version in historial
    ] == [2, 1]


def test_costo_general_y_especifico_independientes(
    contexto_db,
):
    general = crear(
        contexto_db,
        unidad_negocio_id=None,
    )
    especifico = crear(contexto_db)

    assert general.numero_version == 1
    assert especifico.numero_version == 1


def test_rechaza_unidad_de_otra_organizacion(
    contexto_db,
):
    with pytest.raises(
        ValueError,
        match="no pertenece",
    ):
        crear(
            contexto_db,
            unidad_negocio_id=(
                contexto_db["unidad_ajena"].id
            ),
        )


def test_activar_archiva_version_anterior(contexto_db):
    primera = crear(contexto_db)
    segunda = crear(contexto_db)
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


def test_base_impide_dos_vigentes(contexto_db):
    primera = crear(contexto_db)
    segunda = crear(contexto_db)

    primera.vigente = True
    primera.estado = "vigente"
    db.session.commit()

    segunda.vigente = True
    segunda.estado = "vigente"

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()


def test_rechaza_ordenes_repetidos(contexto_db):
    detalles = detalles_base()
    detalles[1]["orden"] = 0

    with pytest.raises(
        ValueError,
        match="no pueden repetirse",
    ):
        crear(
            contexto_db,
            detalles=detalles,
        )


def test_modulo_no_conecta_consumidores_productivos():
    servicio = Path(
        "services/costos_productos.py"
    ).read_text(encoding="utf-8")
    modelos = (
        Path(
            "models/costo_producto_version.py"
        ).read_text(encoding="utf-8")
        + Path(
            "models/costo_producto_detalle.py"
        ).read_text(encoding="utf-8")
    )

    prohibidos = [
        "MercadoLibre",
        "TiendaNube",
        "Pedido",
        "MovimientoInventario",
        "Webhook",
    ]

    for nombre in prohibidos:
        assert nombre not in servicio
        assert nombre not in modelos


def test_app_solo_registra_modelos_de_costos():
    app = Path("app.py").read_text(
        encoding="utf-8"
    )

    assert (
        "from models.costo_producto_version "
        "import CostoProductoVersion"
        in app
    )
    assert (
        "from models.costo_producto_detalle "
        "import CostoProductoDetalle"
        in app
    )
    assert "services.costos_productos import" not in app
