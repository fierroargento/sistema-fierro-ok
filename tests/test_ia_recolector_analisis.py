from pathlib import Path

from services.ia_recolector_analisis import (
    analizar_datos_cliente_ml_acordas,
)


def getenv_con_clave(nombre, default=""):
    if nombre == "OPENAI_API_KEY":
        return "clave-prueba"
    return default


def test_sin_api_key_devuelve_sin_configurar():
    resultado = analizar_datos_cliente_ml_acordas(
        "mensaje",
        getenv_fn=lambda _nombre, default="": default,
        chat_completion_fn=(
            lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("no debe llamar IA")
            )
        ),
    )

    assert resultado == {
        "ok": False,
        "error": "OPENAI_API_KEY no está configurada",
        "estado": "sin_configurar",
    }


def test_fusiona_datos_previos_y_resultado_ia():
    llamadas = []

    def chat(**kwargs):
        llamadas.append(kwargs)
        return '''
        {
          "datos": {
            "nombre": "Juan",
            "apellido": "Pérez",
            "telefono": "2920123456"
          },
          "resumen": "Datos parciales",
          "requiere_operador": false
        }
        '''

    resultado = analizar_datos_cliente_ml_acordas(
        "Soy Juan Pérez",
        {
            "dni": "30111222",
            "direccion": "Mitre 500",
            "localidad": "Viedma",
            "codigo_postal": "8500",
        },
        getenv_fn=getenv_con_clave,
        chat_completion_fn=chat,
        extraer_datos_clasicos_fn=(
            lambda _texto, _previos: {}
        ),
    )

    assert resultado["ok"] is True
    assert resultado["datos_completos"] is True
    assert resultado["faltantes"] == []
    assert resultado["datos"]["nombre"] == "Juan"
    assert resultado["datos"]["dni"] == "30111222"
    assert resultado["datos"]["direccion"] == "Mitre 500"

    assert len(llamadas) == 1
    assert llamadas[0]["temperatura"] == 0
    assert llamadas[0]["timeout"] == 25
    assert llamadas[0]["messages"][0]["role"] == "system"
    assert llamadas[0]["messages"][1]["role"] == "user"


def test_parser_clasico_refuerza_datos_omitidos():
    resultado = analizar_datos_cliente_ml_acordas(
        "DNI 30111222 CP 8500",
        {},
        getenv_fn=getenv_con_clave,
        chat_completion_fn=lambda **_kwargs: (
            '{"datos": {}, "resumen": ""}'
        ),
        extraer_datos_clasicos_fn=(
            lambda _texto, _previos: {
                "dni": "30111222",
                "codigo_postal": "8500",
            }
        ),
    )

    assert resultado["ok"] is True
    assert resultado["datos"]["dni"] == "30111222"
    assert resultado["datos"]["codigo_postal"] == "8500"
    assert "dni" not in resultado["faltantes"]
    assert "codigo_postal" not in resultado["faltantes"]


def test_conserva_separado_al_autorizado():
    resultado = analizar_datos_cliente_ml_acordas(
        "Retira Pedro",
        {
            "nombre": "Juan",
            "apellido": "Pérez",
        },
        getenv_fn=getenv_con_clave,
        chat_completion_fn=lambda **_kwargs: '''
        {
          "datos": {
            "autorizado_nombre": "Pedro Gómez",
            "autorizado_dni": "32111222"
          }
        }
        ''',
        extraer_datos_clasicos_fn=(
            lambda _texto, _previos: {}
        ),
    )

    assert resultado["datos"]["nombre"] == "Juan"
    assert (
        resultado["datos"]["autorizado_nombre"]
        == "Pedro Gómez"
    )
    assert (
        resultado["datos"]["autorizado_dni"]
        == "32111222"
    )


def test_json_invalido_devuelve_error_estructurado():
    resultado = analizar_datos_cliente_ml_acordas(
        "mensaje",
        {},
        getenv_fn=getenv_con_clave,
        chat_completion_fn=(
            lambda **_kwargs: "respuesta inválida"
        ),
        json_loads_fn=lambda _contenido: {},
    )

    assert resultado["ok"] is False
    assert resultado["estado"] == "error"
    assert (
        "La IA no devolvió JSON válido"
        in resultado["error"]
    )


def test_error_proveedor_devuelve_error_estructurado():
    def chat(**_kwargs):
        raise RuntimeError("proveedor caído")

    resultado = analizar_datos_cliente_ml_acordas(
        "mensaje",
        {},
        getenv_fn=getenv_con_clave,
        chat_completion_fn=chat,
    )

    assert resultado == {
        "ok": False,
        "estado": "error",
        "error": "proveedor caído",
    }


def test_servicio_no_depende_de_app_ni_tiene_efectos():
    texto = Path(
        "services/ia_recolector_analisis.py"
    ).read_text(encoding="utf-8")

    prohibidos = [
        "from app import",
        "import app",
        "db.session",
        "commit(",
        "rollback(",
        "wa_auto",
        "ml_enviar_mensaje",
        "cross_sell",
        "pedido.",
    ]

    for prohibido in prohibidos:
        assert prohibido not in texto

    assert "OPENAI_MODEL" not in texto


def test_consumidores_usan_analizador_compartido_sin_wrapper():
    app = Path("app.py").read_text(encoding="utf-8")
    flows = Path(
        "modules/whatsapp/flows.py"
    ).read_text(encoding="utf-8")

    assert (
        "def ia_analizar_datos_cliente_ml_acordas("
        not in app
    )
    assert (
        "ia_analizar_datos_cliente_ml_acordas"
        not in flows
    )

    assert app.count(
        "analizar_datos_cliente_ml_acordas("
    ) == 1
    assert flows.count(
        "analizar_datos_cliente_ml_acordas("
    ) == 1

    assert (
        "from services.ia_recolector_analisis import ("
        in app
    )
    assert (
        "from services.ia_recolector_analisis import ("
        in flows
    )
