from types import SimpleNamespace

from services import ia_runtime


def test_actualizar_estado_ia_usa_modelo_y_db(
    monkeypatch,
):
    llamado = {}

    def servicio_fake(*args, **kwargs):
        llamado["args"] = args
        llamado["kwargs"] = kwargs
        return "estado"

    monkeypatch.setattr(
        ia_runtime,
        "actualizar_estado_conversacional_service",
        servicio_fake,
    )

    pedido = SimpleNamespace(id=123)

    assert ia_runtime.actualizar_estado_conversacional_ia(
        pedido,
        owner_actual="operador",
    ) == "estado"

    assert llamado["args"] == (
        pedido,
        ia_runtime.EstadoConversacionalPedido,
        ia_runtime.db,
    )
    assert llamado["kwargs"] == {
        "owner_actual": "operador",
    }


def test_registrar_evento_ia_usa_modelo_y_db(
    monkeypatch,
):
    llamado = {}

    def servicio_fake(*args, **kwargs):
        llamado["args"] = args
        llamado["kwargs"] = kwargs
        return "evento"

    monkeypatch.setattr(
        ia_runtime,
        "registrar_evento_operativo_service",
        servicio_fake,
    )

    assert ia_runtime.registrar_evento_operativo_ia(
        tipo_evento="prueba",
    ) == "evento"

    assert llamado["args"] == (
        ia_runtime.EventoOperativo,
        ia_runtime.db,
    )
    assert llamado["kwargs"] == {
        "tipo_evento": "prueba",
    }


def test_timeout_ia_usa_dependencias_canonicas(
    monkeypatch,
):
    llamado = {}

    def servicio_fake(*args, **kwargs):
        llamado["args"] = args
        llamado["kwargs"] = kwargs
        return True

    monkeypatch.setattr(
        ia_runtime,
        "ia_escalar_si_timeout_operativo_service",
        servicio_fake,
    )

    pedido = SimpleNamespace(id=456)

    assert ia_runtime.ia_escalar_si_timeout_operativo(
        pedido,
        canal="mercadolibre",
        motivo="Sin respuesta",
    ) is True

    assert llamado["args"] == (
        pedido,
        ia_runtime.actualizar_estado_conversacional_ia,
        ia_runtime.registrar_evento_operativo_ia,
        ia_runtime.db.session,
        ia_runtime.ia_segundos_operativos_entre,
        ia_runtime.ia_ahora_utc,
        ia_runtime.IA_TIMEOUT_RESPUESTA_SEGUNDOS,
    )
    assert llamado["kwargs"] == {
        "canal": "mercadolibre",
        "motivo": "Sin respuesta",
    }
