"""
Administración fiscal preparatoria.

No llama servicios de ARCA, no importa pedidos y no emite CAE.
"""

from decimal import Decimal
from decimal import InvalidOperation

from services.catalogos_comerciales import (
    importe_a_centavos,
)
from services.facturacion_nucleo import (
    calcular_item_fiscal,
    cambiar_estado_borrador,
    normalizar_ambiente,
    recalcular_totales_borrador,
    validar_nombre_variable_entorno,
)


ESTADOS_CONFIGURACION = frozenset(
    {
        "desactivada",
        "configurada",
        "prueba",
    }
)


def _texto(formulario, nombre, limite=500):
    return str(
        formulario.get(nombre)
        or ""
    ).strip()[:limite]


def _id(formulario, nombre):
    valor = _texto(
        formulario,
        nombre,
        30,
    )

    try:
        identificador = int(valor)
    except ValueError as error:
        raise ValueError(
            f"El campo {nombre} no es válido."
        ) from error

    if identificador <= 0:
        raise ValueError(
            f"El campo {nombre} no es válido."
        )

    return identificador


def _opcional_id(formulario, nombre):
    valor = _texto(
        formulario,
        nombre,
        30,
    )

    if not valor:
        return None

    try:
        identificador = int(valor)
    except ValueError as error:
        raise ValueError(
            f"El campo {nombre} no es válido."
        ) from error

    if identificador <= 0:
        raise ValueError(
            f"El campo {nombre} no es válido."
        )

    return identificador


def _obtener(Modelo, identificador, nombre):
    registro = Modelo.query.get(
        identificador
    )

    if registro is None:
        raise ValueError(
            f"No se encontró {nombre}."
        )

    return registro


def _misma_organizacion(
    organizacion,
    registro,
    nombre,
):
    if (
        getattr(
            registro,
            "organizacion_id",
            None,
        )
        != organizacion.id
    ):
        raise ValueError(
            f"{nombre} no pertenece a la organización."
        )


def _guardar(db_session):
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise


def _crear_evento(
    EventoFiscal,
    db_session,
    *,
    tipo,
    usuario,
    detalle,
    organizacion_id,
    borrador_id=None,
    configuracion_id=None,
):
    evento = EventoFiscal(
        organizacion_id=organizacion_id,
        borrador_comprobante_fiscal_id=(
            borrador_id
        ),
        configuracion_fiscal_id=(
            configuracion_id
        ),
        tipo=str(tipo)[:50],
        detalle=str(detalle)[:2000],
        referencia_externa="",
        usuario=str(
            usuario or "admin"
        )[:100],
    )
    db_session.add(evento)
    return evento


def _alicuota_basis_points(valor):
    try:
        porcentaje = Decimal(
            str(valor).strip().replace(",", ".")
        )
    except (
        InvalidOperation,
        AttributeError,
        ValueError,
    ) as error:
        raise ValueError(
            "La alícuota IVA no es válida."
        ) from error

    if not 0 <= porcentaje <= 100:
        raise ValueError(
            "La alícuota IVA no es válida."
        )

    return int(
        porcentaje * Decimal("100")
    )


def procesar_accion_facturacion_admin(
    accion,
    formulario,
    *,
    organizacion,
    modelos,
    db_session,
    usuario="admin",
):
    accion = str(
        accion or ""
    ).strip().lower()

    ConfiguracionFiscal = modelos[
        "ConfiguracionFiscal"
    ]
    PuntoVentaFiscal = modelos[
        "PuntoVentaFiscal"
    ]
    TipoComprobanteFiscal = modelos[
        "TipoComprobanteFiscal"
    ]
    BorradorComprobanteFiscal = modelos[
        "BorradorComprobanteFiscal"
    ]
    BorradorItemFiscal = modelos[
        "BorradorItemFiscal"
    ]
    EventoFiscal = modelos["EventoFiscal"]
    EntidadFiscal = modelos["EntidadFiscal"]
    ClienteCRM = modelos["ClienteCRM"]

    if accion == "crear_configuracion":
        entidad = _obtener(
            EntidadFiscal,
            _id(
                formulario,
                "entidad_fiscal_id",
            ),
            "la entidad fiscal",
        )
        _misma_organizacion(
            organizacion,
            entidad,
            "La entidad fiscal",
        )

        if (
            ConfiguracionFiscal.query
            .filter_by(
                entidad_fiscal_id=entidad.id
            )
            .first()
            is not None
        ):
            raise ValueError(
                "La entidad fiscal ya tiene "
                "una configuración."
            )

        configuracion = ConfiguracionFiscal(
            organizacion_id=organizacion.id,
            entidad_fiscal_id=entidad.id,
            proveedor="arca",
            ambiente=normalizar_ambiente(
                _texto(
                    formulario,
                    "ambiente",
                    30,
                )
            ),
            certificado_env=(
                validar_nombre_variable_entorno(
                    _texto(
                        formulario,
                        "certificado_env",
                        120,
                    )
                )
            ),
            clave_privada_env=(
                validar_nombre_variable_entorno(
                    _texto(
                        formulario,
                        "clave_privada_env",
                        120,
                    )
                )
            ),
            token_env=(
                validar_nombre_variable_entorno(
                    _texto(
                        formulario,
                        "token_env",
                        120,
                    )
                )
            ),
            estado="desactivada",
            detalle=_texto(
                formulario,
                "detalle",
                500,
            ),
        )
        db_session.add(configuracion)
        _crear_evento(
            EventoFiscal,
            db_session,
            organizacion_id=organizacion.id,
            tipo="configuracion_creada",
            usuario=usuario,
            detalle=(
                "Configuración fiscal creada "
                "sin habilitar emisión."
            ),
        )
        _guardar(db_session)

        return (
            "Configuración fiscal creada "
            "como desactivada."
        )

    if accion == "estado_configuracion":
        configuracion = _obtener(
            ConfiguracionFiscal,
            _id(
                formulario,
                "configuracion_id",
            ),
            "la configuración fiscal",
        )
        _misma_organizacion(
            organizacion,
            configuracion,
            "La configuración fiscal",
        )

        estado = _texto(
            formulario,
            "estado",
            30,
        ).lower()

        if estado not in ESTADOS_CONFIGURACION:
            raise ValueError(
                "Estado de configuración inválido."
            )

        configuracion.estado = estado
        configuracion.detalle = _texto(
            formulario,
            "detalle",
            500,
        )
        _crear_evento(
            EventoFiscal,
            db_session,
            organizacion_id=organizacion.id,
            tipo="configuracion_estado",
            usuario=usuario,
            detalle=f"Nuevo estado: {estado}.",
            configuracion_id=configuracion.id,
        )
        _guardar(db_session)

        return (
            "Estado de configuración actualizado. "
            "La emisión real continúa bloqueada."
        )

    if accion == "crear_punto_venta":
        configuracion = _obtener(
            ConfiguracionFiscal,
            _id(
                formulario,
                "configuracion_fiscal_id",
            ),
            "la configuración fiscal",
        )
        _misma_organizacion(
            organizacion,
            configuracion,
            "La configuración fiscal",
        )

        entidad = configuracion.entidad_fiscal

        try:
            numero = int(
                _texto(
                    formulario,
                    "numero",
                    20,
                )
            )
        except ValueError as error:
            raise ValueError(
                "El número de punto de venta "
                "no es válido."
            ) from error

        if numero <= 0:
            raise ValueError(
                "El punto de venta debe ser "
                "mayor que cero."
            )

        if (
            PuntoVentaFiscal.query
            .filter_by(
                entidad_fiscal_id=entidad.id,
                numero=numero,
            )
            .first()
            is not None
        ):
            raise ValueError(
                "Ese punto de venta ya existe "
                "para la entidad fiscal."
            )

        nombre = _texto(
            formulario,
            "nombre",
            150,
        )

        if not nombre:
            raise ValueError(
                "Ingresá el nombre del punto de venta."
            )

        punto = PuntoVentaFiscal(
            organizacion_id=organizacion.id,
            entidad_fiscal_id=entidad.id,
            configuracion_fiscal_id=(
                configuracion.id
            ),
            numero=numero,
            nombre=nombre,
            estado="desactivado",
            emision_real_habilitada=False,
        )
        db_session.add(punto)
        _crear_evento(
            EventoFiscal,
            db_session,
            organizacion_id=organizacion.id,
            tipo="punto_venta_creado",
            usuario=usuario,
            detalle=(
                f"Punto de venta {numero} creado "
                "sin emisión real."
            ),
            configuracion_id=configuracion.id,
        )
        _guardar(db_session)

        return (
            "Punto de venta creado como desactivado."
        )

    if accion == "toggle_punto_venta":
        punto = _obtener(
            PuntoVentaFiscal,
            _id(
                formulario,
                "punto_venta_id",
            ),
            "el punto de venta",
        )
        _misma_organizacion(
            organizacion,
            punto,
            "El punto de venta",
        )

        if punto.estado == "activo":
            punto.estado = "desactivado"
        else:
            punto.estado = "activo"

        punto.emision_real_habilitada = False

        _crear_evento(
            EventoFiscal,
            db_session,
            organizacion_id=organizacion.id,
            tipo="punto_venta_estado",
            usuario=usuario,
            detalle=(
                f"Estado administrativo: "
                f"{punto.estado}. "
                "Emisión real: bloqueada."
            ),
            configuracion_id=(
                punto.configuracion_fiscal_id
            ),
        )
        _guardar(db_session)

        return (
            "Punto de venta actualizado. "
            "La emisión real permanece bloqueada."
        )

    if accion == "crear_tipo_comprobante":
        punto = _obtener(
            PuntoVentaFiscal,
            _id(
                formulario,
                "punto_venta_fiscal_id",
            ),
            "el punto de venta",
        )
        _misma_organizacion(
            organizacion,
            punto,
            "El punto de venta",
        )

        try:
            codigo_arca = int(
                _texto(
                    formulario,
                    "codigo_arca",
                    20,
                )
            )
        except ValueError as error:
            raise ValueError(
                "El código ARCA no es válido."
            ) from error

        if codigo_arca <= 0:
            raise ValueError(
                "El código ARCA debe ser positivo."
            )

        if (
            TipoComprobanteFiscal.query
            .filter_by(
                punto_venta_fiscal_id=punto.id,
                codigo_arca=codigo_arca,
            )
            .first()
            is not None
        ):
            raise ValueError(
                "Ese tipo ya existe para "
                "el punto de venta."
            )

        nombre = _texto(
            formulario,
            "nombre",
            150,
        )
        letra = _texto(
            formulario,
            "letra",
            5,
        ).upper()

        if not nombre or not letra:
            raise ValueError(
                "Completá nombre y letra."
            )

        tipo = TipoComprobanteFiscal(
            punto_venta_fiscal_id=punto.id,
            codigo_arca=codigo_arca,
            nombre=nombre,
            letra=letra,
            ultimo_numero_autorizado=0,
            activo=False,
        )
        db_session.add(tipo)
        _guardar(db_session)

        return (
            "Tipo de comprobante creado "
            "como desactivado."
        )

    if accion == "toggle_tipo_comprobante":
        tipo = _obtener(
            TipoComprobanteFiscal,
            _id(
                formulario,
                "tipo_comprobante_id",
            ),
            "el tipo de comprobante",
        )

        _misma_organizacion(
            organizacion,
            tipo.punto_venta,
            "El punto de venta",
        )

        tipo.activo = not bool(
            tipo.activo
        )
        _guardar(db_session)

        return (
            "Tipo de comprobante activado."
            if tipo.activo
            else "Tipo de comprobante desactivado."
        )

    if accion == "crear_borrador":
        entidad = _obtener(
            EntidadFiscal,
            _id(
                formulario,
                "entidad_fiscal_id",
            ),
            "la entidad fiscal",
        )
        _misma_organizacion(
            organizacion,
            entidad,
            "La entidad fiscal",
        )

        punto = _obtener(
            PuntoVentaFiscal,
            _id(
                formulario,
                "punto_venta_fiscal_id",
            ),
            "el punto de venta",
        )
        _misma_organizacion(
            organizacion,
            punto,
            "El punto de venta",
        )

        if punto.entidad_fiscal_id != entidad.id:
            raise ValueError(
                "El punto de venta pertenece "
                "a otra entidad fiscal."
            )

        tipo = _obtener(
            TipoComprobanteFiscal,
            _id(
                formulario,
                "tipo_comprobante_fiscal_id",
            ),
            "el tipo de comprobante",
        )

        if tipo.punto_venta_fiscal_id != punto.id:
            raise ValueError(
                "El tipo de comprobante pertenece "
                "a otro punto de venta."
            )

        cliente = None
        cliente_id = _opcional_id(
            formulario,
            "cliente_crm_id",
        )

        if cliente_id is not None:
            cliente = _obtener(
                ClienteCRM,
                cliente_id,
                "el cliente CRM",
            )
            _misma_organizacion(
                organizacion,
                cliente,
                "El cliente",
            )

        receptor_nombre = _texto(
            formulario,
            "receptor_nombre",
            200,
        )

        if not receptor_nombre:
            raise ValueError(
                "Ingresá el nombre del receptor."
            )

        borrador = BorradorComprobanteFiscal(
            organizacion_id=organizacion.id,
            entidad_fiscal_id=entidad.id,
            punto_venta_fiscal_id=punto.id,
            tipo_comprobante_fiscal_id=tipo.id,
            cliente_crm_id=(
                cliente.id
                if cliente is not None
                else None
            ),
            receptor_nombre=receptor_nombre,
            receptor_documento=_texto(
                formulario,
                "receptor_documento",
                30,
            ),
            receptor_condicion_iva=_texto(
                formulario,
                "receptor_condicion_iva",
                80,
            ),
            moneda=(
                _texto(
                    formulario,
                    "moneda",
                    10,
                ).upper()
                or "ARS"
            ),
            estado="borrador",
            neto_centavos=0,
            iva_centavos=0,
            otros_tributos_centavos=0,
            total_centavos=0,
            cae=None,
            numero_autorizado=None,
            creado_por=str(
                usuario or "admin"
            )[:100],
        )
        db_session.add(borrador)
        db_session.flush()

        _crear_evento(
            EventoFiscal,
            db_session,
            organizacion_id=organizacion.id,
            tipo="borrador_creado",
            usuario=usuario,
            detalle=(
                "Borrador creado sin relación "
                "con pedidos y sin emisión."
            ),
            borrador_id=borrador.id,
        )
        _guardar(db_session)

        return "Borrador fiscal creado."

    if accion == "agregar_item_borrador":
        borrador = _obtener(
            BorradorComprobanteFiscal,
            _id(
                formulario,
                "borrador_id",
            ),
            "el borrador",
        )
        _misma_organizacion(
            organizacion,
            borrador,
            "El borrador",
        )

        if borrador.estado != "borrador":
            raise ValueError(
                "Solo se pueden modificar "
                "borradores abiertos."
            )

        descripcion = _texto(
            formulario,
            "descripcion",
            300,
        )

        if not descripcion:
            raise ValueError(
                "Ingresá la descripción del ítem."
            )

        precio_centavos = importe_a_centavos(
            _texto(
                formulario,
                "precio_unitario",
                50,
            )
        )
        alicuota = _alicuota_basis_points(
            _texto(
                formulario,
                "alicuota_iva",
                20,
            )
        )
        calculo = calcular_item_fiscal(
            cantidad=_texto(
                formulario,
                "cantidad",
                30,
            ),
            precio_unitario_centavos=(
                precio_centavos
            ),
            alicuota_iva_basis_points=(
                alicuota
            ),
        )

        item = BorradorItemFiscal(
            borrador_comprobante_fiscal_id=(
                borrador.id
            ),
            descripcion=descripcion,
            sku=_texto(
                formulario,
                "sku",
                100,
            ),
            precio_unitario_centavos=(
                precio_centavos
            ),
            alicuota_iva_basis_points=(
                alicuota
            ),
            **calculo,
        )
        db_session.add(item)
        db_session.flush()

        recalcular_totales_borrador(
            borrador,
            list(borrador.items),
        )

        _crear_evento(
            EventoFiscal,
            db_session,
            organizacion_id=organizacion.id,
            tipo="item_agregado",
            usuario=usuario,
            detalle=(
                f"Ítem agregado: {descripcion}."
            ),
            borrador_id=borrador.id,
        )
        _guardar(db_session)

        return "Ítem agregado al borrador."

    if accion == "estado_borrador":
        borrador = _obtener(
            BorradorComprobanteFiscal,
            _id(
                formulario,
                "borrador_id",
            ),
            "el borrador",
        )
        _misma_organizacion(
            organizacion,
            borrador,
            "El borrador",
        )

        nuevo_estado = _texto(
            formulario,
            "estado",
            30,
        )

        cambiar_estado_borrador(
            borrador,
            nuevo_estado,
            db_session=db_session,
            commit=False,
        )

        _crear_evento(
            EventoFiscal,
            db_session,
            organizacion_id=organizacion.id,
            tipo="borrador_estado",
            usuario=usuario,
            detalle=(
                f"Nuevo estado: {nuevo_estado}."
            ),
            borrador_id=borrador.id,
        )
        _guardar(db_session)

        return (
            "Estado del borrador actualizado. "
            "No se emitió ningún comprobante."
        )

    raise ValueError(
        "La acción fiscal no es válida."
    )
