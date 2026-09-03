"""
Servicio DB para catálogo de productos.

Objetivo:
- Mantener fuera de app.py la lógica de sincronización del catálogo.
- Preparar migración liviana de campos logísticos.
- Permitir que Admin importe/edite productos sin cargar la interfaz operativa.
"""

COLUMNAS_PRODUCTO_LOGISTICA = (
    ("peso_gr", "FLOAT"),
    ("alto_cm", "FLOAT"),
    ("ancho_cm", "FLOAT"),
    ("largo_cm", "FLOAT"),
    ("permite_correo", "BOOLEAN DEFAULT TRUE"),
    ("permite_via_cargo", "BOOLEAN DEFAULT TRUE"),
    ("requiere_revision_logistica", "BOOLEAN DEFAULT FALSE"),
    ("observacion_logistica", "VARCHAR(300)"),
)

CAMPOS_PRODUCTO_CATALOGO = (
    "sku",
    "descripcion",
    "peso_gr",
    "alto_cm",
    "ancho_cm",
    "largo_cm",
    "permite_correo",
    "permite_via_cargo",
    "requiere_revision_logistica",
    "observacion_logistica",
)


def aplicar_datos_producto_modelo(producto, datos):
    datos = datos or {}

    for campo in CAMPOS_PRODUCTO_CATALOGO:
        if campo in datos:
            setattr(producto, campo, datos.get(campo))

    return producto


def crear_producto_desde_catalogo(Producto, datos):
    datos = datos or {}

    producto = Producto(
        sku=datos.get("sku") or "",
        descripcion=datos.get("descripcion") or "",
    )

    return aplicar_datos_producto_modelo(producto, datos)


def sincronizar_productos_desde_catalogo(productos, Producto, db):
    """Crea o actualiza el maestro sin borrar productos ausentes.

    Un producto que no aparece en el archivo puede conservar relaciones con
    catalogos, costos, inventario, pedidos o publicaciones. Por eso una
    importacion nunca implica una baja. El SKU identifica cada fila dentro
    de este maestro global de plataforma.
    """
    preparados = []
    sku_archivo = set()

    for datos_originales in productos or []:
        datos = normalizar_producto_catalogo_db(datos_originales)
        sku = datos["sku"]
        if not sku:
            raise ValueError("Cada producto importado requiere SKU.")
        if not datos["descripcion"]:
            raise ValueError(f"El producto {sku} requiere descripcion.")
        if sku in sku_archivo:
            raise ValueError(f"El archivo contiene el SKU duplicado {sku}.")
        sku_archivo.add(sku)
        preparados.append(datos)

    existentes_por_sku = {}
    for producto in Producto.query.all():
        sku = str(getattr(producto, "sku", "") or "").strip().upper()
        if not sku:
            continue
        if sku in existentes_por_sku:
            raise ValueError(
                f"El maestro contiene mas de un producto con el SKU {sku}."
            )
        existentes_por_sku[sku] = producto

    for datos in preparados:
        producto = existentes_por_sku.get(datos["sku"])
        if producto is None:
            producto = crear_producto_desde_catalogo(Producto, datos)
        else:
            aplicar_datos_producto_modelo(producto, datos)
        db.session.add(producto)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return len(preparados)


def normalizar_producto_catalogo_db(datos):
    """Normaliza la identidad minima antes de consultar o persistir."""
    datos = dict(datos or {})
    datos["sku"] = str(datos.get("sku") or "").strip().upper()
    datos["descripcion"] = str(datos.get("descripcion") or "").strip()
    return datos


def asegurar_columnas_producto_logistica(db, inspect_fn, text_fn, tabla="producto"):
    inspector = inspect_fn(db.engine)
    columnas_existentes = {
        columna["name"]
        for columna in inspector.get_columns(tabla)
    }

    columnas_agregadas = []

    for nombre_columna, definicion_sql in COLUMNAS_PRODUCTO_LOGISTICA:
        if nombre_columna in columnas_existentes:
            continue

        db.session.execute(
            text_fn(f"ALTER TABLE {tabla} ADD COLUMN {nombre_columna} {definicion_sql}")
        )
        columnas_agregadas.append(nombre_columna)

    if columnas_agregadas:
        db.session.commit()

    return columnas_agregadas


def guardar_producto_catalogo(producto, datos, db=None):
    """
    Actualiza un producto existente con datos normalizados del catálogo.
    Si se pasa db, guarda y commitea.
    """

    producto = aplicar_datos_producto_modelo(producto, datos)

    if db is not None:
        db.session.add(producto)
        db.session.commit()

    return producto


def crear_y_guardar_producto_catalogo(Producto, datos, db=None):
    """
    Crea un producto desde datos normalizados del catálogo.
    Si se pasa db, guarda y commitea.
    """

    producto = crear_producto_desde_catalogo(Producto, datos)

    if db is not None:
        db.session.add(producto)
        db.session.commit()

    return producto


def eliminar_producto_catalogo(producto, db):
    """
    Elimina un producto del catálogo.
    """

    db.session.delete(producto)
    db.session.commit()
    return True
