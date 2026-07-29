from pathlib import Path
from types import SimpleNamespace

import pytest

from services.crm_nucleo import (
    cambiar_estado_oportunidad,
    configurar_importe_oportunidad,
    crm_habilita_automatizaciones,
    fecha_opcional,
    normalizar_canal_identidad,
    validar_probabilidad,
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


def test_importe_oportunidad_usa_centavos():
    oportunidad = SimpleNamespace(
        importe_estimado_centavos=0
    )

    configurar_importe_oportunidad(
        oportunidad,
        "12500,75",
    )

    assert (
        oportunidad.importe_estimado_centavos
        == 1250075
    )


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("0", 0),
        ("35", 35),
        (100, 100),
    ],
)
def test_probabilidad_valida(
    valor,
    esperado,
):
    assert validar_probabilidad(
        valor
    ) == esperado


@pytest.mark.parametrize(
    "valor",
    [
        "-1",
        "101",
        "texto",
    ],
)
def test_probabilidad_invalida(valor):
    with pytest.raises(ValueError):
        validar_probabilidad(valor)


def test_fecha_opcional_no_inventa_fecha():
    assert fecha_opcional("") is None
    assert (
        fecha_opcional("2026-08-15").year
        == 2026
    )


def test_identidad_rechaza_canal_desconocido():
    with pytest.raises(
        ValueError,
        match="Canal de identidad inválido",
    ):
        normalizar_canal_identidad(
            "red-inventada"
        )


def test_estado_oportunidad_hace_rollback():
    oportunidad = SimpleNamespace(
        estado="abierta"
    )
    session = SessionFake(
        RuntimeError("fallo commit")
    )

    with pytest.raises(
        RuntimeError,
        match="fallo commit",
    ):
        cambiar_estado_oportunidad(
            oportunidad,
            "ganada",
            db_session=session,
        )

    assert session.commits == 1
    assert session.rollbacks == 1


def test_crm_no_habilita_automatizaciones():
    modulo = SimpleNamespace(
        estado="activo"
    )

    assert (
        crm_habilita_automatizaciones(
            modulo
        )
        is False
    )


def test_modelos_crm_nacen_aislados():
    cliente = Path(
        "models/cliente_crm.py"
    ).read_text(encoding="utf-8")

    identidad = Path(
        "models/cliente_identidad_canal.py"
    ).read_text(encoding="utf-8")

    oportunidad = Path(
        "models/oportunidad_crm.py"
    ).read_text(encoding="utf-8")

    assert "Pedido" not in cliente
    assert "Pedido" not in identidad
    assert "Pedido" not in oportunidad
    assert "default=False" in cliente
    assert "default=False" in identidad
    assert "default=False" in oportunidad


def test_runtime_no_importa_modelos_crm():
    archivos = [
        "services/ml_importacion.py",
        "services/ml_claims.py",
        "modules/whatsapp/runtime.py",
        "modules/whatsapp/webhook.py",
    ]

    nombres = [
        "ClienteCRM",
        "OportunidadCRM",
        "ActividadCRM",
    ]

    for archivo in archivos:
        contenido = Path(archivo).read_text(
            encoding="utf-8-sig"
        )

        for nombre in nombres:
            assert nombre not in contenido
