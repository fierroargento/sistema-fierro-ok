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
    productos = productos or []

    db.session.query(Producto).delete()

    for datos in productos:
        db.session.add(crear_producto_desde_catalogo(Producto, datos))

    db.session.commit()

    return len(productos)


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
