import json
from pathlib import Path
from types import SimpleNamespace

from services.ia_recolector_sync import (
    aplicar_codigo_postal_detectado_recolector,
)


class SessionFake:
    def __init__(self, fallar_en=None):
        self.fallar_en = set(fallar_en or [])
        self.intentos_commit = 0
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.intentos_commit += 1

        if self.intentos_commit in self.fallar_en:
            raise RuntimeError("falló commit")

        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def pedido_fake():
    return SimpleNamespace(
        id=15,
        codigo_postal="",
        localidad="",
        provincia="",
        ia_resumen="Resumen previo",
        ia_faltantes='["codigo_postal"]',
        ia_requiere_operador=True,
        ia_recolector_estado="requiere_operador",
        ia_ultimo_timeout_operador="pendiente",
    )


def test_aplica_cp_normaliza_y_completa_recolector():
    pedido = pedido_fake()
    session = SessionFake()
    normalizados = []

    resultado = (
        aplicar_codigo_postal_detectado_recolector(
            pedido,
            "8504",
            normalizar_ubicacion_fn=lambda p: (
                normalizados.append(p.codigo_postal)
            ),
            faltantes_fn=lambda _pedido: [],
            db_session=session,
        )
    )

    assert resultado == {
        "aplicado": True,
        "faltantes": [],
        "datos_completos": True,
    }
    assert pedido.codigo_postal == "8504"
    assert normalizados == ["8504"]
    assert session.intentos_commit == 2
    assert session.commits == 2
    assert session.rollbacks == 0
    assert json.loads(pedido.ia_faltantes) == []
    assert pedido.ia_requiere_operador is False
    assert (
        pedido.ia_recolector_estado
        == "datos_completos"
    )
    assert pedido.ia_ultimo_timeout_operador is None
    assert (
        "IA autocompletó CP simple: 8504"
        in pedido.ia_resumen
    )


def test_con_faltantes_no_limpia_bloqueo_operador():
    pedido = pedido_fake()
    session = SessionFake()

    resultado = (
        aplicar_codigo_postal_detectado_recolector(
            pedido,
            "8504",
            normalizar_ubicacion_fn=lambda _p: None,
            faltantes_fn=lambda _p: ["telefono"],
            db_session=session,
        )
    )

    assert resultado["faltantes"] == ["telefono"]
    assert resultado["datos_completos"] is False
    assert json.loads(pedido.ia_faltantes) == [
        "telefono"
    ]
    assert pedido.ia_requiere_operador is True
    assert (
        pedido.ia_recolector_estado
        == "requiere_operador"
    )
    assert (
        pedido.ia_ultimo_timeout_operador
        == "pendiente"
    )


def test_no_duplica_marca_en_resumen():
    pedido = pedido_fake()
    pedido.ia_resumen = (
        "IA autocompletó CP simple: 8504"
    )
    session = SessionFake()

    aplicar_codigo_postal_detectado_recolector(
        pedido,
        "8504",
        normalizar_ubicacion_fn=lambda _p: None,
        faltantes_fn=lambda _p: [],
        db_session=session,
    )

    assert pedido.ia_resumen.count(
        "IA autocompletó CP simple: 8504"
    ) == 1


def test_fallo_de_normalizacion_no_corta_sincronizacion():
    pedido = pedido_fake()
    session = SessionFake()
    logs = []

    def normalizar(_pedido):
        raise RuntimeError("sin ubicación")

    resultado = (
        aplicar_codigo_postal_detectado_recolector(
            pedido,
            "8504",
            normalizar_ubicacion_fn=normalizar,
            faltantes_fn=lambda _p: [],
            db_session=session,
            logger_fn=logs.append,
        )
    )

    assert resultado["aplicado"] is True
    assert session.commits == 2
    assert len(logs) == 1
    assert "sin ubicación" in logs[0]


def test_fallos_de_commit_hacen_rollback_y_continuan():
    pedido = pedido_fake()
    session = SessionFake(fallar_en={1, 2})

    resultado = (
        aplicar_codigo_postal_detectado_recolector(
            pedido,
            "8504",
            normalizar_ubicacion_fn=lambda _p: None,
            faltantes_fn=lambda _p: [],
            db_session=session,
        )
    )

    assert resultado["aplicado"] is True
    assert session.intentos_commit == 2
    assert session.commits == 0
    assert session.rollbacks == 2
    assert (
        pedido.ia_recolector_estado
        == "datos_completos"
    )


def test_sin_cp_no_modifica_ni_persiste():
    pedido = pedido_fake()
    session = SessionFake()
    normalizados = []

    resultado = (
        aplicar_codigo_postal_detectado_recolector(
            pedido,
            "",
            normalizar_ubicacion_fn=(
                normalizados.append
            ),
            faltantes_fn=lambda _p: [],
            db_session=session,
        )
    )

    assert resultado == {
        "aplicado": False,
        "faltantes": [],
        "datos_completos": False,
    }
    assert pedido.codigo_postal == ""
    assert normalizados == []
    assert session.intentos_commit == 0


def test_app_delega_aplicacion_y_persistencia_cp():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )
    inicio = app.index(
        "def ia_analizar_ultimo_mensaje_pedido("
    )
    fin = app.index(
        "\ndef ia_auto_responder_post_analisis(",
        inicio,
    )
    bloque = app[inicio:fin]

    assert (
        "aplicar_codigo_postal_detectado_recolector("
        in bloque
    )
    assert (
        "normalizar_ubicacion_fn=("
        in bloque
    )
    assert "faltantes_fn=ia_faltantes_pedido" in bloque
    assert "IA autocompletó CP simple" not in bloque
    assert "nuevos_faltantes =" not in bloque
