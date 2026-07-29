"""
Operaciones administrativas de la estructura empresarial.

Este servicio administra únicamente tablas nuevas.
No conecta sus datos con pedidos, canales ni facturación.
"""

from services.catalogos_comerciales import (
    cambiar_estado_catalogo,
    configurar_precio_catalogo,
)
from services.modulos_organizacion import (
    cambiar_estado_modulo,
)


def _texto(formulario, nombre, limite=500):
    return str(
        formulario.get(nombre)
        or ""
    ).strip()[:limite]


def _id_entero(formulario, nombre):
    valor = _texto(
        formulario,
        nombre,
        30,
    )

    try:
        resultado = int(valor)
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            f"El campo {nombre} no es válido."
        ) from error

    if resultado <= 0:
        raise ValueError(
            f"El campo {nombre} no es válido."
        )

    return resultado


def _obtener_por_id(Modelo, identificador, nombre):
    registro = Modelo.query.get(identificador)

    if registro is None:
        raise ValueError(
            f"No se encontró {nombre}."
        )

    return registro


def _guardar(db_session):
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise


def procesar_accion_estructura_admin(
    accion,
    formulario,
    *,
    organizacion,
    modelos,
    db_session,
):
    """
    Ejecuta una acción explícita del panel administrativo.

    Ninguna acción conecta estas tablas al flujo productivo.
    """
    accion = str(
        accion or ""
    ).strip().lower()

    SucursalOperativa = modelos[
        "SucursalOperativa"
    ]
    EntidadFiscal = modelos[
        "EntidadFiscal"
    ]
    Catalogo = modelos["Catalogo"]
    CatalogoProducto = modelos[
        "CatalogoProducto"
    ]
    Producto = modelos["Producto"]
    UnidadNegocio = modelos[
        "UnidadNegocio"
    ]
    ModuloOrganizacion = modelos[
        "ModuloOrganizacion"
    ]

    if accion == "crear_sucursal":
        codigo = _texto(
            formulario,
            "codigo",
            80,
        ).lower()
        nombre = _texto(
            formulario,
            "nombre",
            150,
        )

        if not codigo or not nombre:
            raise ValueError(
                "Completá código y nombre de la sucursal."
            )

        existente = (
            SucursalOperativa.query
            .filter_by(codigo=codigo)
            .first()
        )

        if existente is not None:
            raise ValueError(
                "Ya existe una sucursal con ese código."
            )

        sucursal = SucursalOperativa(
            organizacion_id=organizacion.id,
            codigo=codigo,
            nombre=nombre,
            direccion=_texto(
                formulario,
                "direccion",
                250,
            ),
            localidad=_texto(
                formulario,
                "localidad",
                120,
            ),
            provincia=_texto(
                formulario,
                "provincia",
                120,
            ),
            codigo_postal=_texto(
                formulario,
                "codigo_postal",
                20,
            ),
            es_principal=False,
            activa=False,
        )
        db_session.add(sucursal)
        _guardar(db_session)

        return (
            "Sucursal creada en estado desactivado."
        )

    if accion == "toggle_sucursal":
        sucursal = _obtener_por_id(
            SucursalOperativa,
            _id_entero(
                formulario,
                "sucursal_id",
            ),
            "la sucursal",
        )
        sucursal.activa = not bool(
            sucursal.activa
        )
        _guardar(db_session)

        estado = (
            "activada"
            if sucursal.activa
            else "desactivada"
        )
        return f"Sucursal {estado}."

    if accion == "crear_entidad_fiscal":
        codigo = _texto(
            formulario,
            "codigo",
            80,
        ).lower()
        razon_social = _texto(
            formulario,
            "razon_social",
            200,
        )
        cuit = _texto(
            formulario,
            "cuit",
            20,
        )

        if not codigo or not razon_social:
            raise ValueError(
                "Completá código y razón social."
            )

        existente = (
            EntidadFiscal.query
            .filter_by(codigo=codigo)
            .first()
        )

        if existente is not None:
            raise ValueError(
                "Ya existe una entidad fiscal "
                "con ese código."
            )

        if cuit:
            existente_cuit = (
                EntidadFiscal.query
                .filter_by(cuit=cuit)
                .first()
            )

            if existente_cuit is not None:
                raise ValueError(
                    "Ya existe una entidad fiscal "
                    "con ese CUIT."
                )

        entidad = EntidadFiscal(
            organizacion_id=organizacion.id,
            codigo=codigo,
            razon_social=razon_social,
            nombre_fantasia=_texto(
                formulario,
                "nombre_fantasia",
                200,
            ),
            cuit=cuit or None,
            condicion_iva=_texto(
                formulario,
                "condicion_iva",
                80,
            ),
            domicilio_fiscal=_texto(
                formulario,
                "domicilio_fiscal",
                300,
            ),
            punto_venta_predeterminado=(
                _texto(
                    formulario,
                    "punto_venta_predeterminado",
                    20,
                )
            ),
            activa=False,
            facturacion_habilitada=False,
        )
        db_session.add(entidad)
        _guardar(db_session)

        return (
            "Entidad fiscal creada sin habilitar "
            "facturación."
        )

    if accion == "toggle_entidad_fiscal":
        entidad = _obtener_por_id(
            EntidadFiscal,
            _id_entero(
                formulario,
                "entidad_fiscal_id",
            ),
            "la entidad fiscal",
        )

        entidad.activa = not bool(
            entidad.activa
        )

        if not entidad.activa:
            entidad.facturacion_habilitada = False

        _guardar(db_session)

        estado = (
            "activada"
            if entidad.activa
            else "desactivada"
        )
        return f"Entidad fiscal {estado}."

    if accion == "toggle_facturacion":
        entidad = _obtener_por_id(
            EntidadFiscal,
            _id_entero(
                formulario,
                "entidad_fiscal_id",
            ),
            "la entidad fiscal",
        )

        if not entidad.activa:
            raise ValueError(
                "Primero activá la entidad fiscal."
            )

        entidad.facturacion_habilitada = (
            not bool(
                entidad.facturacion_habilitada
            )
        )
        _guardar(db_session)

        estado = (
            "habilitada"
            if entidad.facturacion_habilitada
            else "deshabilitada"
        )
        return f"Facturación {estado}."

    if accion == "crear_catalogo":
        codigo = _texto(
            formulario,
            "codigo",
            80,
        ).lower()
        nombre = _texto(
            formulario,
            "nombre",
            150,
        )

        if not codigo or not nombre:
            raise ValueError(
                "Completá código y nombre del catálogo."
            )

        existente = (
            Catalogo.query
            .filter_by(codigo=codigo)
            .first()
        )

        if existente is not None:
            raise ValueError(
                "Ya existe un catálogo con ese código."
            )

        unidad_id_texto = _texto(
            formulario,
            "unidad_negocio_id",
            30,
        )
        unidad_id = None

        if unidad_id_texto:
            try:
                unidad_id = int(
                    unidad_id_texto
                )
            except ValueError as error:
                raise ValueError(
                    "La unidad de negocio no es válida."
                ) from error

            unidad = _obtener_por_id(
                UnidadNegocio,
                unidad_id,
                "la unidad de negocio",
            )

            if (
                unidad.organizacion_id
                != organizacion.id
            ):
                raise ValueError(
                    "La unidad no pertenece "
                    "a la organización."
                )

        catalogo = Catalogo(
            organizacion_id=organizacion.id,
            unidad_negocio_id=unidad_id,
            codigo=codigo,
            nombre=nombre,
            descripcion=_texto(
                formulario,
                "descripcion",
                500,
            ),
            moneda=(
                _texto(
                    formulario,
                    "moneda",
                    10,
                ).upper()
                or "ARS"
            ),
            estado="desactivado",
        )
        db_session.add(catalogo)
        _guardar(db_session)

        return (
            "Catálogo creado en estado desactivado."
        )

    if accion == "estado_catalogo":
        catalogo = _obtener_por_id(
            Catalogo,
            _id_entero(
                formulario,
                "catalogo_id",
            ),
            "el catálogo",
        )

        cambiar_estado_catalogo(
            catalogo,
            _texto(
                formulario,
                "estado",
                20,
            ),
            db_session=db_session,
        )

        return (
            "Estado del catálogo actualizado."
        )

    if accion == "agregar_producto_catalogo":
        catalogo = _obtener_por_id(
            Catalogo,
            _id_entero(
                formulario,
                "catalogo_id",
            ),
            "el catálogo",
        )
        producto = _obtener_por_id(
            Producto,
            _id_entero(
                formulario,
                "producto_id",
            ),
            "el producto",
        )

        existente = (
            CatalogoProducto.query
            .filter_by(
                catalogo_id=catalogo.id,
                producto_id=producto.id,
            )
            .first()
        )

        if existente is not None:
            raise ValueError(
                "Ese producto ya está incluido "
                "en el catálogo."
            )

        sku_comercial = (
            _texto(
                formulario,
                "sku_comercial",
                100,
            )
            or str(
                getattr(producto, "sku", "")
                or ""
            ).strip()
        )
        nombre_comercial = (
            _texto(
                formulario,
                "nombre_comercial",
                255,
            )
            or str(
                getattr(
                    producto,
                    "descripcion",
                    "",
                )
                or ""
            ).strip()
        )

        if not sku_comercial or not nombre_comercial:
            raise ValueError(
                "El producto necesita SKU "
                "y nombre comercial."
            )

        inclusion = CatalogoProducto(
            catalogo_id=catalogo.id,
            producto_id=producto.id,
            sku_comercial=sku_comercial,
            nombre_comercial=nombre_comercial,
            precio_centavos=0,
            precio_lista_centavos=None,
            disponible=False,
            activo=False,
        )

        configurar_precio_catalogo(
            inclusion,
            precio=_texto(
                formulario,
                "precio",
                50,
            ),
            precio_lista=(
                _texto(
                    formulario,
                    "precio_lista",
                    50,
                )
                or None
            ),
        )

        db_session.add(inclusion)
        _guardar(db_session)

        return (
            "Producto agregado al catálogo "
            "como inactivo y no disponible."
        )

    if accion == "toggle_producto_catalogo":
        inclusion = _obtener_por_id(
            CatalogoProducto,
            _id_entero(
                formulario,
                "catalogo_producto_id",
            ),
            "el producto del catálogo",
        )
        campo = _texto(
            formulario,
            "campo",
            30,
        )

        if campo == "activo":
            inclusion.activo = not bool(
                inclusion.activo
            )
            descripcion = (
                "Producto activado en el catálogo."
                if inclusion.activo
                else "Producto desactivado del catálogo."
            )
        elif campo == "disponible":
            inclusion.disponible = not bool(
                inclusion.disponible
            )
            descripcion = (
                "Producto marcado como disponible."
                if inclusion.disponible
                else "Producto marcado como no disponible."
            )
        else:
            raise ValueError(
                "La propiedad del producto "
                "no es válida."
            )

        _guardar(db_session)
        return descripcion

    if accion == "estado_modulo":
        modulo = _obtener_por_id(
            ModuloOrganizacion,
            _id_entero(
                formulario,
                "modulo_id",
            ),
            "el módulo",
        )

        cambiar_estado_modulo(
            modulo,
            _texto(
                formulario,
                "estado",
                20,
            ),
            detalle=_texto(
                formulario,
                "detalle",
                500,
            ),
            db_session=db_session,
        )

        return "Estado del módulo actualizado."

    raise ValueError(
        "La acción administrativa no es válida."
    )
