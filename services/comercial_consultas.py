"""Consultas del panel comercial tenant."""

from services.catalogo_ficha_integral import (
    calcular_completitud,
    cargar_json,
    numero_visual,
    presentar_atributos,
    presentar_variantes,
)
from services.reglas_economicas import calcular_pisos_regla, resolver_regla_vigente
from services.motor_comercial_canal import calcular_precio_minimo_canal
from services.control_comercial_masivo import construir_bandeja


def obtener_datos_panel_comercial(organizacion_id, unidad_negocio_id, *, modelos):
    Unidad = modelos["UnidadNegocio"]
    Producto = modelos["Producto"]
    Catalogo = modelos["Catalogo"]
    CatalogoProducto = modelos["CatalogoProducto"]
    Costo = modelos["CostoProductoVersion"]
    Lista = modelos["ListaPrecio"]
    Politica = modelos["PoliticaComercialLista"]
    Item = modelos["ListaPrecioItem"]
    ReglaEconomica = modelos["ReglaEconomicaVersion"]
    ReglaCanal = modelos["ReglaCanalVersion"]
    inclusiones = CatalogoProducto.query.join(
        Catalogo
    ).filter(
        Catalogo.organizacion_id == organizacion_id
        , Catalogo.unidad_negocio_id == unidad_negocio_id
    ).order_by(CatalogoProducto.nombre_comercial).all()
    for inclusion in inclusiones:
        porcentaje, faltantes = calcular_completitud(
            inclusion, inclusion.producto
        )
        inclusion.completitud_visual = porcentaje
        inclusion.faltantes_visual = ", ".join(faltantes) or None
    costos = Costo.query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id
    ).order_by(Costo.fecha_creacion.desc()).all()
    reglas_economicas = ReglaEconomica.query.filter(
        ReglaEconomica.organizacion_id == organizacion_id,
        (ReglaEconomica.unidad_negocio_id.is_(None))
        | (ReglaEconomica.unidad_negocio_id == unidad_negocio_id),
    ).order_by(ReglaEconomica.fecha_creacion.desc()).all()
    pisos_economicos = []
    for costo in (item for item in costos if item.vigente):
        inclusion = next(
            (item for item in inclusiones if item.producto_id == costo.producto_id),
            None,
        )
        regla = resolver_regla_vigente(
            reglas_economicas, unidad_negocio_id=unidad_negocio_id,
            catalogo_id=inclusion.catalogo_id if inclusion else None,
            producto_id=costo.producto_id,
        )
        pisos_economicos.append({
            "costo": costo, "inclusion": inclusion, "regla": regla,
            "pisos": calcular_pisos_regla(costo.costo_total_centavos, regla)
            if regla else None,
        })
    reglas_canal = ReglaCanal.query.join(Lista).filter(
        Lista.organizacion_id == organizacion_id,
        Lista.unidad_negocio_id == unidad_negocio_id,
    ).order_by(ReglaCanal.fecha_creacion.desc()).all()
    simulaciones_canal = []
    for fila in (item for item in pisos_economicos if item["pisos"]):
        for regla_canal in (item for item in reglas_canal if item.vigente):
            simulaciones_canal.append({
                **fila, "regla_canal": regla_canal,
                "minimo": calcular_precio_minimo_canal(
                    fila["pisos"]["minimo"]["piso_liquidacion_centavos"], regla_canal,
                ),
                "objetivo": calcular_precio_minimo_canal(
                    fila["pisos"]["objetivo"]["piso_liquidacion_centavos"], regla_canal,
                ),
            })
    items = Item.query.join(Lista).filter(
        Lista.organizacion_id == organizacion_id,
        Lista.unidad_negocio_id == unidad_negocio_id,
    ).order_by(Item.fecha_creacion.desc()).all()
    control_comercial, resumen_control_comercial = construir_bandeja(
        simulaciones_canal, items,
    )
    return {
        "productos_maestro": Producto.query.order_by(
            Producto.sku.asc()
        ).all(),
        "catalogos": Catalogo.query.filter_by(
            organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id
        ).order_by(Catalogo.nombre.asc()).all(),
        "inclusiones": inclusiones,
        "productos_relacionables": inclusiones,
        "catalogo_json": cargar_json,
        "catalogo_numero": numero_visual,
        "presentar_atributos": presentar_atributos,
        "presentar_variantes": presentar_variantes,
        "inclusiones_activas": [
            inclusion for inclusion in inclusiones if inclusion.activo
        ],
        "costos": costos,
        "listas": Lista.query.filter_by(
            organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id
        ).order_by(Lista.nombre).all(),
        "politicas": Politica.query.join(Lista).filter(
            Lista.organizacion_id == organizacion_id
            , Lista.unidad_negocio_id == unidad_negocio_id
        ).order_by(Politica.fecha_creacion.desc()).all(),
        "items": items,
        "reglas_economicas": reglas_economicas,
        "pisos_economicos": pisos_economicos,
        "reglas_canal": reglas_canal,
        "simulaciones_canal": simulaciones_canal,
        "control_comercial": control_comercial,
        "resumen_control_comercial": resumen_control_comercial,
    }
