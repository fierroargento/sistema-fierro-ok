"""Reglas comunes de la ficha maestra. Sin activar canales ni movimientos."""
from sqlalchemy import inspect, select

USOS = {
    "compra": "Disponible para compra", "venta": "Disponible para venta",
    "insumo": "Insumo de producción", "componente": "Componente de combo",
}
TIPOS = {"simple": "Simple", "produccion": "De producción", "combo": "Combo"}


class ProductoNoStockeable(ValueError):
    """El artículo no participa en el inventario físico."""


CAMPOS_FICHA = (
    "nombre", "linea", "unidad_medida", "tipo", "activo", "no_stockeable",
    "habilita_compra", "habilita_venta", "habilita_insumo", "habilita_componente", "insumo_id",
)


def esquema_ficha_disponible(db_session):
    inspector = inspect(db_session.connection())
    if not inspector.has_table("producto_ficha_maestra"):
        return False
    columnas = {c["name"] for c in inspector.get_columns("producto_ficha_maestra")}
    return set(CAMPOS_FICHA) | {"producto_id", "organizacion_id", "revision"} <= columnas


def leer_ficha(producto, db_session):
    # Las funciones puras de los módulos también se prueban con DTOs sin DB.
    # En ejecución real se exige un modelo mapeado y sesión real.
    if inspect(producto, raiseerr=False) is None:
        return None
    if not esquema_ficha_disponible(db_session):
        return None
    from models.producto_ficha_maestra import ProductoFichaMaestra
    return db_session.query(ProductoFichaMaestra).filter_by(
        producto_id=producto.id, organizacion_id=producto.organizacion_id,
    ).populate_existing().first()


def exigir_uso_producto(producto, uso, db_session):
    if uso not in USOS:
        raise ValueError("El uso del producto no es válido.")
    ficha = leer_ficha(producto, db_session)
    # Compatibilidad explícita: un maestro anterior sin ficha no cambia su
    # operación. La UI lo distingue de los productos ya configurados.
    if ficha is not None and (not ficha.activo or not getattr(ficha, "habilita_" + uso)):
        raise ValueError(f"{producto.sku}: habilitá «{USOS[uso]}» en Base de Datos → Productos.")
    return ficha


def exigir_tipo_producto(producto, tipo, db_session):
    ficha = leer_ficha(producto, db_session)
    if ficha is not None and ficha.tipo != tipo:
        raise ValueError(f"El tipo de {producto.sku} es {TIPOS[ficha.tipo]} en Productos. Revisá su ficha maestra.")


def exigir_producto_stockeable(producto, db_session):
    ficha = leer_ficha(producto, db_session)
    if ficha is not None and ficha.no_stockeable:
        raise ProductoNoStockeable(f"{producto.sku}: es No stockeable. No admite existencias, reservas ni movimientos de inventario.")


def exigir_recurso_stockeable(recurso, db_session):
    if inspect(recurso, raiseerr=False) is None:
        return
    from models.producto import Producto
    producto = db_session.query(Producto).filter_by(
        id=recurso.producto_id, organizacion_id=recurso.organizacion_id,
    ).first()
    if producto is None:
        raise ValueError("El registro de inventario no tiene un producto maestro válido.")
    exigir_producto_stockeable(producto, db_session)


def exigir_insumo_stockeable(insumo, db_session):
    if inspect(insumo, raiseerr=False) is None or not esquema_ficha_disponible(db_session):
        return
    from models.producto_ficha_maestra import ProductoFichaMaestra
    ficha = db_session.query(ProductoFichaMaestra).filter_by(
        organizacion_id=insumo.organizacion_id, insumo_id=insumo.id,
        no_stockeable=True,
    ).first()
    if ficha is not None:
        raise ProductoNoStockeable("El insumo está vinculado a un producto No stockeable. No se crea otro SKU de inventario para la misma identidad.")


def motivo_venta_item(item):
    """La vista publicable también respeta el maestro, sin consultar APIs."""
    estado = inspect(item, raiseerr=False)
    if estado is None or estado.session is None:
        return None
    from models.producto import Producto
    producto = estado.session.query(Producto).filter_by(
        id=item.producto_id, organizacion_id=item.organizacion_id,
    ).first()
    if producto is None:
        return "El SKU no tiene un producto maestro de la organización"
    try:
        exigir_uso_producto(producto, "venta", estado.session)
    except ValueError as error:
        return str(error)
    return None


def exigir_uso_insumo(insumo, uso, db_session, unidad_negocio_id=None):
    """Resuelve identidades verificadas, nunca por coincidencia de códigos."""
    if inspect(insumo, raiseerr=False) is None or not esquema_ficha_disponible(db_session):
        return
    from models.producto import Producto
    from models.producto_ficha_maestra import ProductoFichaMaestra
    ids = set(db_session.scalars(select(ProductoFichaMaestra.producto_id).where(
        ProductoFichaMaestra.organizacion_id == insumo.organizacion_id,
        ProductoFichaMaestra.insumo_id == insumo.id,
    )))
    # Conserva el enlace de inventario que ya existía para materias primas.
    tablas = Producto.metadata.tables
    mapeo, existencia = tablas.get("mapeo_insumo_inventario"), tablas.get("existencia_sucursal")
    inspector = inspect(db_session.connection())
    if mapeo is not None and existencia is not None and inspector.has_table(mapeo.name) and inspector.has_table(existencia.name):
        consulta = select(existencia.c.producto_id).join(mapeo, mapeo.c.existencia_sucursal_id == existencia.c.id).where(
            mapeo.c.organizacion_id == insumo.organizacion_id,
            mapeo.c.insumo_id == insumo.id, mapeo.c.activo.is_(True),
        )
        if unidad_negocio_id is not None:
            consulta = consulta.where(mapeo.c.unidad_negocio_id == unidad_negocio_id)
        ids.update(db_session.scalars(consulta))
    for ident in ids:
        producto = db_session.query(Producto).filter_by(id=ident, organizacion_id=insumo.organizacion_id).first()
        if producto is None:
            raise ValueError("El vínculo del insumo requiere revisión en Productos.")
        exigir_uso_producto(producto, uso, db_session)
