"""
Registro central de modulos web del SaaS.
"""


def registrar_modulos_web(
    app,
    *,
    dependencias,
):
    from modules.admin.crm.routes import (
        crear_blueprint_crm,
    )
    from modules.admin.estructura.routes import (
        crear_blueprint_estructura,
    )
    from modules.admin.facturacion.routes import (
        crear_blueprint_facturacion,
    )
    from modules.admin.inventario.routes import (
        crear_blueprint_inventario,
    )
    from modules.admin.usuarios.routes import (
        crear_blueprint_usuarios,
    )
    from modules.auth.routes import (
        registrar_rutas_auth,
    )

    db = dependencias["db"]
    modelos = dependencias["modelos"]

    comunes = {
        "db": db,
        "login_required": (
            dependencias["login_required"]
        ),
        "usuario_actual": (
            dependencias["usuario_actual"]
        ),
        "registrar_auditoria": (
            dependencias["registrar_auditoria"]
        ),
        "UsuarioOrganizacion": (
            dependencias["UsuarioOrganizacion"]
        ),
    }

    app.register_blueprint(
        crear_blueprint_usuarios(
            dependencias={
                **comunes,
                "UsuarioSistema": (
                    dependencias["UsuarioSistema"]
                ),
            },
        )
    )

    registrar_rutas_auth(
        app,
        dependencias={
            "db": db,
            "limiter": dependencias["limiter"],
            "UsuarioSistema": (
                dependencias["UsuarioSistema"]
            ),
            "Auditoria": dependencias["Auditoria"],
            "check_password_hash": (
                dependencias["check_password_hash"]
            ),
            "usuario_actual": (
                dependencias["usuario_actual"]
            ),
            "membresia_actual": (
                dependencias["membresia_actual"]
            ),
            "registrar_auditoria": (
                dependencias["registrar_auditoria"]
            ),
        },
    )

    app.register_blueprint(
        crear_blueprint_estructura(
            dependencias={
                **comunes,
                "modelos": {
                    nombre: modelos[nombre]
                    for nombre in (
                        "UnidadNegocio",
                        "SucursalOperativa",
                        "EntidadFiscal",
                        "Catalogo",
                        "CatalogoProducto",
                        "ModuloOrganizacion",
                        "Producto",
                        "VinculoCanalComercial",
                        "MercadoLibreCuenta",
                        "TiendaNubeCuenta",
                    )
                },
            },
        )
    )

    app.register_blueprint(
        crear_blueprint_crm(
            dependencias={
                **comunes,
                "modelos": {
                    nombre: modelos[nombre]
                    for nombre in (
                        "ModuloOrganizacion",
                        "UnidadNegocio",
                        "ClienteCRM",
                        "ClienteIdentidadCanal",
                        "EtapaCRM",
                        "OportunidadCRM",
                        "ActividadCRM",
                    )
                },
            },
        )
    )

    app.register_blueprint(
        crear_blueprint_inventario(
            dependencias={
                **comunes,
                "modelos": {
                    nombre: modelos[nombre]
                    for nombre in (
                        "ModuloOrganizacion",
                        "SucursalOperativa",
                        "Producto",
                        "Catalogo",
                        "CatalogoProducto",
                        "ExistenciaSucursal",
                        "MovimientoInventario",
                        "PoliticaDisponibilidadCatalogo",
                    )
                },
            },
        )
    )

    app.register_blueprint(
        crear_blueprint_facturacion(
            dependencias={
                **comunes,
                "modelos": {
                    nombre: modelos[nombre]
                    for nombre in (
                        "ModuloOrganizacion",
                        "EntidadFiscal",
                        "ConfiguracionFiscal",
                        "PuntoVentaFiscal",
                        "TipoComprobanteFiscal",
                        "ClienteCRM",
                        "BorradorComprobanteFiscal",
                        "BorradorItemFiscal",
                        "EventoFiscal",
                    )
                },
            },
        )
    )
