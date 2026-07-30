from pathlib import Path
from types import SimpleNamespace

import pytest

from services.facturacion_nucleo import (
    calcular_item_fiscal,
    cambiar_estado_borrador,
    facturacion_habilita_emision_real,
    normalizar_ambiente,
    recalcular_totales_borrador,
    validar_nombre_variable_entorno,
)


class SessionFake:
    def __init__(self, error=None):
        self.error = error
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1
        if self.error is not None:
            raise self.error

    def rollback(self):
        self.rollbacks += 1


def test_ambiente_fiscal_valido():
    assert (
        normalizar_ambiente("HOMOLOGACION")
        == "homologacion"
    )
    assert (
        normalizar_ambiente("produccion")
        == "produccion"
    )


def test_variable_entorno_no_admite_secretos():
    assert (
        validar_nombre_variable_entorno(
            "ARCA_CERTIFICADO_CUIT_1"
        )
        == "ARCA_CERTIFICADO_CUIT_1"
    )

    with pytest.raises(ValueError):
        validar_nombre_variable_entorno(
            "-----BEGIN PRIVATE KEY-----"
        )


def test_calcula_item_con_iva_incluido():
    resultado = calcular_item_fiscal(
        cantidad="2",
        precio_unitario_centavos=12100,
        alicuota_iva_basis_points=2100,
    )

    assert resultado["cantidad_milesimas"] == 2000
    assert resultado["total_centavos"] == 24200
    assert resultado["neto_centavos"] == 20000
    assert resultado["iva_centavos"] == 4200


def test_recalcula_totales():
    borrador = SimpleNamespace(
        neto_centavos=0,
        iva_centavos=0,
        otros_tributos_centavos=500,
        total_centavos=0,
    )
    items = [
        SimpleNamespace(
            neto_centavos=10000,
            iva_centavos=2100,
        ),
        SimpleNamespace(
            neto_centavos=20000,
            iva_centavos=4200,
        ),
    ]

    recalcular_totales_borrador(
        borrador,
        items,
    )

    assert borrador.neto_centavos == 30000
    assert borrador.iva_centavos == 6300
    assert borrador.total_centavos == 36800


def test_admin_no_puede_autorizar_borrador():
    borrador = SimpleNamespace(
        estado="listo"
    )

    with pytest.raises(
        ValueError,
        match="no puede autorizarse",
    ):
        cambiar_estado_borrador(
            borrador,
            "autorizado",
            db_session=SessionFake(),
        )


def test_commit_fallido_hace_rollback():
    borrador = SimpleNamespace(
        estado="borrador"
    )
    session = SessionFake(
        RuntimeError("fallo commit")
    )

    with pytest.raises(
        RuntimeError,
        match="fallo commit",
    ):
        cambiar_estado_borrador(
            borrador,
            "listo",
            db_session=session,
        )

    assert session.commits == 1
    assert session.rollbacks == 1


def test_emision_real_permanece_bloqueada():
    activo = SimpleNamespace(
        estado="activo"
    )

    assert (
        facturacion_habilita_emision_real(
            activo,
            activo,
            activo,
        )
        is False
    )


def test_modelos_no_referencian_pedido():
    archivos = [
        "models/configuracion_fiscal.py",
        "models/punto_venta_fiscal.py",
        "models/tipo_comprobante_fiscal.py",
        "models/borrador_comprobante_fiscal.py",
        "models/borrador_item_fiscal.py",
        "models/evento_fiscal.py",
    ]

    for archivo in archivos:
        contenido = Path(archivo).read_text(
            encoding="utf-8"
        )
        assert 'ForeignKey("pedido.' not in contenido


def test_runtime_no_importa_facturacion_nueva():
    archivos = [
        "services/canal_manager.py",
        "services/ml_importacion.py",
        "modules/whatsapp/runtime.py",
        "modules/automation/manager.py",
    ]

    for archivo in archivos:
        contenido = Path(archivo).read_text(
            encoding="utf-8-sig"
        )
        assert "ConfiguracionFiscal" not in contenido
        assert "BorradorComprobanteFiscal" not in contenido
