"""Consultas del panel comercial tenant."""


def obtener_datos_panel_comercial(organizacion_id, *, modelos):
    Unidad = modelos["UnidadNegocio"]
    CatalogoProducto = modelos["CatalogoProducto"]
    Costo = modelos["CostoProductoVersion"]
    Lista = modelos["ListaPrecio"]
    Politica = modelos["PoliticaComercialLista"]
    Item = modelos["ListaPrecioItem"]
    inclusiones = CatalogoProducto.query.join(
        modelos["Catalogo"]
    ).filter(
        modelos["Catalogo"].organizacion_id == organizacion_id
    ).order_by(CatalogoProducto.nombre_comercial).all()
    return {
        "unidades": Unidad.query.filter_by(
            organizacion_id=organizacion_id, activa=True
        ).order_by(Unidad.nombre).all(),
        "inclusiones": inclusiones,
        "costos": Costo.query.filter_by(
            organizacion_id=organizacion_id
        ).order_by(Costo.fecha_creacion.desc()).all(),
        "listas": Lista.query.filter_by(
            organizacion_id=organizacion_id
        ).order_by(Lista.nombre).all(),
        "politicas": Politica.query.join(Lista).filter(
            Lista.organizacion_id == organizacion_id
        ).order_by(Politica.fecha_creacion.desc()).all(),
        "items": Item.query.join(Lista).filter(
            Lista.organizacion_id == organizacion_id
        ).order_by(Item.fecha_creacion.desc()).all(),
    }
