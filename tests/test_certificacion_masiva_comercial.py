from pathlib import Path

from services.certificacion_masiva_comercial import (
    campos_certificacion,
    certificar_filas,
    plantilla_certificacion,
    resumir_certificacion,
    sugerir_mapeo,
)


def encabezados():
    return [definicion["nombre"] for definicion in campos_certificacion().values()]


def fila(numero, codigo, costo, impuesto, utilidad, precio, comision, cargo, umbral, envio, promocion, descuento, real, estado):
    return {"numero": numero, "valores": [codigo, costo, impuesto, utilidad, precio, comision, cargo, umbral, envio, promocion, descuento, real, estado]}


def test_plantilla_y_automapeo_cubren_el_contrato_completo():
    nombres = encabezados(); mapeo = sugerir_mapeo(nombres)
    assert len([valor for valor in mapeo.values() if valor]) == len(nombres) == 13
    assert hasattr(plantilla_certificacion(), "read")


def test_lote_detecta_piso_promocion_y_pago_parcial():
    filas = [
        fila(2, "PROMO", 820, 5, 20, 1000, 15, 0, 33000, 0, "SI", 9.09, 850, "confirmada"),
        fila(3, "ENVIO", 26000, 5, 25, 42000, 15, 1430, 33000, 6500, "NO", 0, 28000, "confirmada"),
    ]
    vista = certificar_filas(filas, sugerir_mapeo(encabezados()))
    assert vista[0]["resultado"]["accion_propuesta"] == "cancelar_promocion_y_actualizar_precio"
    assert vista[1]["resultado"]["estado_conciliacion"] == "pago_parcial"
    resumen = resumir_certificacion(vista)
    assert resumen["bajo_piso"] == 2 and resumen["cancelar_promocion"] == 1
    assert resumen["certificacion"] == "no_apta"


def test_escenario_correcto_resulta_apto():
    filas = [fila(2, "OK", 1000, 0, 10, 1500, 10, 0, 33000, 0, "NO", 0, 1350, "confirmada")]
    vista = certificar_filas(filas, sugerir_mapeo(encabezados()))
    assert vista[0]["estado"] == "apto"
    assert resumir_certificacion(vista)["certificacion"] == "apta"


def test_error_de_fila_no_detiene_el_resto_del_lote():
    filas = [
        fila(2, "MAL", "texto", 0, 10, 1500, 10, 0, 33000, 0, "NO", 0, 1350, "confirmada"),
        fila(3, "OK", 1000, 0, 10, 1500, 10, 0, 33000, 0, "NO", 0, 1350, "confirmada"),
    ]
    vista = certificar_filas(filas, sugerir_mapeo(encabezados()))
    assert [item["estado"] for item in vista] == ["error", "apto"]
    assert resumir_certificacion(vista)["errores"] == 1


def test_rutas_ofrecen_plantilla_vista_previa_y_exportacion():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_certificacion_masiva_comercial.html").read_text(encoding="utf-8")
    assert "/admin/comercial/certificacion-masiva" in rutas
    assert "plantilla_certificacion_masiva" in rutas
    assert "certificacion_comercial.xlsx" in rutas
    assert "Automapeo aplicado" in panel and "ninguna se ejecuta" in panel


def test_certificacion_es_generica_en_memoria_y_sin_conectores():
    servicio = Path("services/certificacion_masiva_comercial.py").read_text(encoding="utf-8").lower()
    for prohibido in ("db.session", "requests", "oauth", "webhook", "access_token", "mercadopago", "mercadolibre", "tiendanube"):
        assert prohibido not in servicio
