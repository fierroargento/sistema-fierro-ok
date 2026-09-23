from types import SimpleNamespace

from services.edicion_datos_cliente import (
    aplicar_edicion_datos_cliente_para_etiqueta,
    puede_editar_datos_cliente_para_etiqueta,
)


def pedido(**cambios):
    base = {
        "estado": "Cargando Pedido",
        "organizacion_id": 7,
        "unidad_negocio_id": 9,
        "fecha_etiqueta_impresa": None,
        "cliente": "Alias ML",
        "dni": "",
        "telefono": "",
        "mail": "",
        "direccion": "",
        "localidad": "",
        "provincia": "",
        "codigo_postal": "",
        "sucursal_nombre": "",
        "autorizado_nombre": "",
        "autorizado_dni": "",
        "autorizado_telefono": "",
        "ml_nombre_real": False,
    }
    base.update(cambios)
    return SimpleNamespace(**base)


def test_carga_puede_corregir_antes_de_imprimir():
    assert puede_editar_datos_cliente_para_etiqueta(
        pedido(estado="Etiqueta Lista"), rol="carga"
    ) is True


def test_no_puede_corregir_despues_de_imprimir():
    assert puede_editar_datos_cliente_para_etiqueta(
        pedido(estado="Etiqueta Impresa"), rol="carga"
    ) is False


def test_despacho_no_puede_corregir():
    assert puede_editar_datos_cliente_para_etiqueta(
        pedido(), rol="despacho"
    ) is False


def test_solo_aplica_campos_permitidos():
    actual = pedido()
    resultado = aplicar_edicion_datos_cliente_para_etiqueta(
        actual,
        {
            "cliente": "Sebastián Vacaflor",
            "dni": "27979807",
            "estado": "Finalizado",
            "canal": "Presencial",
            "id_venta": "ALTERADO",
        },
        rol="carga",
        organizacion_id=7,
        unidad_negocio_id=9,
        normalizar_telefono_fn=lambda valor: valor,
    )

    assert resultado.permitida is True
    assert actual.cliente == "Sebastián Vacaflor"
    assert actual.dni == "27979807"
    assert actual.estado == "Cargando Pedido"
    assert not hasattr(actual, "canal")
    assert actual.ml_nombre_real is True
    assert resultado.cambios == ("cliente", "dni")


def test_edicion_rechaza_otro_tenant_y_textos_fuera_de_modelo():
    actual = pedido()
    cruzado = aplicar_edicion_datos_cliente_para_etiqueta(
        actual,
        {"cliente": "Intrusión"},
        rol="carga",
        organizacion_id=8,
        unidad_negocio_id=9,
        normalizar_telefono_fn=lambda valor: valor,
    )
    assert cruzado.permitida is False
    assert cruzado.motivo == "pedido_fuera_del_contexto_activo"
    assert actual.cliente == "Alias ML"

    largo = aplicar_edicion_datos_cliente_para_etiqueta(
        actual,
        {"codigo_postal": "1" * 11},
        rol="carga",
        organizacion_id=7,
        unidad_negocio_id=9,
        normalizar_telefono_fn=lambda valor: valor,
    )
    assert largo.permitida is False
    assert largo.motivo == "campo_demasiado_largo:codigo_postal"
