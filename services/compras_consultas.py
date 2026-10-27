"""Consultas tenant del panel de compras."""


from services.unidades_materias_primas import texto_unidad
import json


def _detalle_seguro(propuesta):
    try:
        dato = json.loads(propuesta.detalle_json or "{}")
        return dato if isinstance(dato, dict) else {}
    except (ValueError, TypeError):
        return {}

def obtener_panel_compras(organizacion_id, unidad_negocio_id, *, modelos):
    Proveedor = modelos["ProveedorCompra"]
    Orden = modelos["OrdenCompra"]
    Recepcion = modelos["RecepcionCompra"]
    Insumo = modelos["InsumoProductivo"]
    Propuesta = modelos["PropuestaImpactoCompra"]
    Mapeo = modelos["MapeoInsumoInventario"]
    Existencia = modelos["ExistenciaSucursal"]
    Factura = modelos["FacturaProveedorCompra"]
    from extensions import db
    from services.proveedores_unidad import consulta, estados
    from scripts.preparar_proveedores_unidad import preparado
    proveedores = consulta(Proveedor, organizacion_id, unidad_negocio_id, db.session).order_by(Proveedor.razon_social.asc()).all()
    estados_proveedores=estados(organizacion_id,unidad_negocio_id,db.session)
    ordenes = Orden.query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
    ).order_by(Orden.fecha_creacion.desc()).all()
    recepciones = Recepcion.query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
    ).order_by(Recepcion.fecha_creacion.desc()).all()
    insumos = Insumo.query.filter_by(
        organizacion_id=organizacion_id, activo=True,
    ).order_by(Insumo.nombre.asc()).all()
    insumos = [item for item in insumos if item.unidad_negocio_id in (None, unidad_negocio_id)]
    propuestas = Propuesta.query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
    ).order_by(Propuesta.fecha_creacion.desc()).all()
    mapeos = Mapeo.query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
    ).order_by(Mapeo.fecha_creacion.desc()).all()
    existencias = Existencia.query.filter_by(
        organizacion_id=organizacion_id,
    ).order_by(Existencia.id.asc()).all()
    facturas = Factura.query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
    ).order_by(Factura.fecha_creacion.desc()).all()
    return {
        "proveedores": proveedores,
        "estados_proveedores": estados_proveedores,
        "proveedores_unidad_preparados": preparado(db.session.connection()),
        "unidad_stock_por_existencia": {e.id: texto_unidad(e.item_inventario) for e in existencias},
        "ordenes_compra": ordenes,
        "recepciones_compra": recepciones,
        "insumos_compra": insumos,
        "propuestas_impacto_compra": propuestas,
        "detalles_propuestas_compra": {p.id: _detalle_seguro(p) for p in propuestas},
        "mapeos_insumo_inventario": mapeos,
        "existencias_para_compras": [item for item in existencias
            if item.item_inventario is not None and item.item_inventario.tipo == "insumo"
            and item.item_inventario.activo and item.control_activo
            and item.sucursal.activa],
        "facturas_proveedor_compra": facturas,
        "resumen_compras": {
            "proveedores_activos": sum(estados_proveedores.get(item.id)=="activo" for item in proveedores),
            "ordenes_abiertas": sum(item.estado in {"borrador", "en_revision", "aprobada"} for item in ordenes),
            "ordenes_aprobadas": sum(item.estado == "aprobada" for item in ordenes),
            "recepciones_preparatorias": sum(item.estado == "preparatoria" for item in recepciones),
            "propuestas_pendientes": sum(item.estado in {"preparada", "bloqueada"} for item in propuestas),
            "insumos_mapeados": sum(bool(item.activo) for item in mapeos),
            "facturas_observadas": sum(item.estado == "observada" for item in facturas),
        },
    }
