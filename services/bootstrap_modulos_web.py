"""
Registro central de modulos web del SaaS.
"""


def registrar_modulos_web(
    app,
    *,
    dependencias,
):
    from modules.admin.comercial.routes import crear_blueprint_comercial
    from modules.admin.compras.routes import crear_blueprint_compras
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
    from modules.admin.produccion.routes import crear_blueprint_produccion
    from modules.admin.tesoreria.routes import crear_blueprint_tesoreria
    from modules.admin.contabilidad.routes import crear_blueprint_contabilidad
    from modules.admin.mantenimiento.routes import crear_blueprint_mantenimiento
    from modules.admin.usuarios.routes import (
        crear_blueprint_usuarios,
    )
    from modules.auth.routes import (
        registrar_rutas_auth,
    )
    from modules.pedidos.edicion_cliente_routes import (
        crear_blueprint_edicion_cliente,
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
        crear_blueprint_edicion_cliente(
            dependencias={
                **comunes,
                "Pedido": modelos["Pedido"],
                "normalizar_telefono": dependencias[
                    "normalizar_telefono"
                ],
            },
        )
    )

    app.register_blueprint(
        crear_blueprint_comercial(
            dependencias={
                **comunes,
                "modelos": {
                    nombre: modelos[nombre]
                    for nombre in (
                        "Organizacion", "UnidadNegocio", "Producto", "Pedido",
                        "Catalogo", "CatalogoProducto",
                        "CostoProductoVersion", "CostoProductoDetalle",
                        "InsumoProductivo", "InsumoPrecioVersion",
                        "MaquinaProductiva", "MaquinaCostoVersion",
                        "EmpleadoProductivo", "EmpleadoCostoVersion",
                        "EmpleadoDistribucionVersion",
                        "ConfiguracionCostoLaboralVersion",
                        "RecursoEmpleadoProductivo",
                        "CostoFijoProductivo", "CostoFijoVersion",
                        "CostoFijoDistribucionVersion",
                        "IndiceIPCOficial", "ReglaAjusteIPCProductivo",
                        "ReglaAjusteCostoHistorial",
                        "PropuestaAjusteIPCProductivo",
                        "ObligacionCostoProductivo",
                        "PagoObligacionCostoProductivo",
                        "ReglaObligacionCostoProductivo",
                        "PerfilCosteoProducto", "ComboProductoComponente",
                        "ProductoInsumoCosteo", "ProductoOperacionCosteo",
                        "ProductoMaquinaCosteo",
                        "ProductoCostoFijoCosteo",
                        "ImportacionMasivaCosto",
                        "ListaPrecio", "PoliticaComercialLista",
                        "ListaPrecioItem", "ReglaEconomicaVersion",
                        "ReglaCanalVersion", "ReglaCanalCargoTramo",
                        "PromocionCanalObservacion",
                        "PropuestaAccionComercial",
                        "ObservacionComercialCanal",
                        "ReglaValidacionCanalVersion",
                        "VentaCanalItem", "MovimientoLiquidacionCanal",
                        "GestionConciliacionCanal",
                        "ControlIntegracionCanal", "EventoIntegracionStaging",
                        "LoteDiagnosticoML", "EventoLoteDiagnosticoML",
                        "TareaManualML", "EventoTareaManualML",
                        "CierreConciliacionMP", "EventoCierreConciliacionMP",
                        "LoteImportacionMP",
                        "LoteDiagnosticoTiendaNube",
                        "EventoLoteDiagnosticoTiendaNube",
                        "PropuestaPedidoTiendaNube",
                        "EventoPropuestaPedidoTiendaNube",
                        "LoteIncorporacionTiendaNube",
                        "ItemLoteIncorporacionTiendaNube",
                        "EventoLoteIncorporacionTiendaNube",
                        "ResultadoIncorporacionTiendaNube",
                        "PedidoItem",
                        "MapeoPublicacionCanal",
                    )
                },
            },
        )
    )

    app.register_blueprint(
        crear_blueprint_compras(
            dependencias={
                **comunes,
                "modelos": {
                    nombre: modelos[nombre]
                    for nombre in (
                        "UnidadNegocio", "InsumoProductivo",
                        "ProveedorCompra", "OrdenCompra", "OrdenCompraItem",
                        "RecepcionCompra", "RecepcionCompraItem",
                        "PropuestaImpactoCompra",
                        "FacturaProveedorCompra",
                        "MapeoInsumoInventario", "ExistenciaSucursal",
                    )
                },
            },
        )
    )

    app.register_blueprint(
        crear_blueprint_produccion(
            dependencias={
                **comunes,
                "modelos": {
                    nombre: modelos[nombre]
                    for nombre in (
                        "UnidadNegocio", "PerfilCosteoProducto", "CostoProductoVersion",
                        "OrdenProduccion", "OrdenProduccionInsumo",
                        "OrdenProduccionOperacion", "OrdenProduccionMaquina",
                        "ParteProduccion", "MapeoInsumoInventario", "ExistenciaSucursal",
                        "EmpleadoProductivo", "EmpleadoCostoVersion",
                        "MaquinaProductiva", "MaquinaCostoVersion",
                        "LoteProduccion", "ControlCalidadProduccion",
                    )
                },
            },
        )
    )

    app.register_blueprint(
        crear_blueprint_tesoreria(
            dependencias={
                **comunes,
                "modelos": {
                    nombre: modelos[nombre]
                    for nombre in (
                        "UnidadNegocio", "CuentaTesoreria", "MovimientoTesoreriaProyectado",
                        "ObligacionCostoProductivo", "FacturaProveedorCompra", "VentaCanalItem",
                    )
                },
            },
        )
    )

    app.register_blueprint(
        crear_blueprint_contabilidad(
            dependencias={
                **comunes,
                "modelos": {
                    nombre: modelos[nombre]
                    for nombre in ("UnidadNegocio", "CuentaContable", "AsientoContableBorrador", "LineaAsientoContableBorrador")
                },
            },
        )
    )

    app.register_blueprint(
        crear_blueprint_mantenimiento(
            dependencias={
                **comunes,
                "modelos": {nombre:modelos[nombre] for nombre in ("UnidadNegocio","MaquinaProductiva","PlanMantenimiento","OrdenMantenimientoPreparatoria")},
            },
        )
    )

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
                        "Organizacion",
                        "UnidadNegocio",
                        "SucursalOperativa",
                        "EntidadFiscal",
                        "Catalogo",
                        "CatalogoProducto",
                        "ModuloOrganizacion",
                        "Producto",
                        "Pedido",
                        "AsignacionTenantPedido",
                        "WhatsAppMensaje",
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
                        "LoteImportacionCRM",
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
                        "ItemInventario",
                        "ReservaInventario",
                        "TransferenciaInventario",
                        "ConteoInventario",
                        "ConteoInventarioItem",
                        "ConfiguracionInventarioPedidos",
                        "EventoInventarioPedido",
                        "EventoCanalInventario",
                        "PropuestaPublicacionInventario",
                        "Pedido",
                        "PedidoItem",
                        "VinculoCanalComercial",
                        "PoliticaDisponibilidadCatalogo",
                        "MapeoPublicacionCanal",
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
                        "LoteImportacionFiscal",
                        "ExpedienteAutorizacionFiscal",
                    )
                },
            },
        )
    )
