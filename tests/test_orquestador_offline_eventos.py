import json
from pathlib import Path

from services.orquestador_offline_eventos import orquestar_eventos


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


def evento(identificador, canal, tipo, referencia, datos, estado="validado"):
    return Obj(id=identificador, canal=canal, cuenta_codigo="CUENTA", estado=estado, payload_json=json.dumps({"version_esquema": 1, "tipo": tipo, "referencia": referencia, "datos": datos}))


def test_relaciona_venta_y_pago_entre_canales():
    venta = evento(1, "mercado_libre", "venta", "V-1:venta", {"venta_id": "V-1", "items": []})
    pago = evento(2, "mercado_pago", "pago", "P-1:pago", {"pago_id": "P-1", "venta_id": "V-1"})
    resultado = orquestar_eventos([pago, venta])
    assert resultado["resumen"]["cadenas_completas"] == 1
    assert resultado["cadenas"][0]["estado_proyectado"] == "pago_observado"
    assert resultado["propuestas"][0]["tipo"] == "conciliar_pago"


def test_detecta_pago_y_devolucion_huerfanos():
    eventos = [evento(1, "mercado_pago", "pago", "P:pago", {"venta_id": "A"}), evento(2, "mercado_pago", "devolucion", "D:devolucion", {"venta_id": "B"})]
    resultado = orquestar_eventos(eventos)
    assert {alerta["codigo"] for alerta in resultado["alertas"]} == {"pago_huerfano", "devolucion_huerfana"}


def test_detecta_publicacion_faltante_en_items():
    venta = evento(1, "tienda_nube", "venta", "V:venta", {"venta_id": "V", "items": [{"referencia_item": "PROD-1"}]})
    resultado = orquestar_eventos([venta])
    assert resultado["alertas"][0]["codigo"] == "publicacion_faltante"


def test_promocion_activa_genera_revision_no_accion():
    promocion = evento(1, "mercado_libre", "promocion", "MLA-1:promocion", {"activa": True})
    resultado = orquestar_eventos([promocion])
    assert resultado["propuestas"][0]["tipo"] == "revisar_promocion"
    assert resultado["acciones_externas"] == 0


def test_antes_y_despues_no_escribe_dominio_ni_staging():
    venta = evento(1, "mercado_libre", "venta", "V:venta", {"venta_id": "V", "items": []}, estado="recibido")
    resultado = orquestar_eventos([venta])
    assert resultado["efectos"][0] == {"evento_id": 1, "tipo": "venta", "antes": "recibido", "despues": "validado_simulado", "escritura_dominio": False}
    assert resultado["escrituras_dominio"] == 0 and venta.estado == "recibido"


def test_json_invalido_se_aisla_sin_detener_lote():
    malo = Obj(id=1, canal="otro", cuenta_codigo="C", estado="recibido", payload_json="{")
    bueno = evento(2, "mercado_libre", "venta", "V:venta", {"venta_id": "V", "items": []})
    resultado = orquestar_eventos([malo, bueno])
    assert resultado["resumen"]["errores"] == 1 and resultado["resumen"]["ventas"] == 1


def test_orquestador_no_contiene_persistencia_ni_transporte():
    servicio = Path("services/orquestador_offline_eventos.py").read_text(encoding="utf-8").lower()
    panel = Path("templates/admin_orquestador_offline.html").read_text(encoding="utf-8")
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    assert "/admin/comercial/orquestador-offline" in rutas
    assert "0 acciones externas" in panel and "0 escrituras de dominio" in panel
    for prohibido in ("db.session", "requests", "oauth", "webhook", "access_token", "http://", "https://"):
        assert prohibido not in servicio
