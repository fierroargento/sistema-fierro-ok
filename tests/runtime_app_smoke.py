"""Smoke real: se ejecuta en un subproceso sin los dobles de tests/conftest.py."""

from io import BytesIO
from types import SimpleNamespace

from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.security import check_password_hash

import app as modulo
from services.ajustes_costos_ipc import actualizar_indices_oficiales
from services.marcador_base_entorno import (
    crear_marcador_staging,
    verificar_marcador_staging,
)
from services.almacenamiento_archivos import guardar_imagen_local
from services.compras_nucleo import crear_orden, crear_proveedor
from services.costos_productos import crear_version_costo
from services.catalogo_ficha_integral import validar_relaciones
from services.importacion_inclusiones_catalogo import aplicar_inclusiones
from services.inventario_saas import (
    cerrar_reserva,
    conciliar_conteo,
    crear_reserva,
    validar_transferencia,
)
from services.produccion_nucleo import crear_orden_preparatoria
from services.tesoreria_nucleo import (
    crear_cuenta as crear_cuenta_tesoreria,
    crear_proyeccion,
)
from services.contabilidad_nucleo import (
    crear_borrador as crear_borrador_contable,
    crear_cuenta as crear_cuenta_contable,
)
from services.crm_admin import procesar_accion_crm_admin
from services.postventa_preparatoria import crear_caso, proponer_resolucion
from services.cierre_postventa import agregar_item


aplicacion = modulo.app
db = modulo.db
aplicacion.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)

with aplicacion.app_context():
    assert crear_marcador_staging(db.engine, "marcador-runtime-pruebas-aisladas-2026")
    assert verificar_marcador_staging(db.engine, "marcador-runtime-pruebas-aisladas-2026")
    assert not crear_marcador_staging(db.engine, "marcador-runtime-pruebas-aisladas-2026")
    db.create_all()
    organizacion = modulo.Organizacion(
        nombre="Fierro UAT",
        slug="fierro-uat",
        activa=True,
    )
    unidad = modulo.UnidadNegocio(
        organizacion=organizacion,
        nombre="Fierro",
        codigo="fierro",
        activa=True,
    )
    db.session.add_all([organizacion, unidad])
    db.session.commit()
    organizacion_id = organizacion.id
    unidad_id = unidad.id

runner = aplicacion.test_cli_runner()
resultado = runner.invoke(
    args=[
        "crear-admin-inicial",
        "--username", "admin-uat",
        "--nombre", "Administrador UAT",
        "--password", "Clave-UAT-Segura-2026",
        "--organizacion", "fierro-uat",
    ],
)
assert resultado.exit_code == 0, resultado.output

with aplicacion.app_context():
    usuario = modulo.UsuarioSistema.query.filter_by(username="admin-uat").one()
    membresia = modulo.UsuarioOrganizacion.query.filter_by(
        usuario_id=usuario.id,
        organizacion_id=organizacion_id,
    ).one()
    assert membresia.rol == "admin"
    assert check_password_hash(usuario.password_hash, "Clave-UAT-Segura-2026")
    ids = usuario.id, organizacion_id, unidad_id
    organizacion_nautica = modulo.Organizacion(
        nombre="Náutica UAT",
        slug="nautica-uat",
        activa=True,
    )
    unidad_nautica = modulo.UnidadNegocio(
        organizacion=organizacion_nautica,
        nombre="Náutica",
        codigo="nautica",
        activa=True,
    )
    db.session.add_all([organizacion_nautica, unidad_nautica])
    db.session.flush()
    db.session.add(modulo.UsuarioOrganizacion(
        usuario_id=usuario.id,
        organizacion_id=organizacion_nautica.id,
        rol="admin",
        activa=True,
        predeterminada=False,
    ))
    respuesta_fierro = modulo.RespuestaRapidaWA(
        organizacion_id=organizacion_id,
        titulo="SECRETO_FIERRO_UAT",
        texto="Visible sólo en Fierro",
        categoria="prueba",
        activa=True,
    )
    db.session.add(respuesta_fierro)
    db.session.commit()
    nautica_ids = organizacion_nautica.id, unidad_nautica.id
    respuesta_fierro_id = respuesta_fierro.id

    producto_fierro = modulo.Producto(
        organizacion_id=organizacion_id,
        sku="SKU-COMPARTIDO-UAT",
        descripcion="Producto Fierro UAT",
    )
    producto_nautica = modulo.Producto(
        organizacion_id=organizacion_nautica.id,
        sku="SKU-COMPARTIDO-UAT",
        descripcion="Producto Náutica UAT",
    )
    insumo_fierro = modulo.InsumoProductivo(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_id,
        codigo="CHAPA-UAT",
        nombre="Chapa UAT",
        tipo="materia_prima",
        unidad_medida="kg",
        activo=True,
    )
    db.session.add_all([producto_fierro, producto_nautica, insumo_fierro])
    db.session.commit()
    assert modulo.Producto.query.filter_by(
        organizacion_id=organizacion_id,
        sku="SKU-COMPARTIDO-UAT",
    ).one().descripcion == "Producto Fierro UAT"
    assert modulo.Producto.query.filter_by(
        organizacion_id=organizacion_nautica.id,
        sku="SKU-COMPARTIDO-UAT",
    ).one().descripcion == "Producto Náutica UAT"

    catalogo_fierro = modulo.Catalogo(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_id,
        codigo="catalogo-fierro-uat",
        nombre="Catálogo Fierro UAT",
        estado="desactivado",
    )
    catalogo_nautica = modulo.Catalogo(
        organizacion_id=organizacion_nautica.id,
        unidad_negocio_id=unidad_nautica.id,
        codigo="catalogo-nautica-uat",
        nombre="Catálogo Náutica UAT",
        estado="desactivado",
    )
    db.session.add_all([catalogo_fierro, catalogo_nautica])
    db.session.flush()
    inclusion_fierro = modulo.CatalogoProducto(
        catalogo_id=catalogo_fierro.id,
        producto_id=producto_fierro.id,
        sku_comercial="SKU-COMPARTIDO-UAT",
        nombre_comercial="Producto Fierro UAT",
        precio_centavos=0,
        activo=False,
        disponible=False,
    )
    inclusion_nautica = modulo.CatalogoProducto(
        catalogo_id=catalogo_nautica.id,
        producto_id=producto_nautica.id,
        sku_comercial="SKU-COMPARTIDO-UAT",
        nombre_comercial="Producto Náutica UAT",
        precio_centavos=0,
        activo=False,
        disponible=False,
    )
    db.session.add_all([inclusion_fierro, inclusion_nautica])
    db.session.commit()
    try:
        validar_relaciones(
            [f"complementario:{inclusion_nautica.id}"],
            inclusion=inclusion_fierro,
            CatalogoProducto=modulo.CatalogoProducto,
        )
    except ValueError as error:
        assert "organización y unidad" in str(error)
    else:
        raise AssertionError("Catálogo aceptó una relación de otro tenant.")
    try:
        aplicar_inclusiones(
            [{
                "accion": "actualizar",
                "catalogo_id": catalogo_fierro.id,
                "producto_id": producto_fierro.id,
                "inclusion_id": inclusion_nautica.id,
                "sku": producto_fierro.sku,
                "descripcion": producto_fierro.descripcion,
                "sku_comercial": "ATAQUE-CRUZADO",
                "nombre_comercial": "No modificar",
                "marca": "",
                "categoria": "",
            }],
            organizacion_id=organizacion_id,
            unidad_negocio_id=unidad_id,
            modelos={
                "Producto": modulo.Producto,
                "Catalogo": modulo.Catalogo,
                "CatalogoProducto": modulo.CatalogoProducto,
            },
            db_session=db.session,
        )
    except ValueError as error:
        assert "cambió de tenant" in str(error)
    else:
        raise AssertionError("Importación aceptó una inclusión de otro tenant.")

    proveedor_fierro = crear_proveedor(
        {"codigo": "PROV-UAT", "razon_social": "Proveedor Fierro UAT"},
        organizacion_id=organizacion_id,
        ProveedorCompra=modulo.ProveedorCompra,
        db_session=db.session,
    )
    orden_fierro = crear_orden(
        {
            "numero": "OC-UAT-1",
            "cantidad": "2",
            "precio_unitario": "1000",
            "descripcion": "Chapa UAT",
            "unidad_medida": "kg",
        },
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_id,
        proveedor=proveedor_fierro,
        insumo=insumo_fierro,
        OrdenCompra=modulo.OrdenCompra,
        OrdenCompraItem=modulo.OrdenCompraItem,
        db_session=db.session,
        usuario_id=usuario.id,
    )
    assert orden_fierro.total_centavos == 200000
    try:
        crear_orden(
            {
                "numero": "OC-CRUZADA-UAT",
                "cantidad": "1",
                "precio_unitario": "1",
                "descripcion": "No permitido",
                "unidad_medida": "u",
            },
            organizacion_id=organizacion_nautica.id,
            unidad_negocio_id=unidad_nautica.id,
            proveedor=proveedor_fierro,
            insumo=None,
            OrdenCompra=modulo.OrdenCompra,
            OrdenCompraItem=modulo.OrdenCompraItem,
            db_session=db.session,
        )
    except ValueError as error:
        assert "tenant activo" in str(error)
    else:
        raise AssertionError("Compras aceptó un proveedor de otro tenant.")

    costo_fierro = crear_version_costo(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_id,
        producto_id=producto_fierro.id,
        moneda="ARS",
        tipo="manual",
        detalles=[{
            "tipo": "insumo",
            "concepto": "Chapa UAT",
            "cantidad": "2",
            "unidad_medida": "kg",
            "costo_unitario_centavos": 100000,
            "orden": 0,
        }],
        Organizacion=modulo.Organizacion,
        UnidadNegocio=modulo.UnidadNegocio,
        Producto=modulo.Producto,
        CostoProductoVersion=modulo.CostoProductoVersion,
        CostoProductoDetalle=modulo.CostoProductoDetalle,
        db_session=db.session,
    )
    assert costo_fierro.costo_total_centavos == 200000
    try:
        crear_version_costo(
            organizacion_id=organizacion_nautica.id,
            unidad_negocio_id=unidad_nautica.id,
            producto_id=producto_fierro.id,
            moneda="ARS",
            tipo="manual",
            detalles=[{
                "tipo": "insumo", "concepto": "Cruce", "cantidad": "1",
                "unidad_medida": "u", "costo_unitario_centavos": 1,
            }],
            Organizacion=modulo.Organizacion,
            UnidadNegocio=modulo.UnidadNegocio,
            Producto=modulo.Producto,
            CostoProductoVersion=modulo.CostoProductoVersion,
            CostoProductoDetalle=modulo.CostoProductoDetalle,
            db_session=db.session,
        )
    except ValueError as error:
        assert "no pertenece" in str(error)
    else:
        raise AssertionError("Costos aceptó un producto de otro tenant.")

    costo_fierro.vigente = True
    costo_fierro.estado = "vigente"
    db.session.commit()
    empleado_fierro = modulo.EmpleadoProductivo(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_id,
        codigo="SOLDADOR-UAT", nombre="Soldador UAT", sector="Producción",
        tipo_registro="empleado", porcentaje_indirecto=0, activo=True,
    )
    perfil_produccion = modulo.PerfilCosteoProducto(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_id,
        producto_id=producto_fierro.id, tipo="produccion", activo=True,
    )
    db.session.add_all([empleado_fierro, perfil_produccion])
    db.session.flush()
    db.session.add_all([
        modulo.ProductoInsumoCosteo(
            perfil_costeo_id=perfil_produccion.id, insumo_id=insumo_fierro.id,
            cantidad=2, porcentaje_merma=0,
        ),
        modulo.ProductoOperacionCosteo(
            perfil_costeo_id=perfil_produccion.id, empleado_id=empleado_fierro.id,
            nombre="Soldadura UAT", minutos=15, orden=1,
        ),
    ])
    db.session.commit()
    orden_produccion = crear_orden_preparatoria(
        {"numero": "OP-UAT-1", "cantidad": "3"},
        perfil=perfil_produccion, version_costo=costo_fierro,
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_id,
        modelos={
            "OrdenProduccion": modulo.OrdenProduccion,
            "OrdenProduccionInsumo": modulo.OrdenProduccionInsumo,
            "OrdenProduccionOperacion": modulo.OrdenProduccionOperacion,
            "OrdenProduccionMaquina": modulo.OrdenProduccionMaquina,
        },
        db_session=db.session, usuario_id=usuario.id,
    )
    assert orden_produccion.impacta_inventario is False
    assert orden_produccion.ejecucion_habilitada is False
    try:
        crear_orden_preparatoria(
            {"numero": "OP-CRUZADA-UAT", "cantidad": "1"},
            perfil=perfil_produccion,
            version_costo=SimpleNamespace(
                id=999, vigente=True, costo_total_centavos=1,
                organizacion_id=organizacion_nautica.id,
                unidad_negocio_id=unidad_id, producto_id=producto_fierro.id,
            ),
            organizacion_id=organizacion_id, unidad_negocio_id=unidad_id,
            modelos={
                "OrdenProduccion": modulo.OrdenProduccion,
                "OrdenProduccionInsumo": modulo.OrdenProduccionInsumo,
                "OrdenProduccionOperacion": modulo.OrdenProduccionOperacion,
                "OrdenProduccionMaquina": modulo.OrdenProduccionMaquina,
            },
            db_session=db.session, usuario_id=usuario.id,
        )
    except ValueError as error:
        assert "tenant activo" in str(error)
    else:
        raise AssertionError("Producción aceptó un costo de otro tenant.")

    cuenta_tesoreria = crear_cuenta_tesoreria(
        {"codigo": "CAJA-UAT", "nombre": "Caja UAT", "tipo": "caja"},
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_id,
        CuentaTesoreria=modulo.CuentaTesoreria,
        db_session=db.session, usuario_id=usuario.id,
    )
    proyeccion = crear_proyeccion(
        {
            "tipo": "egreso", "concepto": "Compra preparatoria UAT",
            "fecha_prevista": "2026-10-01", "importe": "1000,00",
            "referencia": "UAT-FIN-1",
        },
        cuenta=cuenta_tesoreria, organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_id,
        Movimiento=modulo.MovimientoTesoreriaProyectado,
        db_session=db.session, usuario_id=usuario.id,
    )
    assert proyeccion.confirmado is False and proyeccion.afecta_saldo is False
    try:
        crear_proyeccion(
            {
                "tipo": "egreso", "concepto": "Cruce UAT",
                "fecha_prevista": "2026-10-01", "importe": "1,00",
            },
            cuenta=cuenta_tesoreria, organizacion_id=organizacion_nautica.id,
            unidad_negocio_id=unidad_nautica.id,
            Movimiento=modulo.MovimientoTesoreriaProyectado,
            db_session=db.session, usuario_id=usuario.id,
        )
    except ValueError as error:
        assert "contexto activo" in str(error)
    else:
        raise AssertionError("Tesorería aceptó una cuenta de otro tenant.")

    cuenta_debe = crear_cuenta_contable(
        {"codigo": "5.1.1", "nombre": "Compras UAT", "naturaleza": "egreso"},
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_id,
        Cuenta=modulo.CuentaContable, db_session=db.session,
        usuario_id=usuario.id,
    )
    cuenta_haber = crear_cuenta_contable(
        {"codigo": "1.1.1", "nombre": "Caja UAT", "naturaleza": "activo"},
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_id,
        Cuenta=modulo.CuentaContable, db_session=db.session,
        usuario_id=usuario.id,
    )
    asiento = crear_borrador_contable(
        {
            "fecha": "2026-10-01", "concepto": "Compra UAT",
            "importe": "1000,00", "referencia": "UAT-CONT-1",
        },
        cuenta_debe=cuenta_debe, cuenta_haber=cuenta_haber,
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_id,
        Asiento=modulo.AsientoContableBorrador,
        db_session=db.session, usuario_id=usuario.id,
    )
    assert asiento.total_debe_centavos == asiento.total_haber_centavos
    assert asiento.contabilizado is False and asiento.afecta_saldos is False

    deposito_fierro_a = modulo.SucursalOperativa(
        organizacion_id=organizacion_id, codigo="deposito-a-uat",
        nombre="Depósito A UAT", activa=True, es_principal=True,
    )
    deposito_fierro_b = modulo.SucursalOperativa(
        organizacion_id=organizacion_id, codigo="deposito-b-uat",
        nombre="Depósito B UAT", activa=True, es_principal=False,
    )
    deposito_nautica = modulo.SucursalOperativa(
        organizacion_id=organizacion_nautica.id, codigo="deposito-a-uat",
        nombre="Depósito Náutica UAT", activa=True, es_principal=True,
    )
    item_fierro = modulo.ItemInventario(
        organizacion_id=organizacion_id, producto_id=producto_fierro.id,
        catalogo_producto_id=inclusion_fierro.id, sku="SKU-COMPARTIDO-UAT",
        nombre="Producto Fierro UAT", tipo="producto", activo=True,
    )
    item_fierro_alternativo = modulo.ItemInventario(
        organizacion_id=organizacion_id, producto_id=producto_fierro.id,
        catalogo_producto_id=inclusion_fierro.id, sku="SKU-OTRO-UAT",
        nombre="Otro SKU del mismo producto", tipo="variante", activo=True,
    )
    item_nautica = modulo.ItemInventario(
        organizacion_id=organizacion_nautica.id, producto_id=producto_nautica.id,
        catalogo_producto_id=inclusion_nautica.id, sku="SKU-COMPARTIDO-UAT",
        nombre="Producto Náutica UAT", tipo="producto", activo=True,
    )
    db.session.add_all([
        deposito_fierro_a, deposito_fierro_b, deposito_nautica,
        item_fierro, item_fierro_alternativo, item_nautica,
    ])
    db.session.flush()
    existencia_fierro_a = modulo.ExistenciaSucursal(
        organizacion_id=organizacion_id,
        sucursal_operativa_id=deposito_fierro_a.id,
        producto_id=producto_fierro.id, item_inventario_id=item_fierro.id,
        stock_actual=10, stock_reservado=0, stock_bloqueado=0,
        stock_transito=0, stock_minimo=0, control_activo=True,
    )
    existencia_fierro_b = modulo.ExistenciaSucursal(
        organizacion_id=organizacion_id,
        sucursal_operativa_id=deposito_fierro_b.id,
        producto_id=producto_fierro.id, item_inventario_id=item_fierro.id,
        stock_actual=0, stock_reservado=0, stock_bloqueado=0,
        stock_transito=0, stock_minimo=0, control_activo=True,
    )
    existencia_otro_sku = modulo.ExistenciaSucursal(
        organizacion_id=organizacion_id,
        sucursal_operativa_id=deposito_fierro_b.id,
        producto_id=producto_fierro.id,
        item_inventario_id=item_fierro_alternativo.id,
        stock_actual=0, stock_reservado=0, stock_bloqueado=0,
        stock_transito=0, stock_minimo=0, control_activo=True,
    )
    existencia_nautica = modulo.ExistenciaSucursal(
        organizacion_id=organizacion_nautica.id,
        sucursal_operativa_id=deposito_nautica.id,
        producto_id=producto_nautica.id, item_inventario_id=item_nautica.id,
        stock_actual=10, stock_reservado=0, stock_bloqueado=0,
        stock_transito=0, stock_minimo=0, control_activo=True,
    )
    db.session.add_all([
        existencia_fierro_a, existencia_fierro_b,
        existencia_otro_sku, existencia_nautica,
    ])
    db.session.commit()

    reserva = crear_reserva(
        existencia_fierro_a, canal="laboratorio", referencia_externa="UAT-1",
        clave_idempotencia="fierro-uat-reserva-1", cantidad=2,
        ReservaInventario=modulo.ReservaInventario,
        MovimientoInventario=modulo.MovimientoInventario,
        db_session=db.session, usuario="admin-uat",
    )
    assert existencia_fierro_a.stock_reservado == 2
    cerrar_reserva(
        reserva, estado="liberada",
        MovimientoInventario=modulo.MovimientoInventario,
        db_session=db.session, usuario="admin-uat",
    )
    assert existencia_fierro_a.stock_reservado == 0

    transferencia_otro_sku = modulo.TransferenciaInventario(
        organizacion_id=organizacion_id, codigo="TR-SKU-UAT",
        origen=existencia_fierro_a, destino=existencia_otro_sku,
        cantidad_solicitada=1, motivo="Prueba", estado="borrador",
    )
    try:
        validar_transferencia(transferencia_otro_sku)
    except ValueError as error:
        assert "mismo SKU" in str(error)
    else:
        raise AssertionError("Inventario transfirió entre SKU diferentes.")

    transferencia_cruzada = modulo.TransferenciaInventario(
        organizacion_id=organizacion_id, codigo="TR-TENANT-UAT",
        origen=existencia_fierro_a, destino=existencia_nautica,
        cantidad_solicitada=1, motivo="Prueba", estado="borrador",
    )
    try:
        validar_transferencia(transferencia_cruzada)
    except ValueError as error:
        assert "otra organización" in str(error)
    else:
        raise AssertionError("Inventario aceptó una transferencia entre tenants.")

    conteo_alterado = modulo.ConteoInventario(
        organizacion_id=organizacion_id,
        sucursal_operativa_id=deposito_fierro_a.id,
        codigo="CONTEO-ALTERADO-UAT", estado="contado",
    )
    conteo_alterado.items.append(modulo.ConteoInventarioItem(
        existencia=existencia_nautica, cantidad_esperada=10,
        cantidad_contada=9,
    ))
    try:
        conciliar_conteo(
            conteo_alterado, MovimientoInventario=modulo.MovimientoInventario,
            db_session=db.session, usuario="admin-uat",
        )
    except ValueError as error:
        assert "otra organización" in str(error)
    else:
        raise AssertionError("Conteo aceptó una existencia de otro tenant.")
    db.session.rollback()


with aplicacion.app_context():
    modelos_crm = {
        "ClienteCRM": modulo.ClienteCRM,
        "ClienteIdentidadCanal": modulo.ClienteIdentidadCanal,
        "EtapaCRM": modulo.EtapaCRM,
        "OportunidadCRM": modulo.OportunidadCRM,
        "ActividadCRM": modulo.ActividadCRM,
        "UnidadNegocio": modulo.UnidadNegocio,
    }
    organizacion_fierro = modulo.Organizacion.query.get(ids[1])
    organizacion_nautica = modulo.Organizacion.query.get(nautica_ids[0])
    procesar_accion_crm_admin(
        "crear_cliente",
        {"codigo": "cliente-compartido", "nombre": "Cliente Fierro UAT",
         "unidad_negocio_id": str(ids[2])},
        organizacion=organizacion_fierro, modelos=modelos_crm,
        db_session=db.session, usuario="admin-uat",
    )
    procesar_accion_crm_admin(
        "crear_cliente",
        {"codigo": "cliente-compartido", "nombre": "Cliente Náutica UAT",
         "unidad_negocio_id": str(nautica_ids[1])},
        organizacion=organizacion_nautica, modelos=modelos_crm,
        db_session=db.session, usuario="admin-uat",
    )
    cliente_fierro = modulo.ClienteCRM.query.filter_by(
        organizacion_id=ids[1], codigo="cliente-compartido"
    ).one()
    cliente_nautica = modulo.ClienteCRM.query.filter_by(
        organizacion_id=nautica_ids[0], codigo="cliente-compartido"
    ).one()
    for organizacion_actual, cliente_actual in (
        (organizacion_fierro, cliente_fierro),
        (organizacion_nautica, cliente_nautica),
    ):
        procesar_accion_crm_admin(
            "agregar_identidad",
            {"cliente_id": str(cliente_actual.id), "canal": "whatsapp",
             "identificador_externo": "+5491100000000"},
            organizacion=organizacion_actual, modelos=modelos_crm,
            db_session=db.session, usuario="admin-uat",
        )
    assert modulo.ClienteIdentidadCanal.query.filter_by(
        canal="whatsapp", identificador_externo="+5491100000000"
    ).count() == 2
    try:
        procesar_accion_crm_admin(
            "crear_oportunidad",
            {"cliente_id": str(cliente_fierro.id), "titulo": "Cruce no permitido"},
            organizacion=organizacion_nautica, modelos=modelos_crm,
            db_session=db.session, usuario="admin-uat",
        )
    except ValueError as error:
        assert "organización" in str(error)
    else:
        raise AssertionError("CRM aceptó un cliente de otro tenant.")

    pedido_fierro = modulo.Pedido(
        organizacion_id=ids[1], unidad_negocio_id=ids[2],
        cliente="Cliente Fierro UAT", canal="laboratorio", id_venta="UAT-PV-1",
    )
    pedido_nautica = modulo.Pedido(
        organizacion_id=nautica_ids[0], unidad_negocio_id=nautica_ids[1],
        cliente="Cliente Náutica UAT", canal="laboratorio", id_venta="UAT-PV-1",
    )
    db.session.add_all([pedido_fierro, pedido_nautica])
    db.session.commit()
    caso_fierro = crear_caso(
        {"tipo": "garantia", "titulo": "Prueba UAT",
         "descripcion": "Caso interno de laboratorio sin efectos."},
        pedido=pedido_fierro, organizacion_id=ids[1], unidad_negocio_id=ids[2],
        Caso=modulo.CasoPostventa, db_session=db.session, usuario_id=ids[0],
    )
    assert not caso_fierro.contacto_externo and not caso_fierro.afecta_stock
    try:
        proponer_resolucion(
            {"tipo_resolucion": "reintegro", "detalle": "Cruce bloqueado",
             "importe_centavos": "1000"},
            caso=caso_fierro, pedido=pedido_nautica,
            organizacion_id=ids[1], unidad_negocio_id=ids[2],
            Propuesta=modulo.PropuestaResolucionPostventa,
            db_session=db.session,
        )
    except ValueError as error:
        assert "contexto activo" in str(error)
    else:
        raise AssertionError("Postventa aceptó un pedido de otro tenant.")
    producto_fierro_actual = modulo.Producto.query.filter_by(
        organizacion_id=ids[1], sku="SKU-COMPARTIDO-UAT"
    ).one()
    item_postventa = agregar_item(
        {"cantidad": "1", "condicion": "sin_recibir",
         "detalle_item": "Sólo documentado para UAT"},
        caso=caso_fierro, pedido=pedido_fierro, producto=producto_fierro_actual,
        organizacion_id=ids[1], unidad_negocio_id=ids[2],
        Item=modulo.ItemCasoPostventa, db_session=db.session,
    )
    assert item_postventa.recibido is False and item_postventa.afecta_stock is False


def _red_no_debe_invocarse(*_args, **_kwargs):
    raise AssertionError("El modo laboratorio intentó abrir la red para IPC.")


with aplicacion.app_context():
    try:
        actualizar_indices_oficiales(
            desde=__import__("datetime").date(2026, 1, 1),
            hasta=__import__("datetime").date(2026, 2, 1),
            IndiceIPCOficial=modulo.IndiceIPCOficial,
            db_session=db.session,
            urlopen_fn=_red_no_debe_invocarse,
        )
    except RuntimeError as error:
        assert "bloqueada" in str(error)
    else:
        raise AssertionError("La consulta IPC no fue bloqueada.")

cliente = aplicacion.test_client()
with cliente.session_transaction() as sesion:
    sesion["user_id"] = ids[0]
    sesion["username"] = "admin-uat"
    sesion["organizacion_id"] = ids[1]
    sesion["unidad_negocio_id"] = ids[2]

respuesta_segura = cliente.get("/login", base_url="https://localhost")
assert respuesta_segura.headers["X-Content-Type-Options"] == "nosniff"
assert respuesta_segura.headers["X-Frame-Options"] == "DENY"
assert "Content-Security-Policy" in respuesta_segura.headers

aplicacion.config["TESTING"] = False
respuesta_sin_csrf = cliente.post(
    "/whatsapp/respuestas-rapidas/nueva",
    data={"titulo": "No debe crearse", "texto": "sin token"},
    base_url="https://localhost",
)
assert respuesta_sin_csrf.status_code == 400
aplicacion.config["TESTING"] = True

with cliente.session_transaction() as sesion:
    sesion["organizacion_id"] = nautica_ids[0]
    sesion["unidad_negocio_id"] = nautica_ids[1]

panel_nautica = cliente.get(
    "/whatsapp/respuestas-rapidas",
    base_url="https://localhost",
)
assert panel_nautica.status_code == 200
assert b"SECRETO_FIERRO_UAT" not in panel_nautica.data
edicion_cruzada = cliente.post(
    f"/whatsapp/respuestas-rapidas/{respuesta_fierro_id}/editar",
    data={"titulo": "Intrusión", "texto": "No modificar"},
    base_url="https://localhost",
)
assert edicion_cruzada.status_code == 404
toggle_cruzado = cliente.post(
    f"/whatsapp/respuestas-rapidas/{respuesta_fierro_id}/toggle",
    base_url="https://localhost",
)
assert toggle_cruzado.status_code == 404

with cliente.session_transaction() as sesion:
    sesion["organizacion_id"] = ids[1]
    sesion["unidad_negocio_id"] = ids[2]

contenido_imagen = BytesIO()
Image.new("RGB", (8, 8), "red").save(contenido_imagen, format="PNG")
contenido_imagen.seek(0)
imagen_guardada = guardar_imagen_local(
    FileStorage(stream=contenido_imagen, filename="producto.png"),
    organizacion_id=ids[1],
    espacio="catalogo_prueba",
    limite_bytes=1024 * 1024,
)
respuesta_imagen = cliente.get(imagen_guardada["url"], base_url="https://localhost")
assert respuesta_imagen.status_code == 200
assert respuesta_imagen.mimetype == "image/png"
respuesta_otro_tenant = cliente.get(
    imagen_guardada["url"].replace(f"/{ids[1]}/", "/999999/"),
    base_url="https://localhost",
)
assert respuesta_otro_tenant.status_code == 404

revisadas = 0
for regla in sorted(aplicacion.url_map.iter_rules(), key=lambda item: item.rule):
    if (
        "GET" not in regla.methods
        or regla.arguments
        or regla.endpoint == "static"
        or regla.rule == "/logout"
    ):
        continue
    respuesta = cliente.get(
        regla.rule,
        base_url="https://localhost",
        follow_redirects=False,
    )
    assert respuesta.status_code < 500, (
        regla.rule,
        respuesta.status_code,
        respuesta.get_data(as_text=True)[:500],
    )
    revisadas += 1

assert revisadas >= 100, revisadas
print(f"RUNTIME_SMOKE_OK rutas={revisadas}")
