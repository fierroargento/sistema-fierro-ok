"""Consultas del panel comercial tenant."""

from services.catalogo_ficha_integral import (
    calcular_completitud,
    cargar_json,
    numero_visual,
    presentar_atributos,
    presentar_variantes,
)
from services.reglas_economicas import calcular_pisos_regla, resolver_regla_vigente


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
        "items": Item.query.join(Lista).filter(
            Lista.organizacion_id == organizacion_id
            , Lista.unidad_negocio_id == unidad_negocio_id
        ).order_by(Item.fecha_creacion.desc()).all(),
        "reglas_economicas": reglas_economicas,
        "pisos_economicos": pisos_economicos,
    }
