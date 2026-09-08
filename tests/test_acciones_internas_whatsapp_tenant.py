from pathlib import Path
from types import SimpleNamespace

from modules.whatsapp import runtime


class SessionFake:
    def __init__(self):
        self.agregados = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, objeto):
        self.agregados.append(objeto)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class MensajeFake:
    def __init__(self, **campos):
        self.__dict__.update(campos)


def _registrar(pedido, organizacion_id=None):
    sesion = SessionFake()
    resultado = runtime.registrar_whatsapp_mensaje_service(
        MensajeFake,
        lambda *_args, **_kwargs: None,
        lambda **_kwargs: None,
        SimpleNamespace(query=None),
        SimpleNamespace(session=sesion),
        pedido=pedido,
        telefono="2920123456",
        direccion="in",
        texto="Prueba",
        organizacion_id=organizacion_id,
    )
    return resultado, sesion


def test_registro_hereda_organizacion_y_unidad_del_pedido():
    pedido = SimpleNamespace(
        id=1, telefono="2920123456", organizacion_id=10,
        unidad_negocio_id=100, wa_ultimo_contacto=None,
    )
    mensaje, sesion = _registrar(pedido)
    assert mensaje.organizacion_id == 10
    assert mensaje.unidad_negocio_id == 100
    assert sesion.commits == 1


def test_registro_rechaza_organizacion_contradictoria():
    pedido = SimpleNamespace(
        id=1, telefono="2920123456", organizacion_id=10,
        unidad_negocio_id=100, wa_ultimo_contacto=None,
    )
    mensaje, sesion = _registrar(pedido, organizacion_id=20)
    assert mensaje is None
    assert sesion.commits == 0
    assert sesion.rollbacks == 1


def test_ownership_busca_historial_en_el_tenant_del_pedido():
    texto = Path("services/canal_manager.py").read_text(encoding="utf-8")
    bloque = texto.split("def pedido_puede_reencauzarse_a_ml(", 1)[1].split(
        "def devolver_conversacion_a_ml(", 1
    )[0]
    assert "pedido_id=pedido.id" in bloque
    assert "organizacion_id=pedido.organizacion_id" in bloque


def test_acciones_de_bandeja_usan_consulta_tenant():
    rutas = Path("modules/whatsapp/general_routes.py").read_text(encoding="utf-8")
    assert rutas.count("consulta_whatsapp_tenant(") == 3
    assert 'error": "sin_tenant"' in rutas


def test_lote_no_contiene_transporte_ni_webhook():
    auditoria = Path("services/auditoria_consumidores_whatsapp.py").read_text(
        encoding="utf-8"
    ).lower()
    assert "requests." not in auditoria
    assert "db.session" not in auditoria
