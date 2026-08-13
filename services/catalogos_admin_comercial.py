"""Administración tenant de catálogos para el módulo comercial interno."""

from services.catalogos_comerciales import cambiar_estado_catalogo
from services.catalogo_ficha_integral import (
    calcular_completitud,
    cargar_json,
    parsear_atributos,
    parsear_atributos_estructurados,
    parsear_canales,
    parsear_variantes,
    parsear_variantes_estructuradas,
    subir_imagenes,
    validar_relaciones,
    volcar_json,
)


ESTADOS_COMERCIALES = {"borrador", "activo", "discontinuado"}
ESTADOS_DISPONIBILIDAD = {
    "no_disponible", "disponible", "sin_stock", "pausado",
}


def _texto(formulario, campo, limite):
    return str(formulario.get(campo) or "").strip()[:limite]


def _id(formulario, campo):
    valor = _texto(formulario, campo, 30)
    if not valor.isdigit() or int(valor) <= 0:
        raise ValueError(f"{campo} no es válido.")
    return int(valor)


def _decimal_opcional(formulario, campo):
    valor = str(formulario.get(campo) or "").strip().replace(",", ".")
    if not valor:
        return None
    try:
        numero = float(valor)
    except ValueError as error:
        raise ValueError(f"{campo} no es válido.") from error
    if numero < 0:
        raise ValueError(f"{campo} no puede ser negativo.")
    return numero


def _guardar(db_session):
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise


def _catalogo_tenant(catalogo_id, organizacion, Catalogo):
    catalogo = Catalogo.query.filter_by(
        id=catalogo_id,
        organizacion_id=organizacion.id,
    ).first()
    if catalogo is None:
        raise ValueError("El catálogo no pertenece a la organización.")
    return catalogo


def procesar_accion_catalogo_comercial(
    accion,
    formulario,
    *,
    organizacion,
    unidad_activa,
    modelos,
    db_session,
    archivos=None,
):
    """Muta únicamente Catalogo y CatalogoProducto del tenant activo."""
    Catalogo = modelos["Catalogo"]
    CatalogoProducto = modelos["CatalogoProducto"]
    Producto = modelos["Producto"]
    UnidadNegocio = modelos["UnidadNegocio"]

    if accion == "crear_catalogo":
        codigo = _texto(formulario, "codigo_catalogo", 80).lower()
        nombre = _texto(formulario, "nombre_catalogo", 150)
        moneda = _texto(formulario, "moneda_catalogo", 10).upper() or "ARS"
        if not codigo or not nombre:
            raise ValueError("Completá código y nombre del catálogo.")
        if Catalogo.query.filter_by(
            organizacion_id=organizacion.id,
            codigo=codigo,
        ).first() is not None:
            raise ValueError("Ya existe un catálogo con ese código.")
        catalogo = Catalogo(
            organizacion_id=organizacion.id,
            unidad_negocio_id=unidad_activa.id,
            codigo=codigo,
            nombre=nombre,
            descripcion=_texto(formulario, "descripcion_catalogo", 500),
            moneda=moneda,
            estado="desactivado",
        )
        db_session.add(catalogo)
        _guardar(db_session)
        return f"Catálogo {nombre} creado desactivado."

    if accion == "estado_catalogo":
        catalogo = _catalogo_tenant(
            _id(formulario, "catalogo_id"), organizacion, Catalogo
        )
        if catalogo.unidad_negocio_id != unidad_activa.id:
            raise ValueError("El catálogo no pertenece a la unidad activa.")
        cambiar_estado_catalogo(
            catalogo,
            _texto(formulario, "estado", 20),
            db_session=db_session,
        )
        return f"Catálogo {catalogo.nombre} actualizado a {catalogo.estado}."

    if accion == "agregar_producto_catalogo":
        catalogo = _catalogo_tenant(
            _id(formulario, "catalogo_id"), organizacion, Catalogo
        )
        if catalogo.unidad_negocio_id != unidad_activa.id:
            raise ValueError("El catálogo no pertenece a la unidad activa.")
        producto = Producto.query.get(_id(formulario, "producto_id"))
        if producto is None:
            raise ValueError("No se encontró el producto maestro.")
        if CatalogoProducto.query.filter_by(
            catalogo_id=catalogo.id,
            producto_id=producto.id,
        ).first() is not None:
            raise ValueError("Ese producto ya está incluido en el catálogo.")
        sku = _texto(formulario, "sku_comercial", 100) or str(
            producto.sku or ""
        ).strip()
        nombre = _texto(formulario, "nombre_comercial", 255) or str(
            producto.descripcion or ""
        ).strip()
        if not sku or not nombre:
            raise ValueError("El producto necesita SKU y nombre comercial.")
        inclusion = CatalogoProducto(
            catalogo_id=catalogo.id,
            producto_id=producto.id,
            sku_comercial=sku,
            nombre_comercial=nombre,
            precio_centavos=0,
            precio_lista_centavos=None,
            disponible=False,
            activo=False,
            estado_comercial="borrador",
            estado_disponibilidad="no_disponible",
        )
        db_session.add(inclusion)
        _guardar(db_session)
        return f"{sku} incorporado como inactivo y no disponible."

    if accion == "gestionar_producto_catalogo":
        inclusion = CatalogoProducto.query.get(
            _id(formulario, "catalogo_producto_id")
        )
        if (
            inclusion is None
            or inclusion.catalogo.organizacion_id != organizacion.id
            or inclusion.catalogo.unidad_negocio_id != unidad_activa.id
        ):
            raise ValueError("El producto no pertenece a la organización.")
        estado = _texto(formulario, "estado_comercial", 20).lower()
        disponibilidad = _texto(
            formulario, "estado_disponibilidad", 20
        ).lower()
        if estado not in ESTADOS_COMERCIALES:
            raise ValueError("El estado comercial no es válido.")
        if disponibilidad not in ESTADOS_DISPONIBILIDAD:
            raise ValueError("La disponibilidad no es válida.")
        if estado != "activo":
            disponibilidad = "no_disponible"
        motivo = _texto(formulario, "motivo_disponibilidad", 300)
        if disponibilidad in {"sin_stock", "pausado"} and not motivo:
            raise ValueError("Indicá el motivo de la indisponibilidad.")
        sku = _texto(formulario, "sku_comercial", 100)
        nombre = _texto(formulario, "nombre_comercial", 255)
        if not sku or not nombre:
            raise ValueError("Completá SKU y nombre comercial.")
        inclusion.sku_comercial = sku
        inclusion.nombre_comercial = nombre
        inclusion.marca = _texto(formulario, "marca", 120) or None
        inclusion.categoria = _texto(formulario, "categoria", 120) or None
        inclusion.descripcion_corta = (
            _texto(formulario, "descripcion_corta", 300) or None
        )
        inclusion.descripcion_publica = (
            _texto(formulario, "descripcion_publica", 5000) or None
        )
        inclusion.material = _texto(formulario, "material", 120) or None
        inclusion.color = _texto(formulario, "color", 120) or None
        inclusion.terminacion = _texto(formulario, "terminacion", 120) or None
        inclusion.contenido_paquete = (
            _texto(formulario, "contenido_paquete", 3000) or None
        )
        inclusion.peso_producto_gr = _decimal_opcional(
            formulario, "peso_producto_gr"
        )
        inclusion.largo_producto_cm = _decimal_opcional(
            formulario, "largo_producto_cm"
        )
        inclusion.ancho_producto_cm = _decimal_opcional(
            formulario, "ancho_producto_cm"
        )
        inclusion.alto_producto_cm = _decimal_opcional(
            formulario, "alto_producto_cm"
        )
        inclusion.atributos_json = volcar_json(
            parsear_atributos_estructurados(formulario)
        )
        inclusion.variantes_json = volcar_json(
            parsear_variantes_estructuradas(formulario)
        )
        inclusion.canales_json = volcar_json(parsear_canales(formulario))
        inclusion.relaciones_json = volcar_json(validar_relaciones(
            formulario.getlist("relaciones")
            if hasattr(formulario, "getlist") else formulario.get("relaciones", []),
            inclusion=inclusion,
            CatalogoProducto=CatalogoProducto,
        ))
        imagenes = cargar_json(inclusion.imagenes_json, [])
        conservar = set(
            formulario.getlist("conservar_imagen")
            if hasattr(formulario, "getlist") else []
        )
        imagenes = [imagen for imagen in imagenes if imagen.get("url") in conservar]
        nuevas = subir_imagenes(
            archivos.getlist("imagenes") if archivos is not None else [],
            organizacion_id=organizacion.id,
            inclusion_id=inclusion.id,
        )
        imagenes.extend(nuevas)
        principal = str(formulario.get("imagen_principal") or "").strip()
        if imagenes and not any(imagen.get("url") == principal for imagen in imagenes):
            principal = imagenes[0].get("url")
        for imagen in imagenes:
            imagen["principal"] = imagen.get("url") == principal
        inclusion.imagenes_json = volcar_json(imagenes)
        inclusion.estado_comercial = estado
        inclusion.estado_disponibilidad = disponibilidad
        inclusion.motivo_disponibilidad = motivo or None
        inclusion.activo = estado == "activo"
        inclusion.disponible = disponibilidad == "disponible"
        producto = inclusion.producto
        producto.peso_gr = _decimal_opcional(formulario, "peso_gr")
        producto.alto_cm = _decimal_opcional(formulario, "alto_cm")
        producto.ancho_cm = _decimal_opcional(formulario, "ancho_cm")
        producto.largo_cm = _decimal_opcional(formulario, "largo_cm")
        producto.permite_correo = formulario.get("permite_correo") == "1"
        producto.permite_via_cargo = formulario.get("permite_via_cargo") == "1"
        producto.requiere_revision_logistica = (
            formulario.get("requiere_revision_logistica") == "1"
        )
        producto.observacion_logistica = (
            _texto(formulario, "observacion_logistica", 300) or None
        )
        porcentaje, faltantes = calcular_completitud(inclusion, producto)
        inclusion.completitud_pct = porcentaje
        inclusion.faltantes_ficha = ", ".join(faltantes) or None
        if estado == "activo" and disponibilidad == "disponible" and faltantes:
            raise ValueError(
                "La ficha no puede quedar disponible; faltan: "
                + ", ".join(faltantes)
                + "."
            )
        _guardar(db_session)
        return (
            f"Ficha {sku} actualizada: {estado}, "
            f"{disponibilidad.replace('_', ' ')}."
        )

    if accion in {"activar_producto_catalogo", "disponibilidad_producto_catalogo"}:
        inclusion = CatalogoProducto.query.get(
            _id(formulario, "catalogo_producto_id")
        )
        if (
            inclusion is None
            or inclusion.catalogo.organizacion_id != organizacion.id
            or inclusion.catalogo.unidad_negocio_id != unidad_activa.id
        ):
            raise ValueError("El producto no pertenece a la organización.")
        if accion == "activar_producto_catalogo":
            inclusion.activo = not bool(inclusion.activo)
            inclusion.estado_comercial = (
                "activo" if inclusion.activo else "borrador"
            )
            if not inclusion.activo:
                inclusion.disponible = False
                inclusion.estado_disponibilidad = "no_disponible"
            resultado = "activo" if inclusion.activo else "inactivo"
        else:
            if not inclusion.activo:
                raise ValueError(
                    "Activá el producto antes de marcarlo disponible."
                )
            inclusion.disponible = not bool(inclusion.disponible)
            inclusion.estado_disponibilidad = (
                "disponible" if inclusion.disponible else "sin_stock"
            )
            resultado = "disponible" if inclusion.disponible else "no disponible"
        _guardar(db_session)
        return f"{inclusion.sku_comercial} quedó {resultado}."

    raise ValueError("Acción de catálogo no reconocida.")
