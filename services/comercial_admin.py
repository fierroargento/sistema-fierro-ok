"""Acciones del panel comercial interno."""

from services.catalogos_comerciales import importe_a_centavos
from services.catalogos_admin_comercial import procesar_accion_catalogo_comercial
from services.costos_productos import crear_version_costo, activar_version_costo
from services.aprobacion_costos import validar_version_preparatoria
from services.reglas_economicas import activar_regla, crear_regla
from services.reglas_canal import activar_regla_canal, agregar_tramo, crear_regla_canal
from services.promociones_canal import registrar_observacion
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
    archivos=None,
):
    if accion in {
        "crear_catalogo", "estado_catalogo", "agregar_producto_catalogo",
        "activar_producto_catalogo", "disponibilidad_producto_catalogo",
        "gestionar_producto_catalogo",
    }:
        return procesar_accion_catalogo_comercial(
            accion, formulario, organizacion=organizacion,
            unidad_activa=unidad_activa, modelos=modelos, db_session=db_session,
            archivos=archivos,
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
        perfil = modelos["PerfilCosteoProducto"].query.filter_by(
            organizacion_id=organizacion.id,
            unidad_negocio_id=unidad_activa.id,
            producto_id=costo.producto_id if costo else None,
            activo=True,
        ).first()
        validar_version_preparatoria(
            perfil, costo,
            CostoProductoVersion=modelos["CostoProductoVersion"],
        )
        activar_version_costo(
            costo, CostoProductoVersion=modelos["CostoProductoVersion"],
            db_session=db_session,
        )
        return "Costo activado."
    if accion == "crear_regla_economica":
        alcance = str(formulario.get("alcance") or "").strip().lower()
        unidad_id = unidad_activa.id if alcance in {"unidad", "catalogo", "producto"} else None
        catalogo_id = None
        producto_id = None
        if alcance == "catalogo":
            catalogo = modelos["Catalogo"].query.filter_by(
                id=_id(formulario, "catalogo_id"),
                organizacion_id=organizacion.id,
                unidad_negocio_id=unidad_activa.id,
            ).first()
            if catalogo is None:
                raise ValueError("El catálogo no pertenece a la unidad activa.")
            catalogo_id = catalogo.id
        if alcance == "producto":
            inclusion = modelos["CatalogoProducto"].query.get(
                _id(formulario, "catalogo_producto_id")
            )
            if (
                inclusion is None
                or inclusion.catalogo.organizacion_id != organizacion.id
                or inclusion.catalogo.unidad_negocio_id != unidad_activa.id
            ):
                raise ValueError("El producto no pertenece a la unidad activa.")
            producto_id = inclusion.producto_id
        regla = crear_regla(
            organizacion_id=organizacion.id, unidad_negocio_id=unidad_id,
            catalogo_id=catalogo_id, producto_id=producto_id,
            alcance=alcance, nombre=formulario.get("nombre"),
            impuesto_pct=formulario.get("impuesto_pct", 0),
            metodo_impuesto=formulario.get("metodo_impuesto"),
            utilidad_minima_pct=formulario.get("utilidad_minima_pct", 0),
            utilidad_objetivo_pct=formulario.get("utilidad_objetivo_pct", 0),
            metodo_utilidad=formulario.get("metodo_utilidad"),
            incremento_redondeo_centavos=importe_a_centavos(
                formulario.get("redondeo", "0.01")
            ),
            observacion=formulario.get("observacion"), usuario=usuario,
            ReglaEconomicaVersion=modelos["ReglaEconomicaVersion"],
            db_session=db_session,
        )
        return f"Regla económica {regla.nombre} creada como preparatoria."
    if accion == "activar_regla_economica":
        regla = modelos["ReglaEconomicaVersion"].query.filter_by(
            id=_id(formulario, "regla_id"), organizacion_id=organizacion.id,
        ).first()
        if regla is None or regla.unidad_negocio_id not in {None, unidad_activa.id}:
            raise ValueError("La regla no pertenece a la unidad activa.")
        activar_regla(
            regla, ReglaEconomicaVersion=modelos["ReglaEconomicaVersion"],
            db_session=db_session,
        )
        return "Regla económica activada."
    if accion in {"crear_regla_canal", "agregar_tramo_canal", "activar_regla_canal"}:
        lista = modelos["ListaPrecio"].query.filter_by(
            id=_id(formulario, "lista_precio_id"), organizacion_id=organizacion.id,
            unidad_negocio_id=unidad_activa.id,
        ).first()
        if lista is None: raise ValueError("La lista no pertenece a la unidad activa.")
        if accion == "crear_regla_canal":
            regla = crear_regla_canal(
                lista, nombre=formulario.get("nombre"), comision_pct=formulario.get("comision_pct", 0),
                umbral_envio_centavos=importe_a_centavos(formulario.get("umbral_envio", 0)),
                costo_envio_default_centavos=importe_a_centavos(formulario.get("costo_envio", 0)),
                incremento_redondeo_centavos=importe_a_centavos(formulario.get("redondeo", "0.01")),
                observacion=formulario.get("observacion"), usuario=usuario,
                ReglaCanalVersion=modelos["ReglaCanalVersion"], db_session=db_session,
            )
            return f"Política de canal {regla.nombre} creada como preparatoria."
        regla = modelos["ReglaCanalVersion"].query.filter_by(id=_id(formulario, "regla_canal_id"), lista_precio_id=lista.id).first()
        if regla is None: raise ValueError("La política no pertenece a la lista.")
        if accion == "agregar_tramo_canal":
            agregar_tramo(
                regla, precio_desde_centavos=importe_a_centavos(formulario.get("precio_desde", 0)),
                precio_hasta_centavos=importe_a_centavos(formulario.get("precio_hasta")) if str(formulario.get("precio_hasta") or "").strip() else None,
                cargo_fijo_centavos=importe_a_centavos(formulario.get("cargo_fijo", 0)),
                ReglaCanalCargoTramo=modelos["ReglaCanalCargoTramo"], db_session=db_session,
            )
            return "Tramo de cargo fijo agregado."
        activar_regla_canal(regla, ReglaCanalVersion=modelos["ReglaCanalVersion"], db_session=db_session)
        return "Política de canal activada."
    if accion == "registrar_promocion_canal":
        lista = modelos["ListaPrecio"].query.filter_by(
            id=_id(formulario, "lista_precio_id"), organizacion_id=organizacion.id,
            unidad_negocio_id=unidad_activa.id,
        ).first()
        inclusion = modelos["CatalogoProducto"].query.get(
            _id(formulario, "catalogo_producto_id")
        )
        if lista is None: raise ValueError("La lista no pertenece a la unidad activa.")
        if (
            inclusion is None
            or inclusion.catalogo.organizacion_id != organizacion.id
            or inclusion.catalogo.unidad_negocio_id != unidad_activa.id
        ): raise ValueError("El producto no pertenece a la unidad activa.")
        registro = registrar_observacion(
            organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id,
            lista_precio_id=lista.id, catalogo_producto_id=inclusion.id,
            referencia_externa=formulario.get("referencia_externa"),
            nombre=formulario.get("nombre_promocion"),
            precio_base_centavos=importe_a_centavos(formulario.get("precio_base")),
            precio_promocional_centavos=importe_a_centavos(formulario.get("precio_promocional")),
            estado_observado=formulario.get("estado_observado"), origen="manual",
            observacion=formulario.get("observacion"), usuario=usuario,
            PromocionCanalObservacion=modelos["PromocionCanalObservacion"],
            db_session=db_session,
        )
        return f"Promoción observada registrada como {registro.estado_observado}."
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
