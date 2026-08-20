"""
Operaciones manuales del inventario multisucursal.

No recibe eventos de pedidos ni publica stock en canales.
"""

from services.inventario_nucleo import (
    registrar_movimiento,
)
from services.inventario_saas import (
    cerrar_reserva,
    conciliar_conteo,
    crear_reserva,
    despachar_transferencia,
    preparar_items_catalogo,
    recibir_transferencia,
)
from services.inventario_operaciones_admin import procesar_operacion_inventario


def _texto(formulario, nombre, limite=500):
    return str(
        formulario.get(nombre)
        or ""
    ).strip()[:limite]


def _entero(
    formulario,
    nombre,
    *,
    opcional=False,
):
    valor = _texto(
        formulario,
        nombre,
        30,
    )

    if opcional and not valor:
        return None

    try:
        return int(valor)
    except ValueError as error:
        raise ValueError(
            f"El campo {nombre} no es válido."
        ) from error


def _id(formulario, nombre):
    identificador = _entero(
        formulario,
        nombre,
    )

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


def procesar_accion_inventario_admin(
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

    ExistenciaSucursal = modelos[
        "ExistenciaSucursal"
    ]
    MovimientoInventario = modelos[
        "MovimientoInventario"
    ]
    PoliticaDisponibilidadCatalogo = modelos[
        "PoliticaDisponibilidadCatalogo"
    ]
    SucursalOperativa = modelos[
        "SucursalOperativa"
    ]
    Producto = modelos["Producto"]
    CatalogoProducto = modelos[
        "CatalogoProducto"
    ]
    ItemInventario = modelos["ItemInventario"]
    ReservaInventario = modelos["ReservaInventario"]
    TransferenciaInventario = modelos["TransferenciaInventario"]
    ConteoInventario = modelos["ConteoInventario"]
    ConteoInventarioItem = modelos["ConteoInventarioItem"]

    resultado_v2 = procesar_operacion_inventario(
        accion, formulario, organizacion=organizacion, modelos=modelos,
        db_session=db_session, usuario=usuario,
    )
    if resultado_v2 is not None:
        return resultado_v2

    if accion == "crear_existencia":
        sucursal = _obtener(
            SucursalOperativa,
            _id(
                formulario,
                "sucursal_operativa_id",
            ),
            "la sucursal",
        )
        _misma_organizacion(
            organizacion,
            sucursal,
            "La sucursal",
        )

        producto = _obtener(
            Producto,
            _id(
                formulario,
                "producto_id",
            ),
            "el producto",
        )

        existente = (
            ExistenciaSucursal.query
            .filter_by(
                sucursal_operativa_id=(
                    sucursal.id
                ),
                producto_id=producto.id,
            )
            .first()
        )

        if existente is not None:
            raise ValueError(
                "Ese producto ya tiene una existencia "
                "en la sucursal."
            )

        minimo = _entero(
            formulario,
            "stock_minimo",
        )
        maximo = _entero(
            formulario,
            "stock_maximo",
            opcional=True,
        )

        if minimo < 0:
            raise ValueError(
                "El stock mínimo no puede ser negativo."
            )

        if maximo is not None:
            if maximo < 0:
                raise ValueError(
                    "El stock máximo no puede "
                    "ser negativo."
                )
            if maximo < minimo:
                raise ValueError(
                    "El stock máximo no puede ser "
                    "menor al mínimo."
                )

        existencia = ExistenciaSucursal(
            organizacion_id=organizacion.id,
            sucursal_operativa_id=sucursal.id,
            producto_id=producto.id,
            stock_actual=0,
            stock_reservado=0,
            stock_minimo=minimo,
            stock_maximo=maximo,
            control_activo=False,
        )
        db_session.add(existencia)
        _guardar(db_session)

        return (
            "Existencia creada con stock cero "
            "y control desactivado."
        )

    if accion == "toggle_control_existencia":
        existencia = _obtener(
            ExistenciaSucursal,
            _id(
                formulario,
                "existencia_id",
            ),
            "la existencia",
        )
        _misma_organizacion(
            organizacion,
            existencia,
            "La existencia",
        )

        existencia.control_activo = not bool(
            existencia.control_activo
        )
        _guardar(db_session)

        return (
            "Control de stock activado."
            if existencia.control_activo
            else "Control de stock desactivado."
        )

    if accion == "registrar_movimiento":
        existencia = _obtener(
            ExistenciaSucursal,
            _id(
                formulario,
                "existencia_id",
            ),
            "la existencia",
        )
        _misma_organizacion(
            organizacion,
            existencia,
            "La existencia",
        )

        registrar_movimiento(
            existencia,
            tipo=_texto(
                formulario,
                "tipo",
                30,
            ),
            cantidad=_entero(
                formulario,
                "cantidad",
            ),
            motivo=_texto(
                formulario,
                "motivo",
                300,
            ),
            referencia=_texto(
                formulario,
                "referencia",
                150,
            ),
            usuario=usuario,
            MovimientoInventario=(
                MovimientoInventario
            ),
            db_session=db_session,
        )

        return "Movimiento registrado."

    if accion == "crear_politica_disponibilidad":
        inclusion = _obtener(
            CatalogoProducto,
            _id(
                formulario,
                "catalogo_producto_id",
            ),
            "el producto de catálogo",
        )

        catalogo = getattr(
            inclusion,
            "catalogo",
            None,
        )

        if catalogo is None:
            raise ValueError(
                "El producto no tiene catálogo."
            )

        _misma_organizacion(
            organizacion,
            catalogo,
            "El catálogo",
        )

        sucursal = _obtener(
            SucursalOperativa,
            _id(
                formulario,
                "sucursal_operativa_id",
            ),
            "la sucursal",
        )
        _misma_organizacion(
            organizacion,
            sucursal,
            "La sucursal",
        )

        existente = (
            PoliticaDisponibilidadCatalogo.query
            .filter_by(
                catalogo_producto_id=inclusion.id,
                sucursal_operativa_id=sucursal.id,
            )
            .first()
        )

        if existente is not None:
            raise ValueError(
                "Ya existe una política para ese "
                "producto y sucursal."
            )

        umbral = _entero(
            formulario,
            "umbral_publicacion",
        )
        maximo = _entero(
            formulario,
            "maximo_publicable",
            opcional=True,
        )
        dias = _entero(
            formulario,
            "dias_preparacion",
        )

        if umbral < 0:
            raise ValueError(
                "El umbral no puede ser negativo."
            )
        if maximo is not None and maximo < 0:
            raise ValueError(
                "El máximo publicable no puede "
                "ser negativo."
            )
        if dias < 0:
            raise ValueError(
                "Los días de preparación no pueden "
                "ser negativos."
            )

        politica = PoliticaDisponibilidadCatalogo(
            organizacion_id=organizacion.id,
            catalogo_producto_id=inclusion.id,
            sucursal_operativa_id=sucursal.id,
            activa=False,
            permite_sin_stock=False,
            umbral_publicacion=umbral,
            maximo_publicable=maximo,
            dias_preparacion=dias,
        )
        db_session.add(politica)
        _guardar(db_session)

        return (
            "Política creada como desactivada "
            "y sin venta sin stock."
        )

    if accion == "actualizar_politica_disponibilidad":
        politica = _obtener(
            PoliticaDisponibilidadCatalogo,
            _id(formulario, "politica_id"),
            "la política",
        )
        _misma_organizacion(
            organizacion,
            politica,
            "La política",
        )

        umbral = _entero(
            formulario,
            "umbral_publicacion",
        )
        maximo = _entero(
            formulario,
            "maximo_publicable",
            opcional=True,
        )
        dias = _entero(
            formulario,
            "dias_preparacion",
        )

        if umbral < 0:
            raise ValueError(
                "El umbral no puede ser negativo."
            )
        if maximo is not None and maximo < 0:
            raise ValueError(
                "El máximo publicable no puede ser negativo."
            )
        if dias < 0:
            raise ValueError(
                "Los días de preparación no pueden ser negativos."
            )

        activar = _texto(
            formulario,
            "activa",
            5,
        ) == "1"
        if activar and _texto(
            formulario,
            "confirmacion",
            30,
        ).upper() != "PREVISUALIZAR":
            raise ValueError(
                "Para activar la vista previa escribí PREVISUALIZAR."
            )

        politica.umbral_publicacion = umbral
        politica.maximo_publicable = maximo
        politica.dias_preparacion = dias
        politica.activa = activar
        # La sobreventa permanece bloqueada durante esta etapa.
        politica.permite_sin_stock = False
        _guardar(db_session)

        return (
            "Política guardada para vista previa. "
            "La publicación externa continúa bloqueada."
        )

    if accion == "toggle_politica":
        politica = _obtener(
            PoliticaDisponibilidadCatalogo,
            _id(
                formulario,
                "politica_id",
            ),
            "la política",
        )
        _misma_organizacion(
            organizacion,
            politica,
            "La política",
        )

        campo = _texto(
            formulario,
            "campo",
            30,
        )


        if campo == "activa":
            activar = not bool(politica.activa)
            if activar and _texto(
                formulario,
                "confirmacion",
                30,
            ).upper() != "PREVISUALIZAR":
                raise ValueError(
                    "Para activar la vista previa escribí PREVISUALIZAR."
                )
            politica.activa = activar
            mensaje = (
                "Política activada."
                if politica.activa
                else "Política desactivada."
            )
        elif campo == "permite_sin_stock":
            politica.permite_sin_stock = False
            raise ValueError(
                "La venta sin stock permanece bloqueada "
                "durante esta etapa."
            )
        else:
            raise ValueError(
                "La propiedad de la política "
                "no es válida."
            )

        _guardar(db_session)
        return mensaje

    raise ValueError(
        "La acción de inventario no es válida."
    )
