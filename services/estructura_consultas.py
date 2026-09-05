"""
Consultas tenant del panel de estructura empresarial.
"""

from sqlalchemy import or_

from services.modulos_organizacion import (
    ESTADO_ACTIVO,
    ESTADO_DESACTIVADO,
    ESTADO_PRUEBA,
)
from services.certificacion_productos_tenant import (
    certificar_productos_tenant,
)
from services.identidad_tenant_pedidos import (
    obtener_diagnostico_identidad_tenant_pedidos,
)
from services.certificacion_pedidos_tenant import certificar_pedidos_tenant


def obtener_datos_panel_estructura(
    organizacion_id,
    *,
    modelos,
):
    UnidadNegocio = modelos["UnidadNegocio"]
    SucursalOperativa = modelos[
        "SucursalOperativa"
    ]
    EntidadFiscal = modelos["EntidadFiscal"]
    Catalogo = modelos["Catalogo"]
    CatalogoProducto = modelos[
        "CatalogoProducto"
    ]
    ModuloOrganizacion = modelos[
        "ModuloOrganizacion"
    ]
    Producto = modelos["Producto"]
    Pedido = modelos["Pedido"]
    Asignacion = modelos[
        "AsignacionTenantPedido"
    ]
    VinculoCanalComercial = modelos[
        "VinculoCanalComercial"
    ]
    MercadoLibreCuenta = modelos[
        "MercadoLibreCuenta"
    ]
    TiendaNubeCuenta = modelos[
        "TiendaNubeCuenta"
    ]

    unidades = (
        UnidadNegocio.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            UnidadNegocio.nombre.asc()
        )
        .all()
    )
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
    entidades_fiscales = (
        EntidadFiscal.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            EntidadFiscal.razon_social.asc()
        )
        .all()
    )
    catalogos = (
        Catalogo.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            Catalogo.nombre.asc()
        )
        .all()
    )
    modulos = (
        ModuloOrganizacion.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            ModuloOrganizacion.nombre.asc()
        )
        .all()
    )
    productos = (
        Producto.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            Producto.sku.asc()
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
    certificacion_productos = certificar_productos_tenant(
        organizacion_id,
        Producto=Producto,
        Catalogo=Catalogo,
        CatalogoProducto=CatalogoProducto,
    )
    diagnostico_pedidos = obtener_diagnostico_identidad_tenant_pedidos(
        Pedido=Pedido,
        VinculoCanalComercial=VinculoCanalComercial,
    )
    certificacion_pedidos = certificar_pedidos_tenant(
        organizacion_id, Pedido=Pedido, UnidadNegocio=UnidadNegocio,
    )
    propuestas_tenant_pedidos = (
        Asignacion.query
        .filter_by(organizacion_id=organizacion_id)
        .order_by(
            Asignacion.fecha_creacion.desc(),
            Asignacion.id.desc(),
        )
        .limit(200)
        .all()
    )
    vinculos_canales = (
        VinculoCanalComercial.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            VinculoCanalComercial.id.asc()
        )
        .all()
    )

    cuentas_ml_estructura = (
        MercadoLibreCuenta.query
        .outerjoin(
            VinculoCanalComercial,
            (
                VinculoCanalComercial
                .mercado_libre_cuenta_id
                == MercadoLibreCuenta.id
            ),
        )
        .filter(or_(
            VinculoCanalComercial.id.is_(None),
            (
                VinculoCanalComercial
                .organizacion_id
                == organizacion_id
            ),
        ))
        .order_by(
            MercadoLibreCuenta.id.asc()
        )
        .all()
    )
    cuentas_tn_estructura = (
        TiendaNubeCuenta.query
        .outerjoin(
            VinculoCanalComercial,
            (
                VinculoCanalComercial
                .tienda_nube_cuenta_id
                == TiendaNubeCuenta.id
            ),
        )
        .filter(or_(
            VinculoCanalComercial.id.is_(None),
            (
                VinculoCanalComercial
                .organizacion_id
                == organizacion_id
            ),
        ))
        .order_by(
            TiendaNubeCuenta.id.asc()
        )
        .all()
    )

    return {
        "unidades": unidades,
        "sucursales": sucursales,
        "entidades_fiscales": (
            entidades_fiscales
        ),
        "catalogos": catalogos,
        "productos": productos,
        "productos_catalogo": (
            productos_catalogo
        ),
        "certificacion_productos": (
            certificacion_productos
        ),
        "diagnostico_pedidos": diagnostico_pedidos,
        "certificacion_pedidos": certificacion_pedidos,
        "propuestas_tenant_pedidos": propuestas_tenant_pedidos,
        "modulos": modulos,
        "vinculos_canales": vinculos_canales,
        "cuentas_ml_estructura": (
            cuentas_ml_estructura
        ),
        "cuentas_tn_estructura": (
            cuentas_tn_estructura
        ),
        "estados_modulo": (
            ESTADO_DESACTIVADO,
            ESTADO_PRUEBA,
            ESTADO_ACTIVO,
        ),
    }
