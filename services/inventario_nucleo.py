"""
Reglas puras de inventario multisucursal.

No importa pedidos ni sincroniza stock con canales.
"""


TIPO_INGRESO = "ingreso"
TIPO_EGRESO = "egreso"
TIPO_AJUSTE = "ajuste"
TIPO_RESERVA = "reserva"
TIPO_LIBERACION = "liberacion"

TIPOS_MOVIMIENTO = frozenset(
    {
        TIPO_INGRESO,
        TIPO_EGRESO,
        TIPO_AJUSTE,
        TIPO_RESERVA,
        TIPO_LIBERACION,
    }
)


def _entero(valor, nombre):
    try:
        return int(
            str(valor).strip()
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            f"{nombre} no es válido."
        ) from error


def stock_disponible(existencia):
    if existencia is None:
        return 0

    actual = _entero(
        getattr(
            existencia,
            "stock_actual",
            0,
        ),
        "El stock actual",
    )
    reservado = _entero(
        getattr(
            existencia,
            "stock_reservado",
            0,
        ),
        "El stock reservado",
    )

    return actual - reservado


def validar_existencia(existencia):
    if existencia is None:
        raise ValueError(
            "No se recibió la existencia."
        )

    actual = _entero(
        getattr(
            existencia,
            "stock_actual",
            0,
        ),
        "El stock actual",
    )
    reservado = _entero(
        getattr(
            existencia,
            "stock_reservado",
            0,
        ),
        "El stock reservado",
    )

    if actual < 0:
        raise ValueError(
            "El stock actual no puede ser negativo."
        )

    if reservado < 0:
        raise ValueError(
            "El stock reservado no puede ser negativo."
        )

    if reservado > actual:
        raise ValueError(
            "El stock reservado no puede superar "
            "el stock actual."
        )

    return True


def aplicar_movimiento(
    existencia,
    tipo,
    cantidad,
):
    """
    Aplica en memoria un movimiento validado.

    Devuelve la fotografía anterior y posterior para
    crear el registro de auditoría en la misma transacción.
    """
    validar_existencia(existencia)

    tipo = str(
        tipo or ""
    ).strip().lower()

    if tipo not in TIPOS_MOVIMIENTO:
        raise ValueError(
            "Tipo de movimiento inválido."
        )

    cantidad = _entero(
        cantidad,
        "La cantidad",
    )

    if tipo != TIPO_AJUSTE and cantidad <= 0:
        raise ValueError(
            "La cantidad debe ser mayor que cero."
        )

    if tipo == TIPO_AJUSTE and cantidad == 0:
        raise ValueError(
            "El ajuste no puede ser cero."
        )

    actual_anterior = int(
        existencia.stock_actual
    )
    reservado_anterior = int(
        existencia.stock_reservado
    )

    if tipo == TIPO_INGRESO:
        existencia.stock_actual += cantidad

    elif tipo == TIPO_EGRESO:
        if stock_disponible(existencia) < cantidad:
            raise ValueError(
                "No hay stock disponible suficiente "
                "para el egreso."
            )
        existencia.stock_actual -= cantidad

    elif tipo == TIPO_AJUSTE:
        existencia.stock_actual += cantidad

    elif tipo == TIPO_RESERVA:
        if stock_disponible(existencia) < cantidad:
            raise ValueError(
                "No hay stock disponible suficiente "
                "para reservar."
            )
        existencia.stock_reservado += cantidad

    elif tipo == TIPO_LIBERACION:
        if existencia.stock_reservado < cantidad:
            raise ValueError(
                "No se puede liberar más stock "
                "del reservado."
            )
        existencia.stock_reservado -= cantidad

    validar_existencia(existencia)

    return {
        "stock_actual_anterior": actual_anterior,
        "stock_actual_nuevo": int(
            existencia.stock_actual
        ),
        "stock_reservado_anterior": (
            reservado_anterior
        ),
        "stock_reservado_nuevo": int(
            existencia.stock_reservado
        ),
    }


def registrar_movimiento(
    existencia,
    *,
    tipo,
    cantidad,
    motivo,
    MovimientoInventario,
    db_session,
    referencia="",
    usuario="sistema",
):
    if not str(
        motivo or ""
    ).strip():
        raise ValueError(
            "El movimiento necesita un motivo."
        )

    fotografia = aplicar_movimiento(
        existencia,
        tipo,
        cantidad,
    )

    movimiento = MovimientoInventario(
        organizacion_id=existencia.organizacion_id,
        existencia_sucursal_id=existencia.id,
        tipo=str(tipo).strip().lower(),
        cantidad=int(cantidad),
        motivo=str(motivo).strip()[:300],
        referencia=str(
            referencia or ""
        ).strip()[:150],
        usuario=str(
            usuario or "sistema"
        ).strip()[:100],
        **fotografia,
    )

    db_session.add(movimiento)

    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise

    return movimiento


def cantidad_publicable(
    existencia,
    politica,
):
    """
    Cálculo futuro, sin publicar datos externamente.
    """
    if (
        existencia is None
        or politica is None
        or not bool(
            getattr(
                existencia,
                "control_activo",
                False,
            )
        )
        or not bool(
            getattr(
                politica,
                "activa",
                False,
            )
        )
    ):
        return 0

    disponible = max(
        stock_disponible(existencia),
        0,
    )
    umbral = max(
        _entero(
            getattr(
                politica,
                "umbral_publicacion",
                0,
            ),
            "El umbral",
        ),
        0,
    )

    if disponible <= umbral:
        if bool(
            getattr(
                politica,
                "permite_sin_stock",
                False,
            )
        ):
            return 1
        return 0

    publicable = disponible - umbral
    maximo = getattr(
        politica,
        "maximo_publicable",
        None,
    )

    if maximo is not None:
        publicable = min(
            publicable,
            max(
                _entero(
                    maximo,
                    "El máximo publicable",
                ),
                0,
            ),
        )

    return max(publicable, 0)


def inventario_habilita_sincronizacion(
    modulo_inventario,
):
    """
    Guardia explícita: aún activo no sincroniza canales.
    """
    return False
