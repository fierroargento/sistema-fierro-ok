"""
Operaciones manuales del panel CRM interno.

No importa pedidos, no consulta APIs y no envía mensajes.
"""

from datetime import datetime

from services.crm_nucleo import (
    cambiar_estado_oportunidad,
    configurar_importe_oportunidad,
    fecha_opcional,
    normalizar_canal_identidad,
    normalizar_estado_cliente,
    normalizar_tipo_actividad,
    normalizar_tipo_cliente,
    validar_probabilidad,
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


def procesar_accion_crm_admin(
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

    ClienteCRM = modelos["ClienteCRM"]
    ClienteIdentidadCanal = modelos[
        "ClienteIdentidadCanal"
    ]
    EtapaCRM = modelos["EtapaCRM"]
    OportunidadCRM = modelos[
        "OportunidadCRM"
    ]
    ActividadCRM = modelos["ActividadCRM"]
    UnidadNegocio = modelos[
        "UnidadNegocio"
    ]

    if accion == "crear_etapa":
        codigo = _texto(
            formulario,
            "codigo",
            80,
        ).lower()
        nombre = _texto(
            formulario,
            "nombre",
            150,
        )

        if not codigo or not nombre:
            raise ValueError(
                "Completá código y nombre de la etapa."
            )

        if (
            EtapaCRM.query
            .filter_by(
                organizacion_id=organizacion.id,
                codigo=codigo,
            )
            .first()
            is not None
        ):
            raise ValueError(
                "Ya existe una etapa con ese código."
            )

        try:
            orden = int(
                _texto(
                    formulario,
                    "orden",
                    20,
                )
                or "0"
            )
        except ValueError as error:
            raise ValueError(
                "El orden de la etapa no es válido."
            ) from error

        etapa = EtapaCRM(
            organizacion_id=organizacion.id,
            codigo=codigo,
            nombre=nombre,
            orden=orden,
            color=(
                _texto(
                    formulario,
                    "color",
                    20,
                )
                or "#64748b"
            ),
            activa=False,
        )
        db_session.add(etapa)
        _guardar(db_session)

        return "Etapa creada como desactivada."

    if accion == "toggle_etapa":
        etapa = _obtener(
            EtapaCRM,
            _id(
                formulario,
                "etapa_id",
            ),
            "la etapa",
        )
        _misma_organizacion(
            organizacion,
            etapa,
            "La etapa",
        )
        etapa.activa = not bool(
            etapa.activa
        )
        _guardar(db_session)

        return (
            "Etapa activada."
            if etapa.activa
            else "Etapa desactivada."
        )

    if accion == "crear_cliente":
        codigo = _texto(
            formulario,
            "codigo",
            80,
        ).lower()
        nombre = _texto(
            formulario,
            "nombre",
            200,
        )

        if not codigo or not nombre:
            raise ValueError(
                "Completá código y nombre del cliente."
            )

        if (
            ClienteCRM.query
            .filter_by(
                organizacion_id=organizacion.id,
                codigo=codigo,
            )
            .first()
            is not None
        ):
            raise ValueError(
                "Ya existe un cliente con ese código."
            )

        unidad_id = _opcional_id(
            formulario,
            "unidad_negocio_id",
        )
        unidad = None

        if unidad_id is not None:
            unidad = _obtener(
                UnidadNegocio,
                unidad_id,
                "la unidad de negocio",
            )
            _misma_organizacion(
                organizacion,
                unidad,
                "La unidad de negocio",
            )

        cliente = ClienteCRM(
            organizacion_id=organizacion.id,
            unidad_negocio_id=(
                unidad.id
                if unidad is not None
                else None
            ),
            codigo=codigo,
            nombre=nombre,
            tipo=normalizar_tipo_cliente(
                _texto(
                    formulario,
                    "tipo",
                    30,
                )
                or "persona"
            ),
            documento=_texto(
                formulario,
                "documento",
                30,
            ),
            email=_texto(
                formulario,
                "email",
                200,
            ),
            telefono=_texto(
                formulario,
                "telefono",
                50,
            ),
            localidad=_texto(
                formulario,
                "localidad",
                120,
            ),
            provincia=_texto(
                formulario,
                "provincia",
                120,
            ),
            origen=_texto(
                formulario,
                "origen",
                50,
            ),
            observaciones=_texto(
                formulario,
                "observaciones",
                2000,
            ),
            estado=normalizar_estado_cliente(
                _texto(
                    formulario,
                    "estado",
                    30,
                )
                or "potencial"
            ),
            activo=False,
        )
        db_session.add(cliente)
        _guardar(db_session)

        return "Cliente CRM creado como desactivado."

    if accion == "toggle_cliente":
        cliente = _obtener(
            ClienteCRM,
            _id(
                formulario,
                "cliente_id",
            ),
            "el cliente",
        )
        _misma_organizacion(
            organizacion,
            cliente,
            "El cliente",
        )
        cliente.activo = not bool(
            cliente.activo
        )
        _guardar(db_session)

        return (
            "Cliente activado."
            if cliente.activo
            else "Cliente desactivado."
        )

    if accion == "agregar_identidad":
        cliente = _obtener(
            ClienteCRM,
            _id(
                formulario,
                "cliente_id",
            ),
            "el cliente",
        )
        _misma_organizacion(
            organizacion,
            cliente,
            "El cliente",
        )

        canal = normalizar_canal_identidad(
            _texto(
                formulario,
                "canal",
                30,
            )
        )
        identificador = _texto(
            formulario,
            "identificador_externo",
            150,
        )

        if not identificador:
            raise ValueError(
                "Ingresá el identificador externo."
            )

        existente = (
            ClienteIdentidadCanal.query
            .filter_by(
                organizacion_id=organizacion.id,
                canal=canal,
                identificador_externo=(
                    identificador
                ),
            )
            .first()
        )

        if existente is not None:
            raise ValueError(
                "Esa identidad ya está registrada."
            )

        identidad = ClienteIdentidadCanal(
            organizacion_id=organizacion.id,
            cliente_crm_id=cliente.id,
            canal=canal,
            identificador_externo=identificador,
            alias=_texto(
                formulario,
                "alias",
                150,
            ),
            detalle=_texto(
                formulario,
                "detalle",
                500,
            ),
            activo=False,
        )
        db_session.add(identidad)
        _guardar(db_session)

        return "Identidad agregada como desactivada."

    if accion == "toggle_identidad":
        identidad = _obtener(
            ClienteIdentidadCanal,
            _id(
                formulario,
                "identidad_id",
            ),
            "la identidad",
        )

        _misma_organizacion(
            organizacion,
            identidad,
            "La identidad",
        )

        cliente = _obtener(
            ClienteCRM,
            identidad.cliente_crm_id,
            "el cliente de la identidad",
        )
        _misma_organizacion(
            organizacion,
            cliente,
            "El cliente",
        )

        identidad.activo = not bool(
            identidad.activo
        )
        _guardar(db_session)

        return (
            "Identidad activada."
            if identidad.activo
            else "Identidad desactivada."
        )

    if accion == "crear_oportunidad":
        cliente = _obtener(
            ClienteCRM,
            _id(
                formulario,
                "cliente_id",
            ),
            "el cliente",
        )
        _misma_organizacion(
            organizacion,
            cliente,
            "El cliente",
        )

        titulo = _texto(
            formulario,
            "titulo",
            200,
        )

        if not titulo:
            raise ValueError(
                "Ingresá un título para la oportunidad."
            )

        unidad = None
        unidad_id = _opcional_id(
            formulario,
            "unidad_negocio_id",
        )

        if unidad_id is not None:
            unidad = _obtener(
                UnidadNegocio,
                unidad_id,
                "la unidad de negocio",
            )
            _misma_organizacion(
                organizacion,
                unidad,
                "La unidad de negocio",
            )

        etapa = None
        etapa_id = _opcional_id(
            formulario,
            "etapa_crm_id",
        )

        if etapa_id is not None:
            etapa = _obtener(
                EtapaCRM,
                etapa_id,
                "la etapa",
            )
            _misma_organizacion(
                organizacion,
                etapa,
                "La etapa",
            )

        oportunidad = OportunidadCRM(
            organizacion_id=organizacion.id,
            cliente_crm_id=cliente.id,
            unidad_negocio_id=(
                unidad.id
                if unidad is not None
                else None
            ),
            etapa_crm_id=(
                etapa.id
                if etapa is not None
                else None
            ),
            titulo=titulo,
            origen=_texto(
                formulario,
                "origen",
                50,
            ),
            estado="abierta",
            importe_estimado_centavos=0,
            probabilidad=validar_probabilidad(
                _texto(
                    formulario,
                    "probabilidad",
                    10,
                )
                or "0"
            ),
            fecha_cierre_estimada=(
                fecha_opcional(
                    _texto(
                        formulario,
                        "fecha_cierre_estimada",
                        20,
                    )
                )
            ),
            responsable=_texto(
                formulario,
                "responsable",
                100,
            ),
            detalle=_texto(
                formulario,
                "detalle",
                2000,
            ),
            activa=False,
        )

        configurar_importe_oportunidad(
            oportunidad,
            _texto(
                formulario,
                "importe_estimado",
                50,
            )
            or "0",
        )

        db_session.add(oportunidad)
        _guardar(db_session)

        return (
            "Oportunidad creada como desactivada."
        )

    if accion == "estado_oportunidad":
        oportunidad = _obtener(
            OportunidadCRM,
            _id(
                formulario,
                "oportunidad_id",
            ),
            "la oportunidad",
        )
        _misma_organizacion(
            organizacion,
            oportunidad,
            "La oportunidad",
        )

        cambiar_estado_oportunidad(
            oportunidad,
            _texto(
                formulario,
                "estado",
                30,
            ),
            db_session=db_session,
        )

        return "Estado de oportunidad actualizado."

    if accion == "toggle_oportunidad":
        oportunidad = _obtener(
            OportunidadCRM,
            _id(
                formulario,
                "oportunidad_id",
            ),
            "la oportunidad",
        )
        _misma_organizacion(
            organizacion,
            oportunidad,
            "La oportunidad",
        )
        oportunidad.activa = not bool(
            oportunidad.activa
        )
        _guardar(db_session)

        return (
            "Oportunidad activada."
            if oportunidad.activa
            else "Oportunidad desactivada."
        )

    if accion == "crear_actividad":
        cliente = _obtener(
            ClienteCRM,
            _id(
                formulario,
                "cliente_id",
            ),
            "el cliente",
        )
        _misma_organizacion(
            organizacion,
            cliente,
            "El cliente",
        )

        oportunidad = None
        oportunidad_id = _opcional_id(
            formulario,
            "oportunidad_crm_id",
        )

        if oportunidad_id is not None:
            oportunidad = _obtener(
                OportunidadCRM,
                oportunidad_id,
                "la oportunidad",
            )
            _misma_organizacion(
                organizacion,
                oportunidad,
                "La oportunidad",
            )

            if (
                oportunidad.cliente_crm_id
                != cliente.id
            ):
                raise ValueError(
                    "La oportunidad pertenece "
                    "a otro cliente."
                )

        asunto = _texto(
            formulario,
            "asunto",
            200,
        )

        if not asunto:
            raise ValueError(
                "Ingresá un asunto para la actividad."
            )

        actividad = ActividadCRM(
            organizacion_id=organizacion.id,
            cliente_crm_id=cliente.id,
            oportunidad_crm_id=(
                oportunidad.id
                if oportunidad is not None
                else None
            ),
            tipo=normalizar_tipo_actividad(
                _texto(
                    formulario,
                    "tipo",
                    30,
                )
                or "nota"
            ),
            asunto=asunto,
            detalle=_texto(
                formulario,
                "detalle",
                2000,
            ),
            estado="pendiente",
            fecha_vencimiento=fecha_opcional(
                _texto(
                    formulario,
                    "fecha_vencimiento",
                    20,
                )
            ),
            fecha_completada=None,
            creado_por=str(
                usuario or "admin"
            )[:100],
        )
        db_session.add(actividad)
        _guardar(db_session)

        return "Actividad CRM creada."

    if accion == "completar_actividad":
        actividad = _obtener(
            ActividadCRM,
            _id(
                formulario,
                "actividad_id",
            ),
            "la actividad",
        )
        _misma_organizacion(
            organizacion,
            actividad,
            "La actividad",
        )

        if actividad.estado == "completada":
            actividad.estado = "pendiente"
            actividad.fecha_completada = None
            mensaje = (
                "Actividad reabierta como pendiente."
            )
        else:
            actividad.estado = "completada"
            actividad.fecha_completada = (
                datetime.utcnow()
            )
            mensaje = "Actividad completada."

        _guardar(db_session)
        return mensaje

    raise ValueError(
        "La acción CRM no es válida."
    )
