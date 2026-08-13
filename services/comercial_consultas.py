"""Consultas del panel comercial tenant."""

from services.catalogo_ficha_integral import (
    cargar_json,
    numero_visual,
    presentar_atributos,
    presentar_variantes,
)


def obtener_datos_panel_comercial(organizacion_id, unidad_negocio_id, *, modelos):
    Unidad = modelos["UnidadNegocio"]
    Producto = modelos["Producto"]
    Catalogo = modelos["Catalogo"]
    CatalogoProducto = modelos["CatalogoProducto"]
    Costo = modelos["CostoProductoVersion"]
    Lista = modelos["ListaPrecio"]
    Politica = modelos["PoliticaComercialLista"]
    Item = modelos["ListaPrecioItem"]
    inclusiones = CatalogoProducto.query.join(
        Catalogo
    ).filter(
        Catalogo.organizacion_id == organizacion_id
        , Catalogo.unidad_negocio_id == unidad_negocio_id
    ).order_by(CatalogoProducto.nombre_comercial).all()
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
        "costos": Costo.query.filter_by(
            organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id
        ).order_by(Costo.fecha_creacion.desc()).all(),
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
    }
