"""Carga individual de precios con el contrato de la importación existente."""

from services.importacion_datos_comerciales_canal import previsualizar, aplicar, campos_para


def registrar_precio_manual(datos, *, organizacion_id, unidad_negocio_id, usuario, modelos, db_session):
    Lista, Catalogo, Inclusion = (modelos[n] for n in ("ListaPrecio", "Catalogo", "CatalogoProducto"))
    Observacion = modelos["ObservacionComercialCanal"]
    lista = Lista.query.filter_by(id=int(datos.get("lista_precio_id")), organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id).first()
    inclusion = Inclusion.query.filter_by(id=int(datos.get("catalogo_producto_id"))).first()
    catalogo = Catalogo.query.filter_by(id=inclusion.catalogo_id, organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id).first() if inclusion else None
    if lista is None or catalogo is None:
        raise ValueError("El producto y la lista deben pertenecer a la unidad activa.")
    if int(datos.get("unidad_negocio_id")) != unidad_negocio_id:
        raise ValueError("Cambió la unidad activa. Cerrá y volvé a abrir el formulario.")
    anterior = Observacion.query.filter_by(organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id, lista_precio_id=lista.id, catalogo_producto_id=inclusion.id, tipo="precio").order_by(Observacion.fecha_observacion.desc(), Observacion.id.desc()).first()
    if int(datos.get("observacion_id") or 0) != (anterior.id if anterior else 0):
        raise ValueError("El precio observado cambió. Revisá el valor actual antes de guardar.")
    for campo, limite in (("cuenta_codigo", 100), ("referencia_publicacion", 160)):
        if len(str(datos.get(campo) or "").strip()) > limite:
            raise ValueError("La cuenta o referencia excede el largo permitido.")
    valores = {"lista_codigo": lista.codigo, "catalogo_codigo": catalogo.codigo, "sku_comercial": inclusion.sku_comercial, "cuenta_codigo": datos.get("cuenta_codigo"), "referencia_publicacion": datos.get("referencia_publicacion"), "precio_publicado": datos.get("precio_publicado")}
    campos = list(campos_para("precios"))
    vista = previsualizar([{"numero": 1, "valores": [valores[c] for c in campos]}], {str(i): c for i, c in enumerate(campos)}, "precios", organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id, modelos=modelos)
    fila = vista[0]
    if fila["errores"]:
        raise ValueError("; ".join(fila["errores"]))
    if fila["inclusion_id"] != inclusion.id:
        raise ValueError("La identidad del producto cambió. Revisá el catálogo.")
    if anterior and all(getattr(anterior, c) == v for c, v in fila["datos"].items()):
        return False
    aplicar(vista, "precios", organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id, lote_id=None, usuario=usuario, modelos=modelos, db_session=db_session, origen="manual")
    return True
