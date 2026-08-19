import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from services.inventario_eventos_canal import (
    cargar_sobre_persistido,
    diagnosticar_eventos_persistidos,
)


def _evento(contenido, **cambios):
    serializado = json.dumps(
        contenido, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    datos = {
        "id": 9,
        "contrato_json": serializado,
        "payload_hash": hashlib.sha256(serializado.encode("utf-8")).hexdigest(),
        "clave_idempotencia": "org:3:tienda_nube:7:evento:55",
        "estado": "preparado_sin_conexion",
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def _contenido():
    return {
        "organizacion_id": 3,
        "pedido_id": 1204,
        "cuenta_tipo": "tienda_nube",
        "cuenta_id": 7,
        "evento_externo_id": "55",
        "contrato": {
            "version": 1,
            "canal": "tienda_nube",
            "referencia": "TN-55",
            "tipo_evento": "reservar",
            "cantidades": {"PP6040H": 1},
            "parcial": False,
            "estado_origen": "paid",
            "requiere_revision": False,
            "modo": "desconectado",
        },
    }


def test_reconstruccion_verifica_integridad_del_contrato():
    evento = _evento(_contenido())
    sobre = cargar_sobre_persistido(evento)
    assert sobre["pedido_id"] == 1204
    assert sobre["contrato"]["cantidades"] == {"PP6040H": 1}
    evento.payload_hash = "alterado"
    try:
        cargar_sobre_persistido(evento)
        assert False, "Debio rechazar una huella alterada"
    except ValueError as error:
        assert "huella" in str(error)


def test_diagnostico_resume_bloqueos_sin_mutar_evento():
    evento = _evento(_contenido())
    diagnosticos, resumen = diagnosticar_eventos_persistidos(
        [evento],
        configuracion=SimpleNamespace(estado="desactivado"),
        vinculos=[],
        items_inventario=[],
        existencias=[],
        reservas=[],
    )
    assert diagnosticos[9]["estado"] == "bloqueado"
    assert diagnosticos[9]["puede_ejecutar"] is False
    assert resumen == {
        "total": 1,
        "listos": 0,
        "bloqueados": 1,
        "revision_manual": 0,
        "invalidos": 0,
    }
    assert evento.estado == "preparado_sin_conexion"


def test_contrato_corrupto_se_informa_y_no_rompe_el_panel():
    evento = _evento(_contenido(), contrato_json="{", payload_hash="x")
    diagnosticos, resumen = diagnosticar_eventos_persistidos(
        [evento],
        configuracion=None,
        vinculos=[],
        items_inventario=[],
        existencias=[],
    )
    assert diagnosticos[9]["estado"] == "invalido"
    assert resumen["invalidos"] == 1


def test_panel_muestra_resumen_y_diagnostico_sin_accion_productiva():
    panel = Path("templates/admin_inventario.html").read_text(encoding="utf-8")
    servicio = Path("services/inventario_eventos_canal.py").read_text(
        encoding="utf-8"
    )
    assert "listos sin ejecutar" in panel
    assert "Diagnóstico actual" in panel
    assert "diagnosticar_eventos_persistidos" in servicio
    assert "db_session" not in servicio.split(
        "def diagnosticar_eventos_persistidos", 1
    )[1]
