"""Acciones del panel comercial interno."""

from services.catalogos_comerciales import importe_a_centavos
from services.catalogos_admin_comercial import procesar_accion_catalogo_comercial
from services.costos_productos import crear_version_costo, activar_version_costo
from services.listas_precios import (
    activar_item_lista, activar_politica_lista, crear_item_lista,
    crear_lista_precio, crear_politica_lista,
)


def _id(formulario, campo, opcional=False):
    valor = str(formulario.get(campo) or "").strip()
    if opcional and not valor:
        return None
    if not valor.isdigit():
        raise ValueError(f"{campo} no es valido.")
    return int(valor)


def procesar_accion_comercial(
    accion, formulario, *, organizacion, unidad_activa, modelos, db_session, usuario,
):
    if accion in {
        "crear_catalogo", "estado_catalogo", "agregar_producto_catalogo",
        "activar_producto_catalogo", "disponibilidad_producto_catalogo",
        "gestionar_producto_catalogo",
    }:
        return procesar_accion_catalogo_comercial(
            accion, formulario, organizacion=organizacion,
            unidad_activa=unidad_activa, modelos=modelos, db_session=db_session,
        )
    if accion == "crear_costo_manual":
        inclusion = modelos["CatalogoProducto"].query.get(
            _id(formulario, "catalogo_producto_id")
        )
        if inclusion is None or inclusion.catalogo.organizacion_id != organizacion.id:
            raise ValueError("El producto no pertenece a la organizacion.")
        if inclusion.catalogo.unidad_negocio_id != unidad_activa.id:
            raise ValueError("El producto no pertenece a la unidad activa.")
        if not inclusion.activo:
            raise ValueError("Primero activá el producto en su catálogo.")
        unidad_id = inclusion.catalogo.unidad_negocio_id
        version = crear_version_costo(
            organizacion_id=organizacion.id, unidad_negocio_id=unidad_id,
            producto_id=inclusion.producto_id, moneda=inclusion.catalogo.moneda,
            tipo="manual", detalles=[{
                "tipo": "elaboracion", "concepto": "Costo base manual",
                "cantidad": "1", "unidad_medida": "unidad",
                "costo_unitario_centavos": importe_a_centavos(
                    formulario.get("costo_base")
                ), "orden": 0,
            }], creado_por_usuario_id=getattr(usuario, "id", None),
            creado_por_username=getattr(usuario, "username", None),
            Organizacion=modelos["Organizacion"],
            UnidadNegocio=modelos["UnidadNegocio"], Producto=modelos["Producto"],
            CostoProductoVersion=modelos["CostoProductoVersion"],
            CostoProductoDetalle=modelos["CostoProductoDetalle"],
            db_session=db_session,
        )
        return f"Costo version {version.numero_version} creado."
    if accion == "activar_costo":
        costo = modelos["CostoProductoVersion"].query.filter_by(
            id=_id(formulario, "costo_id"), organizacion_id=organizacion.id,
            unidad_negocio_id=unidad_activa.id,
        ).first()
        activar_version_costo(
            costo, CostoProductoVersion=modelos["CostoProductoVersion"],
            db_session=db_session,
        )
        return "Costo activado."
    if accion == "crear_lista":
        lista = crear_lista_precio(
            organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id,
            codigo=formulario.get("codigo"), nombre=formulario.get("nombre"),
            tipo=formulario.get("tipo"), moneda=formulario.get("moneda", "ARS"),
            Organizacion=modelos["Organizacion"],
            UnidadNegocio=modelos["UnidadNegocio"], ListaPrecio=modelos["ListaPrecio"],
            db_session=db_session, creado_por_usuario_id=getattr(usuario, "id", None),
            creado_por_username=getattr(usuario, "username", None),
        )
        return f"Lista {lista.nombre} creada."
    lista = modelos["ListaPrecio"].query.filter_by(
        id=_id(formulario, "lista_precio_id"), organizacion_id=organizacion.id,
        unidad_negocio_id=unidad_activa.id,
    ).first()
    if lista is None:
        raise ValueError("La lista no pertenece a la organizacion.")
    if accion == "crear_politica":
        politica = crear_politica_lista(
            lista, comision_pct=formulario.get("comision_pct", 0),
            cargo_fijo_centavos=importe_a_centavos(formulario.get("cargo_fijo", 0)),
            flete_venta_centavos=importe_a_centavos(formulario.get("flete_venta", 0)),
            margen_objetivo_pct=formulario.get("margen_pct", 0),
            incremento_redondeo_centavos=importe_a_centavos(
                formulario.get("redondeo", "0.01")
            ), PoliticaComercialLista=modelos["PoliticaComercialLista"],
            db_session=db_session,
        )
        return f"Politica version {politica.numero_version} creada."
    if accion == "activar_politica":
        politica = modelos["PoliticaComercialLista"].query.get(
            _id(formulario, "politica_id")
        )
        if politica is None or politica.lista_precio_id != lista.id:
            raise ValueError("La politica no pertenece a la lista.")
        activar_politica_lista(
            politica, PoliticaComercialLista=modelos["PoliticaComercialLista"],
            db_session=db_session,
        )
        return "Politica activada."
    if accion == "crear_precio":
        inclusion = modelos["CatalogoProducto"].query.get(
            _id(formulario, "catalogo_producto_id")
        )
        if (
            inclusion is None
            or inclusion.catalogo.organizacion_id != organizacion.id
            or inclusion.catalogo.unidad_negocio_id != unidad_activa.id
            or not inclusion.activo
        ):
            raise ValueError("El producto de catálogo no está activo.")
        costo = modelos["CostoProductoVersion"].query.filter_by(
            id=_id(formulario, "costo_id"), organizacion_id=organizacion.id,
            unidad_negocio_id=unidad_activa.id,
            vigente=True,
        ).first()
        politica = modelos["PoliticaComercialLista"].query.filter_by(
            id=_id(formulario, "politica_id"), lista_precio_id=lista.id,
            vigente=True,
        ).first()
        elegido = str(formulario.get("precio_elegido") or "").strip()
        item = crear_item_lista(
            lista=lista, catalogo_producto=inclusion,
            costo_version=costo, politica=politica,
            impuesto_pct=formulario.get("impuesto_pct", 0),
            precio_elegido_centavos=(
                importe_a_centavos(elegido) if elegido else None
            ), ListaPrecioItem=modelos["ListaPrecioItem"],
            db_session=db_session,
        )
        return f"Precio version {item.numero_version} creado."
    if accion == "activar_precio":
        item = modelos["ListaPrecioItem"].query.get(
            _id(formulario, "item_id")
        )
        if item is None or item.lista_precio_id != lista.id:
            raise ValueError("El precio no pertenece a la lista.")
        activar_item_lista(
            item, ListaPrecioItem=modelos["ListaPrecioItem"],
            db_session=db_session,
        )
        return "Precio activado."
    raise ValueError("Accion comercial no reconocida.")
