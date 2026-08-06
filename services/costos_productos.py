"""
Servicios del dominio historico de costos de productos.

Este modulo no publica precios ni se conecta con canales, pedidos,
inventario o facturacion.
"""

from decimal import Decimal
from decimal import InvalidOperation
from decimal import ROUND_HALF_UP

from sqlalchemy import func

from services.fechas import ahora_utc_naive


TIPOS_COSTO = {
    "manual",
    "calculado",
}

ESTADOS_COSTO = {
    "preparatorio",
    "vigente",
    "archivado",
    "cancelado",
}

TIPOS_DETALLE_COSTO = {
    "insumo",
    "mano_obra",
    "elaboracion",
    "flete_entrada",
}


def _normalizar_opcion(valor, opciones, campo):
    normalizado = str(valor or "").strip().lower()

    if normalizado not in opciones:
        raise ValueError(
            f"{campo} invalido: "
            f"{normalizado or '(vacio)'}."
        )

    return normalizado


def normalizar_moneda(moneda):
    normalizada = str(moneda or "").strip().upper()

    if len(normalizada) != 3 or not normalizada.isalpha():
        raise ValueError(
            "La moneda debe tener tres letras."
        )

    return normalizada


def decimal_no_negativo(valor, campo):
    try:
        numero = Decimal(str(valor).strip())
    except (
        InvalidOperation,
        AttributeError,
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            f"{campo} no es valido."
        ) from error

    if not numero.is_finite() or numero < 0:
        raise ValueError(
            f"{campo} no puede ser negativo."
        )

    return numero


def entero_no_negativo(valor, campo):
    try:
        numero = int(valor)
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            f"{campo} no es valido."
        ) from error

    if numero < 0:
        raise ValueError(
            f"{campo} no puede ser negativo."
        )

    return numero


def calcular_subtotal_detalle(
    *,
    cantidad,
    costo_unitario_centavos,
    porcentaje_merma=0,
):
    cantidad_decimal = decimal_no_negativo(
        cantidad,
        "La cantidad",
    )
    costo_unitario = entero_no_negativo(
        costo_unitario_centavos,
        "El costo unitario",
    )
    merma = decimal_no_negativo(
        porcentaje_merma,
        "El porcentaje de merma",
    )

    if merma > Decimal("100"):
        raise ValueError(
            "El porcentaje de merma no puede "
            "superar 100."
        )

    subtotal = (
        cantidad_decimal
        * Decimal(costo_unitario)
        * (
            Decimal("1")
            + merma / Decimal("100")
        )
    )

    return int(
        subtotal.quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def preparar_detalles(detalles):
    if not detalles:
        raise ValueError(
            "La version de costo requiere detalles."
        )

    preparados = []

    for posicion, detalle in enumerate(detalles):
        tipo = _normalizar_opcion(
            detalle.get("tipo"),
            TIPOS_DETALLE_COSTO,
            "Tipo de detalle",
        )
        concepto = str(
            detalle.get("concepto") or ""
        ).strip()

        if not concepto:
            raise ValueError(
                "Cada detalle requiere un concepto."
            )

        cantidad = decimal_no_negativo(
            detalle.get("cantidad"),
            "La cantidad",
        )
        merma = decimal_no_negativo(
            detalle.get("porcentaje_merma", 0),
            "El porcentaje de merma",
        )

        if merma > Decimal("100"):
            raise ValueError(
                "El porcentaje de merma no puede "
                "superar 100."
            )

        costo_unitario = entero_no_negativo(
            detalle.get(
                "costo_unitario_centavos"
            ),
            "El costo unitario",
        )
        orden = entero_no_negativo(
            detalle.get("orden", posicion),
            "El orden",
        )
        subtotal = calcular_subtotal_detalle(
            cantidad=cantidad,
            costo_unitario_centavos=costo_unitario,
            porcentaje_merma=merma,
        )

        preparados.append({
            "tipo": tipo,
            "codigo": (
                str(detalle.get("codigo") or "").strip()
                or None
            ),
            "concepto": concepto,
            "cantidad": cantidad,
            "unidad_medida": (
                str(
                    detalle.get("unidad_medida")
                    or ""
                ).strip()
            ),
            "costo_unitario_centavos": costo_unitario,
            "porcentaje_merma": merma,
            "subtotal_centavos": subtotal,
            "observacion": (
                str(
                    detalle.get("observacion")
                    or ""
                ).strip()
                or None
            ),
            "orden": orden,
        })

    if any(
        not detalle["unidad_medida"]
        for detalle in preparados
    ):
        raise ValueError(
            "Cada detalle requiere unidad de medida."
        )

    ordenes = [
        detalle["orden"]
        for detalle in preparados
    ]

    if len(ordenes) != len(set(ordenes)):
        raise ValueError(
            "Los ordenes de detalle no pueden repetirse."
        )

    return preparados


def validar_alcance_costo(
    *,
    organizacion_id,
    unidad_negocio_id,
    producto_id,
    Organizacion,
    UnidadNegocio,
    Producto,
    db_session,
):
    organizacion = db_session.get(
        Organizacion,
        organizacion_id,
    )

    if organizacion is None:
        raise ValueError(
            "La organizacion indicada no existe."
        )

    producto = db_session.get(
        Producto,
        producto_id,
    )

    if producto is None:
        raise ValueError(
            "El producto indicado no existe."
        )

    unidad = None

    if unidad_negocio_id is not None:
        unidad = db_session.get(
            UnidadNegocio,
            unidad_negocio_id,
        )

        if unidad is None:
            raise ValueError(
                "La unidad de negocio indicada no existe."
            )

        if int(unidad.organizacion_id) != int(
            organizacion_id
        ):
            raise ValueError(
                "La unidad no pertenece a la organizacion."
            )

    return organizacion, unidad, producto


def crear_version_costo(
    *,
    organizacion_id,
    unidad_negocio_id,
    producto_id,
    moneda,
    tipo,
    detalles,
    creado_por_usuario_id=None,
    creado_por_username=None,
    observacion=None,
    Organizacion,
    UnidadNegocio,
    Producto,
    CostoProductoVersion,
    CostoProductoDetalle,
    db_session,
    commit=True,
):
    validar_alcance_costo(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        producto_id=producto_id,
        Organizacion=Organizacion,
        UnidadNegocio=UnidadNegocio,
        Producto=Producto,
        db_session=db_session,
    )

    moneda_normalizada = normalizar_moneda(moneda)
    tipo_normalizado = _normalizar_opcion(
        tipo,
        TIPOS_COSTO,
        "Tipo de costo",
    )
    detalles_preparados = preparar_detalles(
        detalles
    )

    consulta_version = db_session.query(
        func.max(
            CostoProductoVersion.numero_version
        )
    ).filter(
        CostoProductoVersion.organizacion_id
        == organizacion_id,
        CostoProductoVersion.producto_id
        == producto_id,
        CostoProductoVersion.moneda
        == moneda_normalizada,
    )

    if unidad_negocio_id is None:
        consulta_version = consulta_version.filter(
            CostoProductoVersion.unidad_negocio_id
            .is_(None)
        )
    else:
        consulta_version = consulta_version.filter(
            CostoProductoVersion.unidad_negocio_id
            == unidad_negocio_id
        )

    ultima_version = consulta_version.scalar() or 0

    version = CostoProductoVersion(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        producto_id=producto_id,
        moneda=moneda_normalizada,
        tipo=tipo_normalizado,
        numero_version=ultima_version + 1,
        costo_total_centavos=sum(
            detalle["subtotal_centavos"]
            for detalle in detalles_preparados
        ),
        estado="preparatorio",
        vigente=False,
        creado_por_usuario_id=(
            creado_por_usuario_id
        ),
        creado_por_username=(
            str(creado_por_username or "").strip()
            or None
        ),
        observacion=(
            str(observacion or "").strip()
            or None
        ),
    )

    try:
        db_session.add(version)
        db_session.flush()

        for detalle in detalles_preparados:
            db_session.add(
                CostoProductoDetalle(
                    costo_producto_version_id=version.id,
                    **detalle,
                )
            )

        if commit:
            db_session.commit()
    except Exception:
        db_session.rollback()
        raise

    return version


def activar_version_costo(
    version,
    *,
    CostoProductoVersion,
    db_session,
    ahora_fn=ahora_utc_naive,
    commit=True,
):
    if version is None:
        raise ValueError(
            "No se recibio una version de costo."
        )

    if version.estado not in {
        "preparatorio",
        "archivado",
    }:
        raise ValueError(
            "La version no puede activarse "
            "desde su estado actual."
        )

    momento = ahora_fn()

    consulta = CostoProductoVersion.query.filter(
        CostoProductoVersion.organizacion_id
        == version.organizacion_id,
        CostoProductoVersion.producto_id
        == version.producto_id,
        CostoProductoVersion.moneda
        == version.moneda,
        CostoProductoVersion.vigente.is_(True),
        CostoProductoVersion.id != version.id,
    )

    if version.unidad_negocio_id is None:
        consulta = consulta.filter(
            CostoProductoVersion.unidad_negocio_id
            .is_(None)
        )
    else:
        consulta = consulta.filter(
            CostoProductoVersion.unidad_negocio_id
            == version.unidad_negocio_id
        )

    try:
        for anterior in consulta.all():
            anterior.vigente = False
            anterior.estado = "archivado"
            anterior.vigente_hasta = momento

        version.vigente = True
        version.estado = "vigente"
        version.vigente_desde = momento
        version.vigente_hasta = None

        if commit:
            db_session.commit()
    except Exception:
        db_session.rollback()
        raise

    return version


def historial_costos(
    *,
    organizacion_id,
    producto_id,
    moneda,
    unidad_negocio_id,
    CostoProductoVersion,
):
    consulta = CostoProductoVersion.query.filter(
        CostoProductoVersion.organizacion_id
        == organizacion_id,
        CostoProductoVersion.producto_id
        == producto_id,
        CostoProductoVersion.moneda
        == normalizar_moneda(moneda),
    )

    if unidad_negocio_id is None:
        consulta = consulta.filter(
            CostoProductoVersion.unidad_negocio_id
            .is_(None)
        )
    else:
        consulta = consulta.filter(
            CostoProductoVersion.unidad_negocio_id
            == unidad_negocio_id
        )

    return consulta.order_by(
        CostoProductoVersion.numero_version.desc()
    ).all()
