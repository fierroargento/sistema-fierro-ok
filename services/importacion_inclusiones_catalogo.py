"""Importacion tenant de productos incluidos en catalogos comerciales.

Este modulo no consulta canales externos, no activa productos y no modifica
precios. Su unico alcance es preparar identidades internas en estado borrador.
"""

from io import BytesIO

from openpyxl import Workbook

from services.importacion_productos_costeo import normalizar


CAMPOS_INCLUSIONES = {
    "catalogo_codigo": {
        "nombre": "Codigo de catalogo", "obligatorio": True,
        "alias": {
            "catalogo", "codigo catalogo", "codigo de catalogo",
            "catalogo codigo",
        },
    },
    "sku": {
        "nombre": "SKU maestro", "obligatorio": True,
        "alias": {"sku", "sku maestro", "codigo", "codigo producto"},
    },
    "descripcion": {
        "nombre": "Descripcion maestra", "obligatorio": True,
        "alias": {"descripcion", "descripcion maestra", "producto", "nombre"},
    },
    "sku_comercial": {
        "nombre": "SKU comercial", "obligatorio": False,
        "alias": {"sku comercial", "codigo comercial"},
    },
    "nombre_comercial": {
        "nombre": "Nombre comercial", "obligatorio": False,
        "alias": {"nombre comercial", "titulo comercial"},
    },
    "marca": {
        "nombre": "Marca", "obligatorio": False,
        "alias": {"marca"},
    },
    "categoria": {
        "nombre": "Categoria", "obligatorio": False,
        "alias": {"categoria", "familia", "linea"},
    },
}


def sugerir_mapeo_inclusiones(encabezados):
    resultado, usados = {}, set()
    for indice, encabezado in enumerate(encabezados):
        limpio = normalizar(encabezado)
        destino = ""
        for campo, definicion in CAMPOS_INCLUSIONES.items():
            if campo not in usados and limpio in definicion["alias"]:
                destino = campo
                usados.add(campo)
                break
        resultado[str(indice)] = destino
    return resultado


def validar_mapeo_inclusiones(mapeo):
    destinos = [campo for campo in mapeo.values() if campo]
    if len(destinos) != len(set(destinos)):
        raise ValueError("Un campo del sistema no puede recibir dos columnas.")
    faltantes = [
        definicion["nombre"]
        for campo, definicion in CAMPOS_INCLUSIONES.items()
        if definicion["obligatorio"] and campo not in destinos
    ]
    if faltantes:
        raise ValueError("Faltan campos obligatorios: " + ", ".join(faltantes) + ".")


def _extraer(fila, mapeo):
    return {
        campo: (
            fila["valores"][int(indice)]
            if int(indice) < len(fila["valores"])
            else ""
        )
        for indice, campo in mapeo.items() if campo
    }


def _texto(datos, campo, limite):
    return str(datos.get(campo) or "").strip()[:limite]


def _producto_tenant_por_sku(
    sku, *, organizacion_id, Producto, Catalogo, CatalogoProducto,
):
    return Producto.query.filter(
        Producto.organizacion_id == organizacion_id,
        Producto.sku.ilike(sku),
    ).all()


def previsualizar_inclusiones(
    filas, mapeo, *, organizacion_id, unidad_negocio_id, modelos,
):
    """Valida un lote sin crear productos ni inclusiones."""
    validar_mapeo_inclusiones(mapeo)
    Producto = modelos["Producto"]
    Catalogo = modelos["Catalogo"]
    CatalogoProducto = modelos["CatalogoProducto"]
    resultado, identidades = [], set()

    for fila in filas:
        datos = _extraer(fila, mapeo)
        catalogo_codigo = _texto(datos, "catalogo_codigo", 80).lower()
        sku = _texto(datos, "sku", 80).upper()
        descripcion = _texto(datos, "descripcion", 255)
        sku_comercial = _texto(datos, "sku_comercial", 100).upper() or sku
        nombre_comercial = (
            _texto(datos, "nombre_comercial", 255) or descripcion
        )
        marca = _texto(datos, "marca", 120)
        categoria = _texto(datos, "categoria", 120)
        errores = []
        catalogo = None
        producto = None
        inclusion = None

        if not catalogo_codigo:
            errores.append("Falta codigo de catalogo")
        if not sku:
            errores.append("Falta SKU maestro")
        if not descripcion:
            errores.append("Falta descripcion maestra")
        identidad = (catalogo_codigo, sku_comercial)
        if all(identidad):
            if identidad in identidades:
                errores.append("El archivo contiene una inclusion duplicada")
            identidades.add(identidad)

        if not errores:
            catalogo = Catalogo.query.filter_by(
                organizacion_id=organizacion_id,
                unidad_negocio_id=unidad_negocio_id,
                codigo=catalogo_codigo,
            ).first()
            if catalogo is None:
                errores.append("No existe el catalogo en la unidad activa")

        productos = []
        if not errores:
            productos = _producto_tenant_por_sku(
                sku, organizacion_id=organizacion_id,
                Producto=Producto, Catalogo=Catalogo,
                CatalogoProducto=CatalogoProducto,
            )
            if len(productos) > 1:
                errores.append("El SKU identifica mas de un producto del tenant")
            elif productos:
                producto = productos[0]

        if not errores and producto is not None:
            inclusion = CatalogoProducto.query.filter_by(
                catalogo_id=catalogo.id,
                producto_id=producto.id,
            ).first()
            por_sku = CatalogoProducto.query.filter(
                CatalogoProducto.catalogo_id == catalogo.id,
                CatalogoProducto.sku_comercial.ilike(sku_comercial),
            ).first()
            if por_sku is not None and (
                inclusion is None or por_sku.id != inclusion.id
            ):
                errores.append("El SKU comercial ya pertenece a otro producto")

        if errores:
            accion = "rechazado"
        elif inclusion is None and producto is None:
            accion = "crear_producto_e_inclusion"
        elif inclusion is None:
            accion = "crear_inclusion"
        else:
            cambios = any((
                str(producto.descripcion or "").strip() != descripcion,
                str(inclusion.sku_comercial or "").strip().upper() != sku_comercial,
                str(inclusion.nombre_comercial or "").strip() != nombre_comercial,
                str(inclusion.marca or "").strip() != marca,
                str(inclusion.categoria or "").strip() != categoria,
            ))
            accion = "actualizar" if cambios else "sin_cambios"

        resultado.append({
            "numero": fila["numero"],
            "catalogo_codigo": catalogo_codigo,
            "catalogo_id": getattr(catalogo, "id", None),
            "producto_id": getattr(producto, "id", None),
            "inclusion_id": getattr(inclusion, "id", None),
            "sku": sku,
            "descripcion": descripcion,
            "sku_comercial": sku_comercial,
            "nombre_comercial": nombre_comercial,
            "marca": marca,
            "categoria": categoria,
            "accion": accion,
            "errores": errores,
        })
    return resultado


def aplicar_inclusiones(
    vista, *, organizacion_id, unidad_negocio_id, modelos, db_session,
):
    """Aplica exclusivamente filas validadas y deja inclusiones desconectadas."""
    Producto = modelos["Producto"]
    Catalogo = modelos["Catalogo"]
    CatalogoProducto = modelos["CatalogoProducto"]
    conteos = {
        "creados": 0, "actualizados": 0,
        "sin_cambios": 0, "rechazados": 0,
    }
    productos_creados_lote = {}

    try:
        for fila in vista:
            accion = fila.get("accion")
            if accion == "rechazado":
                conteos["rechazados"] += 1
                continue
            if accion == "sin_cambios":
                conteos["sin_cambios"] += 1
                continue
            catalogo = Catalogo.query.filter_by(
                id=fila.get("catalogo_id"),
                organizacion_id=organizacion_id,
                unidad_negocio_id=unidad_negocio_id,
            ).first()
            if catalogo is None:
                raise ValueError("El catalogo cambio desde la validacion.")

            producto_id = fila.get("producto_id")
            producto = (
                db_session.get(Producto, producto_id) if producto_id else None
            )
            if (
                producto is not None
                and producto.organizacion_id != organizacion_id
            ):
                raise ValueError(
                    "El producto cambió de organización desde la validación."
                )
            if producto is None:
                producto = productos_creados_lote.get(fila["sku"])
            if producto is None:
                producto = Producto(
                    organizacion_id=organizacion_id,
                    sku=fila["sku"],
                    descripcion=fila["descripcion"],
                )
                db_session.add(producto)
                db_session.flush()
                productos_creados_lote[fila["sku"]] = producto

            inclusion_id = fila.get("inclusion_id")
            inclusion = (
                db_session.get(CatalogoProducto, inclusion_id)
                if inclusion_id else None
            )
            if inclusion is not None and (
                inclusion.catalogo_id != catalogo.id
                or inclusion.producto_id != producto.id
            ):
                raise ValueError(
                    "La inclusión cambió de tenant, catálogo o producto "
                    "desde la validación."
                )
            creado = inclusion is None
            if creado:
                inclusion = CatalogoProducto(
                    catalogo_id=catalogo.id,
                    producto_id=producto.id,
                    precio_centavos=0,
                    precio_lista_centavos=None,
                    disponible=False,
                    activo=False,
                    estado_comercial="borrador",
                    estado_disponibilidad="no_disponible",
                )
                db_session.add(inclusion)
            inclusion.sku_comercial = fila["sku_comercial"]
            inclusion.nombre_comercial = fila["nombre_comercial"]
            inclusion.marca = fila["marca"] or None
            inclusion.categoria = fila["categoria"] or None
            conteos["creados" if creado else "actualizados"] += 1
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return conteos


def aplicar_modo_inclusiones(vista, modo):
    modos = {"crear_actualizar", "solo_crear", "solo_actualizar", "solo_validar"}
    if modo not in modos:
        raise ValueError("El modo de importacion no es valido.")
    resultado = []
    for original in vista:
        fila = {**original, "errores": list(original.get("errores") or [])}
        accion = fila.get("accion")
        es_creacion = accion in {"crear_producto_e_inclusion", "crear_inclusion"}
        if modo == "solo_crear" and accion == "actualizar":
            fila["accion"] = "rechazado"
            fila["errores"].append("El registro ya existe")
        elif modo == "solo_actualizar" and es_creacion:
            fila["accion"] = "rechazado"
            fila["errores"].append("La inclusion todavia no existe")
        resultado.append(fila)
    return resultado


def plantilla_inclusiones_catalogo():
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Productos por catalogo"
    hoja.append([
        definicion["nombre"].upper()
        for definicion in CAMPOS_INCLUSIONES.values()
    ])
    hoja.append([
        "catalogo-fierro", "PP6040H", "Parrilla plegable 60x40",
        "PP6040H", "Parrilla plegable 60x40", "Fierro", "Parrillas",
    ])
    salida = BytesIO()
    libro.save(salida)
    salida.seek(0)
    return salida
