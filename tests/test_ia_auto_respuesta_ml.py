from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from services.ia_auto_respuesta_ml import (
    enviar_auto_respuesta_ml,
    evaluar_habilitacion_auto_respuesta_ml,
)


def pedido_base(**cambios):
    datos = {
        "id": 91,
        "ia_respuesta_sugerida": "",
        "ia_respuesta_enviada_hash": "",
        "ia_ultima_respuesta_enviada": None,
        "ia_requiere_operador": False,
        "ia_recolector_estado": "",
        "ml_mensajes_pendientes": False,
        "ml_mensajes_pendientes_count": 0,
        "ia_resumen": "",
        "ia_error": "",
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def ejecutar(
    pedido,
    texto="Necesitamos tu DNI",
    *,
    requiere_operador=False,
    faltantes=None,
    duplicada=False,
    permitido=True,
    motivo_bloqueo="bloqueado",
    error_envio=False,
):
    enviados = []
    registros = []
    logs = []
    fecha = datetime(2026, 7, 26, 21, 0, 0)

    def enviar(*args, **kwargs):
        if error_envio:
            raise RuntimeError("fallo controlado")
        enviados.append((args, kwargs))

    resultado = enviar_auto_respuesta_ml(
        pedido,
        texto,
        requiere_operador=requiere_operador,
        faltantes=faltantes or [],
        respuesta_ya_enviada_fn=(
            lambda _pedido, _texto: duplicada
        ),
        puede_enviar_fn=(
            lambda **_kwargs: (
                permitido,
                motivo_bloqueo,
            )
        ),
        enviar_mensaje_fn=enviar,
        registrar_envio_fn=(
            lambda **kwargs: registros.append(
                kwargs
            )
        ),
        hash_texto_fn=lambda valor: f"hash:{valor}",
        ahora_fn=lambda: fecha,
        log_fn=logs.append,
    )

    return (
        resultado,
        enviados,
        registros,
        logs,
        fecha,
    )


def test_sin_texto_no_envia():
    resultado, enviados, registros, _, _ = ejecutar(
        pedido_base(),
        texto="   ",
    )

    assert resultado.ok is False
    assert resultado.motivo == "sin_texto"
    assert enviados == []
    assert registros == []


def test_respuesta_duplicada_no_envia():
    resultado, enviados, registros, _, _ = ejecutar(
        pedido_base(),
        duplicada=True,
    )

    assert resultado.ok is False
    assert resultado.motivo == "duplicada"
    assert enviados == []
    assert registros == []


def test_canal_manager_bloquea_envio():
    resultado, enviados, registros, logs, _ = (
        ejecutar(
            pedido_base(),
            permitido=False,
            motivo_bloqueo="wa_activo",
        )
    )

    assert resultado.ok is False
    assert resultado.motivo == "wa_activo"
    assert enviados == []
    assert registros == []
    assert "wa_activo" in logs[0]


def test_envio_normal_limpia_pendientes():
    pedido = pedido_base(
        ml_mensajes_pendientes=True,
        ml_mensajes_pendientes_count=3,
    )

    resultado, enviados, registros, _, fecha = (
        ejecutar(pedido)
    )

    assert resultado.ok is True
    assert resultado.motivo == "enviada"
    assert len(enviados) == 1
    assert enviados[0][1] == {
        "permitir_requiere_operador": False,
    }
    assert registros == [
        {
            "pedido": pedido,
            "canal": "ml",
            "texto": "Necesitamos tu DNI",
        }
    ]
    assert (
        pedido.ia_respuesta_sugerida
        == "Necesitamos tu DNI"
    )
    assert (
        pedido.ia_respuesta_enviada_hash
        == "hash:Necesitamos tu DNI"
    )
    assert pedido.ia_ultima_respuesta_enviada == fecha
    assert pedido.ml_mensajes_pendientes is False
    assert pedido.ml_mensajes_pendientes_count == 0
    assert (
        "IA respondió automáticamente"
        in pedido.ia_resumen
    )


def test_operador_con_faltantes_habilita_envio():
    pedido = pedido_base()

    resultado, enviados, _, _, _ = ejecutar(
        pedido,
        requiere_operador=True,
        faltantes=["dni"],
    )

    assert resultado.ok is True
    assert enviados[0][1] == {
        "permitir_requiere_operador": True,
    }
    assert pedido.ia_requiere_operador is True
    assert (
        pedido.ia_recolector_estado
        == "requiere_operador"
    )
    assert pedido.ml_mensajes_pendientes is True
    assert pedido.ml_mensajes_pendientes_count == 1
    assert (
        "consulta pendiente para operador"
        in pedido.ia_resumen
    )


def test_operador_sin_faltantes_no_abre_excepcion_envio():
    pedido = pedido_base()

    resultado, enviados, _, _, _ = ejecutar(
        pedido,
        requiere_operador=True,
        faltantes=[],
    )

    assert resultado.ok is True
    assert enviados[0][1] == {
        "permitir_requiere_operador": False,
    }
    assert pedido.ia_requiere_operador is True
    assert pedido.ml_mensajes_pendientes is True


def test_error_de_envio_marca_error_controlado():
    pedido = pedido_base()

    resultado, _, registros, logs, _ = ejecutar(
        pedido,
        error_envio=True,
    )

    assert resultado.ok is False
    assert resultado.motivo == "error_envio"
    assert registros == []
    assert "fallo controlado" in pedido.ia_error
    assert len(logs) == 1


def test_app_delega_envio_final_al_servicio():
    app = Path("app.py").read_text(encoding="utf-8")

    inicio = app.index(
        "def ia_auto_responder_post_analisis("
    )
    fin = app.find("\ndef ", inicio + 1)
    bloque = app[inicio:fin]

    assert "enviar_auto_respuesta_ml(" in bloque
    assert (
        "requiere_operador=("
        in bloque
    )
    assert "faltantes=faltantes" in bloque
    assert (
        "resultado_envio.motivo"
        in bloque
    )

    prohibidos = [
        "permitir_requiere_operador=bool(",
        "IA respondió automáticamente",
        "IA respondió y dejó consulta",
        "construir_log_error_wa_auto_ml",
        'return False, "error_envio"',
    ]

    for prohibido in prohibidos:
        assert prohibido not in bloque


def evaluar_habilitacion(pedido):
    return evaluar_habilitacion_auto_respuesta_ml(
        pedido,
        es_pedido_aplicable_fn=(
            lambda valor:
            getattr(valor, "aplicable", False)
        ),
    )


def test_habilitacion_auto_respuesta_respeta_feature_flag(
    monkeypatch,
):
    monkeypatch.setenv(
        "IA_AUTO_RESPUESTA",
        "off",
    )
    pedido = SimpleNamespace(
        aplicable=True,
        contacto_iniciado=True,
        ia_recolector_estado="ok",
    )

    resultado = evaluar_habilitacion(pedido)

    assert resultado.habilitada is False
    assert resultado.motivo == "apagada"


def test_habilitacion_rechaza_pedido_no_aplicable(
    monkeypatch,
):
    monkeypatch.setenv(
        "IA_AUTO_RESPUESTA",
        "1",
    )
    pedido = SimpleNamespace(
        aplicable=False,
        contacto_iniciado=True,
        ia_recolector_estado="ok",
    )

    resultado = evaluar_habilitacion(pedido)

    assert resultado.habilitada is False
    assert resultado.motivo == "no_aplica"


def test_habilitacion_requiere_contacto_iniciado(
    monkeypatch,
):
    monkeypatch.setenv(
        "IA_AUTO_RESPUESTA",
        "1",
    )
    pedido = SimpleNamespace(
        aplicable=True,
        contacto_iniciado=False,
        ia_recolector_estado="ok",
    )

    resultado = evaluar_habilitacion(pedido)

    assert resultado.habilitada is False
    assert resultado.motivo == "sin_contacto"


def test_habilitacion_rechaza_error_del_recolector(
    monkeypatch,
):
    monkeypatch.setenv(
        "IA_AUTO_RESPUESTA",
        "1",
    )
    pedido = SimpleNamespace(
        aplicable=True,
        contacto_iniciado=True,
        ia_recolector_estado="error",
    )

    resultado = evaluar_habilitacion(pedido)

    assert resultado.habilitada is False
    assert resultado.motivo == "error_ia"


def test_habilitacion_acepta_pedido_operable(
    monkeypatch,
):
    monkeypatch.setenv(
        "IA_AUTO_RESPUESTA",
        "1",
    )
    pedido = SimpleNamespace(
        aplicable=True,
        contacto_iniciado=True,
        ia_recolector_estado="ok",
    )

    resultado = evaluar_habilitacion(pedido)

    assert resultado.habilitada is True
    assert resultado.motivo == "habilitada"


def test_app_delega_guardas_iniciales_auto_respuesta():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )
    inicio = app.index(
        "def ia_auto_responder_post_analisis("
    )
    fin = app.find(
        "\ndef ",
        inicio + 1,
    )
    if fin == -1:
        fin = len(app)

    bloque = app[inicio:fin]

    assert (
        "evaluar_habilitacion_auto_respuesta_ml("
        in bloque
    )
    assert (
        "es_pedido_aplicable_fn=("
        in bloque
    )
    assert (
        "resultado_habilitacion.motivo"
        in bloque
    )

    prohibidos = [
        'os.getenv("IA_AUTO_RESPUESTA"',
        'return False, "apagada"',
        'return False, "no_aplica"',
        'return False, "sin_contacto"',
        'return False, "error_ia"',
    ]

    for prohibido in prohibidos:
        assert prohibido not in bloque

def test_preparacion_operador_con_faltantes():
    from services.ia_auto_respuesta_ml import (
        preparar_respuesta_post_analisis_ml,
    )

    llamados = []
    pedido = object()

    resultado = preparar_respuesta_post_analisis_ml(
        pedido,
        requiere_operador=True,
        faltantes=["dni"],
        generar_derivacion_y_faltantes_fn=(
            lambda recibido: (
                llamados.append(("derivacion", recibido))
                or "derivacion y faltantes"
            )
        ),
        generar_cta_operador_fn=(
            lambda recibido: (
                llamados.append(("cta", recibido))
                or "cta"
            )
        ),
        generar_faltantes_fn=(
            lambda recibido: (
                llamados.append(("faltantes", recibido))
                or "faltantes"
            )
        ),
    )

    assert resultado.texto == "derivacion y faltantes"
    assert resultado.datos_completos is False
    assert llamados == [("derivacion", pedido)]


def test_preparacion_operador_sin_faltantes():
    from services.ia_auto_respuesta_ml import (
        preparar_respuesta_post_analisis_ml,
    )

    llamados = []
    pedido = object()

    resultado = preparar_respuesta_post_analisis_ml(
        pedido,
        requiere_operador=True,
        faltantes=[],
        generar_derivacion_y_faltantes_fn=(
            lambda recibido: (
                llamados.append(("derivacion", recibido))
                or "derivacion"
            )
        ),
        generar_cta_operador_fn=(
            lambda recibido: (
                llamados.append(("cta", recibido))
                or "cta operador"
            )
        ),
        generar_faltantes_fn=(
            lambda recibido: (
                llamados.append(("faltantes", recibido))
                or "faltantes"
            )
        ),
    )

    assert resultado.texto == "cta operador"
    assert resultado.datos_completos is False
    assert llamados == [("cta", pedido)]


def test_preparacion_datos_completos_no_genera_texto():
    from services.ia_auto_respuesta_ml import (
        preparar_respuesta_post_analisis_ml,
    )

    llamados = []

    def no_debe_llamarse(_pedido):
        llamados.append("llamado")
        return "inesperado"

    resultado = preparar_respuesta_post_analisis_ml(
        object(),
        requiere_operador=False,
        faltantes=[],
        generar_derivacion_y_faltantes_fn=(
            no_debe_llamarse
        ),
        generar_cta_operador_fn=no_debe_llamarse,
        generar_faltantes_fn=no_debe_llamarse,
    )

    assert resultado.texto == ""
    assert resultado.datos_completos is True
    assert llamados == []


def test_preparacion_faltantes_sin_operador():
    from services.ia_auto_respuesta_ml import (
        preparar_respuesta_post_analisis_ml,
    )

    llamados = []
    pedido = object()

    resultado = preparar_respuesta_post_analisis_ml(
        pedido,
        requiere_operador=False,
        faltantes=["telefono"],
        generar_derivacion_y_faltantes_fn=(
            lambda recibido: (
                llamados.append(("derivacion", recibido))
                or "derivacion"
            )
        ),
        generar_cta_operador_fn=(
            lambda recibido: (
                llamados.append(("cta", recibido))
                or "cta"
            )
        ),
        generar_faltantes_fn=(
            lambda recibido: (
                llamados.append(("faltantes", recibido))
                or "pedir faltantes"
            )
        ),
    )

    assert resultado.texto == "pedir faltantes"
    assert resultado.datos_completos is False
    assert llamados == [("faltantes", pedido)]


def test_app_delega_preparacion_post_analisis_ml():
    from pathlib import Path

    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )
    inicio = app.index(
        "def ia_auto_responder_post_analisis("
    )
    fin = app.index(
        "\ndef ia_generar_respuesta_faltantes_pedido",
        inicio,
    )
    bloque = app[inicio:fin]

    assert (
        "preparar_respuesta_post_analisis_ml("
        in bloque
    )
    assert (
        "generar_derivacion_y_faltantes_fn=("
        in bloque
    )
    assert "generar_cta_operador_fn=(" in bloque
    assert "generar_faltantes_fn=(" in bloque
    assert (
        "resultado_preparacion.datos_completos"
        in bloque
    )
    assert (
        "texto = resultado_preparacion.texto"
        in bloque
    )
    assert (
        "if requiere_operador_actual and faltantes:"
        not in bloque
    )
    assert "elif requiere_operador_actual:" not in bloque

    posicion_preparacion = bloque.index(
        "preparar_respuesta_post_analisis_ml("
    )
    posicion_datos_completos = bloque.index(
        "procesar_datos_completos_auto_respuesta_ml("
    )
    posicion_envio = bloque.index(
        "enviar_auto_respuesta_ml("
    )

    assert (
        posicion_preparacion
        < posicion_datos_completos
        < posicion_envio
    )
