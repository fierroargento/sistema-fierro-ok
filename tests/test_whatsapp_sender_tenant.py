import ast
import json
from pathlib import Path
from types import SimpleNamespace

from modules.whatsapp import sender


PAYLOAD = {
    "messaging_product": "whatsapp",
    "to": "5492920123456",
    "type": "text",
    "text": {"body": "prueba"},
}


def test_modo_desconectado_bloquea_antes_de_resolver_o_abrir_red(monkeypatch):
    llamados = []
    monkeypatch.setattr(sender, "efectos_externos_habilitados", lambda _canal: False)
    monkeypatch.setattr(
        sender, "_resolver_configuracion_envio",
        lambda **_kwargs: llamados.append("resolver"),
    )
    monkeypatch.setattr(sender, "urlopen", lambda *_args, **_kwargs: llamados.append("red"))

    ok, detalle = sender._wa_post(PAYLOAD)

    assert ok is False
    assert "modo desconectado" in detalle
    assert llamados == []


def test_efecto_sin_permiso_de_conexion_tambien_bloquea(monkeypatch):
    llamados = []
    monkeypatch.setattr(sender, "efectos_externos_habilitados", lambda _canal: True)
    monkeypatch.setattr(sender, "conexiones_externas_habilitadas", lambda _canal: False)
    monkeypatch.setattr(
        sender, "_resolver_configuracion_envio",
        lambda **_kwargs: llamados.append("resolver"),
    )
    monkeypatch.setattr(sender, "urlopen", lambda *_args, **_kwargs: llamados.append("red"))

    ok, detalle = sender._wa_post(PAYLOAD)

    assert ok is False
    assert "conexion externa no habilitada" in detalle
    assert llamados == []


def test_post_usa_url_y_token_resueltos_para_el_tenant(monkeypatch):
    capturado = {}

    class Respuesta:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"messages":[{"id":"wamid.tenant"}]}'

    def abrir(request, timeout):
        capturado["url"] = request.full_url
        capturado["authorization"] = request.headers["Authorization"]
        capturado["payload"] = json.loads(request.data.decode("utf-8"))
        capturado["timeout"] = timeout
        return Respuesta()

    monkeypatch.setattr(sender, "efectos_externos_habilitados", lambda _canal: True)
    monkeypatch.setattr(sender, "conexiones_externas_habilitadas", lambda _canal: True)
    monkeypatch.setattr(
        sender,
        "_resolver_configuracion_envio",
        lambda **kwargs: (
            capturado.update(contexto=kwargs)
            or SimpleNamespace(
                api_url="https://graph.facebook.com/v19.0/PHONE-NAUTICA/messages",
                token="token-nautica",
            )
        ),
    )
    monkeypatch.setattr(sender, "urlopen", abrir)
    pedido = SimpleNamespace(organizacion_id=2, unidad_negocio_id=20)

    ok, data = sender._wa_post(PAYLOAD, pedido=pedido)

    assert ok is True and data["messages"][0]["id"] == "wamid.tenant"
    assert capturado["contexto"]["pedido"] is pedido
    assert capturado["url"].endswith("/PHONE-NAUTICA/messages")
    assert capturado["authorization"] == "Bearer token-nautica"
    assert capturado["payload"] == PAYLOAD
    assert capturado["timeout"] == 10


def test_contexto_ausente_falla_cerrado_sin_red(monkeypatch):
    llamados = []
    monkeypatch.setattr(sender, "efectos_externos_habilitados", lambda _canal: True)
    monkeypatch.setattr(sender, "conexiones_externas_habilitadas", lambda _canal: True)
    monkeypatch.setattr(sender, "urlopen", lambda *_args, **_kwargs: llamados.append("red"))

    ok, detalle = sender._wa_post(PAYLOAD)

    assert ok is False
    assert "falta identidad" in detalle
    assert llamados == []


def test_error_de_base_al_resolver_cuenta_falla_cerrado_sin_red(monkeypatch):
    llamados = []
    monkeypatch.setattr(sender, "efectos_externos_habilitados", lambda _canal: True)
    monkeypatch.setattr(sender, "conexiones_externas_habilitadas", lambda _canal: True)
    monkeypatch.setattr(
        sender, "_resolver_configuracion_envio",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("base no disponible")),
    )
    monkeypatch.setattr(sender, "urlopen", lambda *_args, **_kwargs: llamados.append("red"))

    ok, detalle = sender._wa_post(PAYLOAD, organizacion_id=1, unidad_negocio_id=10)

    assert ok is False
    assert "no se pudo resolver" in detalle
    assert llamados == []


def test_envio_publico_propaga_pedido_hasta_frontera(monkeypatch):
    capturado = {}
    pedido = SimpleNamespace(organizacion_id=1, unidad_negocio_id=10)

    def post(payload, **kwargs):
        capturado["payload"] = payload
        capturado.update(kwargs)
        return True, {"messages": [{"id": "wamid.fierro"}]}

    monkeypatch.setattr(sender, "_wa_post", post)
    monkeypatch.setattr(sender, "_registrar_historial", lambda **_kwargs: None)

    assert sender.wa_enviar_texto(
        "5492920123456", "hola", pedido=pedido, autor="operador", registrar=False,
    ) is True
    assert capturado["pedido"] is pedido
    assert capturado["payload"]["text"]["body"] == "hola"


def test_sender_no_importa_credencial_global_legacy():
    fuente = Path("modules/whatsapp/sender.py").read_text(encoding="utf-8-sig")
    assert "WA_TOKEN" not in fuente
    assert "WA_API_URL" not in fuente
    assert "resolver_configuracion_salida_whatsapp" in fuente


def test_todos_los_consumidores_entregan_contexto_tenant():
    funciones = {
        "wa_enviar_texto", "wa_enviar_imagen", "wa_enviar_template",
        "wa_enviar_producto",
    }
    archivos = [
        *Path("modules").rglob("*.py"),
        *Path("services").rglob("*.py"),
        Path("app.py"),
    ]
    faltantes = []
    for archivo in archivos:
        arbol = ast.parse(archivo.read_text(encoding="utf-8-sig"))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            nombre = getattr(nodo.func, "id", None) or getattr(nodo.func, "attr", None)
            if nombre not in funciones:
                continue
            argumentos = {kw.arg for kw in nodo.keywords}
            if "pedido" not in argumentos and "organizacion_id" not in argumentos:
                faltantes.append(f"{archivo}:{nodo.lineno}:{nombre}")
    assert faltantes == []
