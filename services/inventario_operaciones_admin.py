"""Flujos administrativos de inventario v2, sin automatizar canales."""

from services.inventario_saas import (
    cerrar_reserva,
    conciliar_conteo,
    crear_reserva,
    despachar_transferencia,
    preparar_items_catalogo,
    recibir_transferencia,
)


ACCIONES = {
    "actualizar_modulo_inventario", "actualizar_ubicacion", "actualizar_item",
    "crear_ubicacion", "preparar_items_catalogo", "crear_existencia_item",
    "crear_reserva", "cerrar_reserva", "crear_transferencia",
    "despachar_transferencia", "recibir_transferencia", "crear_conteo",
    "guardar_conteo", "conciliar_conteo",
}


def _texto(formulario, nombre, limite=300):
    return str(formulario.get(nombre) or "").strip()[:limite]


def _entero(formulario, nombre, opcional=False):
    texto = _texto(formulario, nombre, 30)
    if opcional and not texto:
        return None
    try:
        return int(texto)
    except (TypeError, ValueError) as error:
        raise ValueError(f"El campo {nombre} no es válido.") from error


def _registro(Modelo, identificador, nombre):
    registro = Modelo.query.get(identificador)
    if registro is None:
        raise ValueError(f"No se encontró {nombre}.")
    return registro


def _tenant(organizacion, registro, nombre):
    if int(getattr(registro, "organizacion_id", 0) or 0) != int(organizacion.id):
        raise ValueError(f"{nombre} no pertenece a la organización.")


def _guardar(db_session):
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise


def procesar_operacion_inventario(
    accion, formulario, *, organizacion, modelos, db_session, usuario,
):
    if accion not in ACCIONES:
        return None
    Sucursal = modelos["SucursalOperativa"]
    Catalogo = modelos["Catalogo"]
    CatalogoProducto = modelos["CatalogoProducto"]
    Existencia = modelos["ExistenciaSucursal"]
    Movimiento = modelos["MovimientoInventario"]
    Item = modelos["ItemInventario"]
    Reserva = modelos["ReservaInventario"]
    Transferencia = modelos["TransferenciaInventario"]
    Conteo = modelos["ConteoInventario"]
    ConteoItem = modelos["ConteoInventarioItem"]
    Modulo = modelos["ModuloOrganizacion"]

    if accion == "actualizar_modulo_inventario":
        modulo = Modulo.query.filter_by(
            organizacion_id=organizacion.id, codigo="inventario-sucursales",
        ).first()
        if modulo is None:
            raise ValueError("No se encontró la configuración del módulo.")
        estado = _texto(formulario, "estado", 20)
        if estado not in {"activo", "desactivado"}:
            raise ValueError("El estado del módulo no es válido.")
        if estado == "activo" and _texto(formulario, "confirmacion", 20) != "ACTIVAR":
            raise ValueError("Escribí ACTIVAR para habilitar el módulo.")
        modulo.estado = estado
        _guardar(db_session)
        return f"Módulo de inventario {estado}. La sincronización sigue bloqueada."

    if accion == "actualizar_ubicacion":
        sucursal = _registro(Sucursal, _entero(formulario, "sucursal_operativa_id"), "la ubicación")
        _tenant(organizacion, sucursal, "La ubicación")
        activa = _texto(formulario, "activa", 1) == "1"
        principal = _texto(formulario, "es_principal", 1) == "1"
        modulo = Modulo.query.filter_by(
            organizacion_id=organizacion.id, codigo="inventario-sucursales",
        ).first()
        if activa and (modulo is None or modulo.estado != "activo"):
            raise ValueError("Activá primero el módulo de inventario.")
        if sucursal.activa and not activa:
            existencias = Existencia.query.filter_by(
                organizacion_id=organizacion.id,
                sucursal_operativa_id=sucursal.id,
            ).all()
            if any(
                e.control_activo or int(e.stock_actual or 0) or
                int(e.stock_reservado or 0) or int(e.stock_bloqueado or 0) or
                int(e.stock_transito or 0)
                for e in existencias
            ):
                raise ValueError("La ubicación tiene stock o controles activos y no puede desactivarse.")
        nombre = _texto(formulario, "nombre", 150)
        if not nombre:
            raise ValueError("La ubicación necesita un nombre.")
        sucursal.nombre = nombre
        sucursal.direccion = _texto(formulario, "direccion", 250) or None
        sucursal.localidad = _texto(formulario, "localidad", 120) or None
        sucursal.provincia = _texto(formulario, "provincia", 120) or None
        sucursal.codigo_postal = _texto(formulario, "codigo_postal", 20) or None
        sucursal.activa = activa
        if principal:
            for otra in Sucursal.query.filter_by(organizacion_id=organizacion.id).all():
                otra.es_principal = otra.id == sucursal.id
        else:
            sucursal.es_principal = False
        _guardar(db_session)
        return f"Ubicación {sucursal.nombre} actualizada."

    if accion == "actualizar_item":
        item = _registro(Item, _entero(formulario, "item_inventario_id"), "el SKU")
        _tenant(organizacion, item, "El SKU")
        activo = _texto(formulario, "activo", 1) == "1"
        modulo = Modulo.query.filter_by(
            organizacion_id=organizacion.id, codigo="inventario-sucursales",
        ).first()
        if activo and (modulo is None or modulo.estado != "activo"):
            raise ValueError("Activá primero el módulo de inventario.")
        if item.activo and not activo:
            existencias = Existencia.query.filter_by(
                organizacion_id=organizacion.id, item_inventario_id=item.id,
            ).all()
            if any(
                e.control_activo or int(e.stock_actual or 0) or
                int(e.stock_reservado or 0) or int(e.stock_bloqueado or 0) or
                int(e.stock_transito or 0)
                for e in existencias
            ):
                raise ValueError("El SKU tiene stock o controles activos y no puede desactivarse.")
        item.activo = activo
        _guardar(db_session)
        return f"SKU {item.sku} {'activado' if activo else 'desactivado'}."

    if accion == "crear_ubicacion":
        codigo, nombre = _texto(formulario, "codigo", 80).lower(), _texto(formulario, "nombre", 150)
        if not codigo or not nombre:
            raise ValueError("Completá código y nombre de la ubicación.")
        if Sucursal.query.filter_by(organizacion_id=organizacion.id, codigo=codigo).first():
            raise ValueError("Ya existe una ubicación con ese código.")
        db_session.add(Sucursal(
            organizacion_id=organizacion.id, codigo=codigo, nombre=nombre,
            direccion=_texto(formulario, "direccion", 250) or None,
            localidad=_texto(formulario, "localidad", 120) or None,
            provincia=_texto(formulario, "provincia", 120) or None,
            codigo_postal=_texto(formulario, "codigo_postal", 20) or None,
            es_principal=False, activa=False,
        ))
        _guardar(db_session)
        return "Ubicación creada desactivada."

    if accion == "preparar_items_catalogo":
        inclusiones = CatalogoProducto.query.join(Catalogo).filter(
            Catalogo.organizacion_id == organizacion.id
        ).all()
        creados = preparar_items_catalogo(
            organizacion.id, inclusiones, ItemInventario=Item, db_session=db_session,
        )
        return f"SKU preparados: {creados} nuevos; todos desactivados."

    if accion == "crear_existencia_item":
        sucursal = _registro(Sucursal, _entero(formulario, "sucursal_operativa_id"), "la ubicación")
        item = _registro(Item, _entero(formulario, "item_inventario_id"), "el SKU")
        _tenant(organizacion, sucursal, "La ubicación")
        _tenant(organizacion, item, "El SKU")
        if Existencia.query.filter_by(
            sucursal_operativa_id=sucursal.id, item_inventario_id=item.id
        ).first():
            raise ValueError("Ese SKU ya tiene existencia en la ubicación.")
        minimo = _entero(formulario, "stock_minimo")
        maximo = _entero(formulario, "stock_maximo", opcional=True)
        if minimo < 0 or (maximo is not None and maximo < minimo):
            raise ValueError("Revisá los límites mínimo y máximo.")
        db_session.add(Existencia(
            organizacion_id=organizacion.id, sucursal_operativa_id=sucursal.id,
            producto_id=item.producto_id, item_inventario_id=item.id,
            stock_actual=0, stock_reservado=0, stock_bloqueado=0,
            stock_transito=0, stock_minimo=minimo, stock_maximo=maximo,
            control_activo=False,
        ))
        _guardar(db_session)
        return "Existencia creada en cero y con control desactivado."

    if accion == "crear_reserva":
        existencia = _registro(Existencia, _entero(formulario, "existencia_id"), "la existencia")
        _tenant(organizacion, existencia, "La existencia")
        reserva = crear_reserva(
            existencia, canal=_texto(formulario, "canal", 50),
            referencia_externa=_texto(formulario, "referencia", 150),
            clave_idempotencia=_texto(formulario, "clave_idempotencia", 180),
            cantidad=_entero(formulario, "cantidad"),
            motivo=_texto(formulario, "motivo") or "Reserva manual",
            ReservaInventario=Reserva, MovimientoInventario=Movimiento,
            db_session=db_session, usuario=usuario,
        )
        return f"Reserva #{reserva.id} registrada sin publicar stock."

    if accion == "cerrar_reserva":
        reserva = _registro(Reserva, _entero(formulario, "reserva_id"), "la reserva")
        _tenant(organizacion, reserva, "La reserva")
        estado = _texto(formulario, "estado", 30)
        cerrar_reserva(
            reserva, estado=estado, MovimientoInventario=Movimiento,
            db_session=db_session, usuario=usuario,
        )
        return f"Reserva {estado}."

    if accion == "crear_transferencia":
        origen = _registro(Existencia, _entero(formulario, "origen_id"), "el origen")
        destino = _registro(Existencia, _entero(formulario, "destino_id"), "el destino")
        _tenant(organizacion, origen, "El origen")
        _tenant(organizacion, destino, "El destino")
        codigo = _texto(formulario, "codigo", 100)
        cantidad = _entero(formulario, "cantidad")
        if not codigo or cantidad <= 0:
            raise ValueError("Completá código y cantidad positiva.")
        db_session.add(Transferencia(
            organizacion_id=organizacion.id, codigo=codigo,
            existencia_origen_id=origen.id, existencia_destino_id=destino.id,
            cantidad_solicitada=cantidad,
            motivo=_texto(formulario, "motivo") or "Transferencia interna",
            estado="borrador", usuario_solicita=usuario,
        ))
        _guardar(db_session)
        return f"Transferencia {codigo} creada en borrador."

    if accion in {"despachar_transferencia", "recibir_transferencia"}:
        transferencia = _registro(
            Transferencia, _entero(formulario, "transferencia_id"), "la transferencia"
        )
        _tenant(organizacion, transferencia, "La transferencia")
        if accion == "despachar_transferencia":
            despachar_transferencia(
                transferencia, MovimientoInventario=Movimiento,
                db_session=db_session, usuario=usuario,
            )
            return "Transferencia despachada."
        recibir_transferencia(
            transferencia, _entero(formulario, "cantidad_recibida"),
            MovimientoInventario=Movimiento, db_session=db_session, usuario=usuario,
        )
        return "Recepción registrada."

    if accion == "crear_conteo":
        sucursal = _registro(Sucursal, _entero(formulario, "sucursal_operativa_id"), "la ubicación")
        _tenant(organizacion, sucursal, "La ubicación")
        codigo = _texto(formulario, "codigo", 100)
        existencias = Existencia.query.filter_by(
            organizacion_id=organizacion.id, sucursal_operativa_id=sucursal.id,
        ).all()
        if not codigo or not existencias:
            raise ValueError("Indicá un código y una ubicación con existencias.")
        conteo = Conteo(
            organizacion_id=organizacion.id, sucursal_operativa_id=sucursal.id,
            codigo=codigo, estado="abierto",
            observacion=_texto(formulario, "observacion"), usuario_inicia=usuario,
        )
        db_session.add(conteo)
        db_session.flush()
        for existencia in existencias:
            db_session.add(ConteoItem(
                conteo_inventario_id=conteo.id,
                existencia_sucursal_id=existencia.id,
                cantidad_esperada=existencia.stock_actual,
            ))
        _guardar(db_session)
        return f"Inventario {codigo} abierto con fotografía de existencias."

    if accion == "guardar_conteo":
        conteo = _registro(Conteo, _entero(formulario, "conteo_id"), "el inventario")
        _tenant(organizacion, conteo, "El inventario")
        ids = formulario.getlist("conteo_item_id")
        cantidades = formulario.getlist("cantidad_contada")
        por_id = {int(item.id): item for item in conteo.items}
        if len(ids) != len(cantidades) or not ids:
            raise ValueError("El conteo está incompleto.")
        for identificador, valor in zip(ids, cantidades):
            item = por_id.get(int(identificador))
            cantidad = int(valor)
            if item is None or cantidad < 0:
                raise ValueError("El renglón contado no es válido.")
            item.cantidad_contada = cantidad
            item.diferencia = cantidad - item.cantidad_esperada
        conteo.estado = "contado"
        _guardar(db_session)
        return "Conteo guardado; todavía no ajustó stock."

    conteo = _registro(Conteo, _entero(formulario, "conteo_id"), "el inventario")
    _tenant(organizacion, conteo, "El inventario")
    conciliar_conteo(
        conteo, MovimientoInventario=Movimiento,
        db_session=db_session, usuario=usuario,
    )
    return "Inventario conciliado con ajustes auditados."
