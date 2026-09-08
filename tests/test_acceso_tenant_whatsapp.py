from pathlib import Path
from types import SimpleNamespace

import pytest

from services.acceso_tenant_whatsapp import (
    consulta_whatsapp_tenant,
    obtener_mensaje_whatsapp_tenant,
    validar_mensaje_whatsapp_en_tenant,
)


class Query:
    def __init__(self, datos):
        self.datos = list(datos)

    def filter_by(self, **filtros):
        return Query([
            item for item in self.datos
            if all(getattr(item, clave) == valor for clave, valor in filtros.items())
        ])

    def first(self):
        return self.datos[0] if self.datos else None

    def all(self):
        return list(self.datos)


class WhatsAppModelo:
    query = Query([])


def _mensajes():
    return [
        SimpleNamespace(id=1, organizacion_id=10, unidad_negocio_id=100),
        SimpleNamespace(id=2, organizacion_id=20, unidad_negocio_id=200),
        SimpleNamespace(id=3, organizacion_id=None, unidad_negocio_id=None),
    ]


def test_consulta_exige_tenant_y_excluye_otros_y_legacy():
    WhatsAppModelo.query = Query(_mensajes())
    assert [m.id for m in consulta_whatsapp_tenant(WhatsAppModelo, 10).all()] == [1]
    with pytest.raises(ValueError, match="organización"):
        consulta_whatsapp_tenant(WhatsAppModelo, None)


def test_obtencion_por_id_conserva_frontera_tenant_y_unidad():
    WhatsAppModelo.query = Query(_mensajes())
    assert obtener_mensaje_whatsapp_tenant(
        1, 10, WhatsAppMensaje=WhatsAppModelo,
    ).id == 1
    assert obtener_mensaje_whatsapp_tenant(
        2, 10, WhatsAppMensaje=WhatsAppModelo,
    ) is None
    assert obtener_mensaje_whatsapp_tenant(
        1, 10, unidad_negocio_id=101, WhatsAppMensaje=WhatsAppModelo,
    ) is None


def test_validador_rechaza_objeto_de_otro_tenant():
    with pytest.raises(ValueError, match="no pertenece"):
        validar_mensaje_whatsapp_en_tenant(_mensajes()[1], 10)


def test_guardian_no_contiene_transporte_externo():
    texto = Path("services/acceso_tenant_whatsapp.py").read_text(encoding="utf-8")
    for prohibido in ("requests", "oauth", "webhook", "access_token", "graph.facebook"):
        assert prohibido not in texto.lower()
