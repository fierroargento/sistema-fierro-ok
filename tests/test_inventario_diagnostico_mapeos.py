from types import SimpleNamespace

import pytest

from services.inventario_mapeos_publicacion import (
    construir_candidato,
    diagnosticar_mapeos,
    normalizar_canal,
)


def _base():
    catalogo = SimpleNamespace(id=5, organizacion_id=1)
    producto = SimpleNamespace(id=10, catalogo_id=5, catalogo=catalogo)
    vinculo = SimpleNamespace(id=20, organizacion_id=1, catalogo_id=5, canal="mercadolibre")
    mapeo = SimpleNamespace(
        id=30, organizacion_id=1, vinculo_canal_comercial_id=20,
        catalogo_producto_id=10, canal="ml", publicacion_externa_id="MLA1",
        variante_externa_id="", sku_externo="PP6040H",
    )
    return producto, vinculo, mapeo


def test_normaliza_canales_sin_aceptar_desconocidos():
    assert normalizar_canal("ML") == "mercadolibre"
    assert normalizar_canal("tienda_nube") == "tiendanube"
    with pytest.raises(ValueError):
        normalizar_canal("otro")


def test_diagnostica_consistente_incompleto_duplicado_y_cruzado():
    producto, vinculo, mapeo = _base()
    diagnosticos, resumen = diagnosticar_mapeos(
        [mapeo], organizacion_id=1, productos=[producto], vinculos=[vinculo]
    )
    assert diagnosticos[30]["estado"] == "preparado_sin_conexion"
    assert diagnosticos[30]["permite_sincronizar"] is False
    sin_sku = SimpleNamespace(**{**vars(mapeo), "id": 31, "sku_externo": "", "publicacion_externa_id": "MLA2"})
    assert diagnosticar_mapeos([sin_sku], organizacion_id=1, productos=[producto], vinculos=[vinculo])[0][31]["estado"] == "incompleto"
    duplicado = SimpleNamespace(**{**vars(mapeo), "id": 32})
    assert diagnosticar_mapeos([mapeo, duplicado], organizacion_id=1, productos=[producto], vinculos=[vinculo])[0][32]["estado"] == "duplicado"
    cruzado = SimpleNamespace(**{**vars(mapeo), "id": 33, "canal": "tiendanube"})
    assert diagnosticar_mapeos([cruzado], organizacion_id=1, productos=[producto], vinculos=[vinculo])[0][33]["estado"] == "cruzado"


def test_candidato_no_verifica_no_sincroniza_y_no_persiste():
    candidato = construir_candidato(
        canal="TN", organizacion_id=1, vinculo_canal_comercial_id=2,
        catalogo_producto_id=3, publicacion_externa_id="100", sku_externo="SKU",
    )
    assert candidato["canal"] == "tiendanube"
    assert candidato["identidad_verificada"] is False
    assert candidato["permite_sincronizar"] is False
    assert candidato["persistir"] is False


def test_diagnostico_no_modifica_objetos():
    producto, vinculo, mapeo = _base()
    antes = vars(mapeo).copy()
    diagnosticar_mapeos([mapeo], organizacion_id=1, productos=[producto], vinculos=[vinculo])
    assert vars(mapeo) == antes
