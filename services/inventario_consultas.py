"""
Consultas tenant del inventario administrativo.

No modifica stock, no importa pedidos y no sincroniza
datos con canales comerciales.
"""

from services.inventario_eventos_canal import (
    diagnosticar_eventos_persistidos,
)
from services.inventario_disponibilidad_comercial import (
    construir_vista_previa_disponibilidad,
)
from services.inventario_cola_publicacion import diagnosticar_cola


def obtener_datos_panel_inventario(
    organizacion,
    *,
    modelos,
):
    organizacion_id = int(
        organizacion.id
    )

    ModuloOrganizacion = modelos[
        "ModuloOrganizacion"
    ]
    SucursalOperativa = modelos[
        "SucursalOperativa"
    ]
    Catalogo = modelos[
        "Catalogo"
    ]
    CatalogoProducto = modelos[
        "CatalogoProducto"
    ]
    ExistenciaSucursal = modelos[
        "ExistenciaSucursal"
    ]
    MovimientoInventario = modelos[
        "MovimientoInventario"
    ]
    ItemInventario = modelos["ItemInventario"]
    ReservaInventario = modelos["ReservaInventario"]
    TransferenciaInventario = modelos["TransferenciaInventario"]
    ConteoInventario = modelos["ConteoInventario"]
    ConfiguracionInventarioPedidos = modelos["ConfiguracionInventarioPedidos"]
    Evento = modelos["EventoInventarioPedido"]
    EventoCanal = modelos["EventoCanalInventario"]
    PropuestaPublicacion = modelos["PropuestaPublicacionInventario"]
    VinculoCanalComercial = modelos["VinculoCanalComercial"]
    PoliticaDisponibilidadCatalogo = modelos[
        "PoliticaDisponibilidadCatalogo"
    ]

    modulo_inventario = (
        ModuloOrganizacion.query
        .filter_by(
            organizacion_id=organizacion_id,
            codigo="inventario-sucursales",
        )
        .first()
    )
    automatizacion_pedidos = ConfiguracionInventarioPedidos.query.filter_by(
        organizacion_id=organizacion_id,
    ).first()
    eventos_pedidos = Evento.query.filter_by(
        organizacion_id=organizacion_id,
    ).order_by(Evento.id.desc()).limit(100).all()
    eventos_canal = EventoCanal.query.filter_by(
        organizacion_id=organizacion_id,
    ).order_by(EventoCanal.id.desc()).limit(100).all()
    propuestas_publicacion = PropuestaPublicacion.query.filter_by(
        organizacion_id=organizacion_id,
    ).order_by(PropuestaPublicacion.id.desc()).limit(100).all()
    diagnosticos_propuestas, resumen_propuestas = diagnosticar_cola(
        propuestas_publicacion
    )
    vinculos_canal = VinculoCanalComercial.query.filter_by(
        organizacion_id=organizacion_id,
    ).all()

    sucursales = (
        SucursalOperativa.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            SucursalOperativa.nombre.asc()
        )
        .all()
    )

    productos_catalogo = (
        CatalogoProducto.query
        .join(Catalogo)
        .filter(
            Catalogo.organizacion_id
            == organizacion_id
        )
        .order_by(
            CatalogoProducto.id.asc()
        )
        .all()
    )

    productos_por_id = {}

    for inclusion in productos_catalogo:
        producto = getattr(
            inclusion,
            "producto",
            None,
        )

        if producto is not None:
            productos_por_id[
                int(producto.id)
            ] = producto

    productos = sorted(
        productos_por_id.values(),
        key=lambda producto: (
            str(
                getattr(
                    producto,
                    "sku",
                    "",
                )
                or ""
            ).lower(),
            int(
                getattr(
                    producto,
                    "id",
                    0,
                )
                or 0
            ),
        ),
    )

    existencias = (
        ExistenciaSucursal.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            ExistenciaSucursal.id.asc()
        )
        .all()
    )

    movimientos = (
        MovimientoInventario.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            MovimientoInventario.id.desc()
        )
        .limit(200)
        .all()
    )

    politicas = (
        PoliticaDisponibilidadCatalogo.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            PoliticaDisponibilidadCatalogo.id.asc()
        )
        .all()
    )

    items_inventario = ItemInventario.query.filter_by(
        organizacion_id=organizacion_id
    ).order_by(ItemInventario.sku.asc()).all()
    reservas = ReservaInventario.query.filter_by(
        organizacion_id=organizacion_id
    ).order_by(ReservaInventario.id.desc()).limit(100).all()
    transferencias = TransferenciaInventario.query.filter_by(
        organizacion_id=organizacion_id
    ).order_by(TransferenciaInventario.id.desc()).limit(100).all()
    conteos = ConteoInventario.query.filter_by(
        organizacion_id=organizacion_id
    ).order_by(ConteoInventario.id.desc()).limit(100).all()
    diagnosticos_canal, resumen_diagnosticos_canal = (
        diagnosticar_eventos_persistidos(
            eventos_canal,
            configuracion=automatizacion_pedidos,
            vinculos=vinculos_canal,
            items_inventario=items_inventario,
            existencias=existencias,
            reservas=reservas,
        )
    )
    vista_previa_disponibilidad = construir_vista_previa_disponibilidad(
        politicas,
        items_inventario=items_inventario,
        existencias=existencias,
        vinculos=vinculos_canal,
    )

    pares_existentes = {
        (
            int(existencia.sucursal_operativa_id),
            int(existencia.item_inventario_id),
        )
        for existencia in existencias
        if existencia.item_inventario_id is not None
    }
    combinaciones_faltantes = [
        {
            "sucursal_id": int(sucursal.id),
            "sucursal_nombre": sucursal.nombre,
            "item_id": int(item.id),
            "sku": item.sku,
            "item_nombre": item.nombre,
        }
        for sucursal in sucursales
        if sucursal.activa
        for item in items_inventario
        if item.activo and (int(sucursal.id), int(item.id)) not in pares_existentes
    ]
    sucursales_con_control_ids = {
        int(existencia.sucursal_operativa_id)
        for existencia in existencias
        if existencia.control_activo
    }
    sucursales_con_control = [
        sucursal
        for sucursal in sucursales
        if int(sucursal.id) in sucursales_con_control_ids
    ]

    return {
        "modulo_inventario": modulo_inventario,
        "sucursales": sucursales,
        "productos": productos,
        "existencias": existencias,
        "movimientos": movimientos,
        "politicas": politicas,
        "productos_catalogo": (
            productos_catalogo
        ),
        "vinculos_canal": vinculos_canal,
        "items_inventario": items_inventario,
        "reservas": reservas,
        "transferencias": transferencias,
        "conteos": conteos,
        "combinaciones_faltantes": combinaciones_faltantes,
        "sucursales_con_control": sucursales_con_control,
        "automatizacion_pedidos": automatizacion_pedidos,
        "eventos_inventario_pedidos": eventos_pedidos,
        "eventos_canal_inventario": eventos_canal,
        "diagnosticos_eventos_canal": diagnosticos_canal,
        "resumen_diagnosticos_canal": resumen_diagnosticos_canal,
        "vista_previa_disponibilidad": vista_previa_disponibilidad,
        "propuestas_publicacion_inventario": propuestas_publicacion,
        "diagnosticos_propuestas_publicacion": diagnosticos_propuestas,
        "resumen_propuestas_publicacion": resumen_propuestas,
    }
