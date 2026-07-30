"""
Reglas puras de facturación multi-CUIT.

No conecta con ARCA y no importa pedidos.
"""

import re
from decimal import Decimal
from decimal import InvalidOperation
from decimal import ROUND_HALF_UP


AMBIENTE_HOMOLOGACION = "homologacion"
AMBIENTE_PRODUCCION = "produccion"

AMBIENTES_FISCALES = frozenset(
    {
        AMBIENTE_HOMOLOGACION,
        AMBIENTE_PRODUCCION,
    }
)

ESTADO_BORRADOR = "borrador"
ESTADO_LISTO = "listo"
ESTADO_CANCELADO = "cancelado"
ESTADO_AUTORIZADO = "autorizado"

ESTADOS_BORRADOR = frozenset(
    {
        ESTADO_BORRADOR,
        ESTADO_LISTO,
        ESTADO_CANCELADO,
        ESTADO_AUTORIZADO,
    }
)

TRANSICIONES_BORRADOR = {
    ESTADO_BORRADOR: {
        ESTADO_LISTO,
        ESTADO_CANCELADO,
    },
    ESTADO_LISTO: {
        ESTADO_BORRADOR,
        ESTADO_CANCELADO,
    },
    ESTADO_CANCELADO: set(),
    ESTADO_AUTORIZADO: set(),
}

PATRON_VARIABLE_ENTORNO = re.compile(
    r"^[A-Z][A-Z0-9_]{2,119}$"
)


def normalizar_ambiente(ambiente):
    normalizado = str(
        ambiente or ""
    ).strip().lower()

    if normalizado not in AMBIENTES_FISCALES:
        raise ValueError(
            "Ambiente fiscal inválido."
        )

    return normalizado


def validar_nombre_variable_entorno(
    nombre,
    *,
    obligatorio=False,
):
    texto = str(
        nombre or ""
    ).strip()

    if not texto:
        if obligatorio:
            raise ValueError(
                "Falta la variable de entorno requerida."
            )
        return ""

    if not PATRON_VARIABLE_ENTORNO.fullmatch(
        texto
    ):
        raise ValueError(
            "El nombre de la variable de entorno "
            "no es válido."
        )

    return texto


def cantidad_a_milesimas(cantidad):
    try:
        valor = Decimal(
            str(cantidad).strip().replace(",", ".")
        )
    except (
        InvalidOperation,
        AttributeError,
        ValueError,
    ) as error:
        raise ValueError(
            "La cantidad no es válida."
        ) from error

    if valor <= 0:
        raise ValueError(
            "La cantidad debe ser mayor que cero."
        )

    return int(
        (
            valor * Decimal("1000")
        ).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def calcular_item_fiscal(
    *,
    cantidad,
    precio_unitario_centavos,
    alicuota_iva_basis_points,
):
    cantidad_milesimas = (
        cantidad_a_milesimas(cantidad)
    )

    try:
        precio = int(
            precio_unitario_centavos
        )
        alicuota = int(
            alicuota_iva_basis_points
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "Precio o alícuota inválidos."
        ) from error

    if precio < 0:
        raise ValueError(
            "El precio no puede ser negativo."
        )

    if not 0 <= alicuota <= 10000:
        raise ValueError(
            "La alícuota IVA no es válida."
        )

    total = int(
        (
            Decimal(precio)
            * Decimal(cantidad_milesimas)
            / Decimal("1000")
        ).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )

    divisor = (
        Decimal("1")
        + Decimal(alicuota)
        / Decimal("10000")
    )

    neto = int(
        (
            Decimal(total) / divisor
        ).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )

    iva = total - neto

    return {
        "cantidad_milesimas": (
            cantidad_milesimas
        ),
        "neto_centavos": neto,
        "iva_centavos": iva,
        "total_centavos": total,
    }


def recalcular_totales_borrador(
    borrador,
    items,
):
    if borrador is None:
        raise ValueError(
            "No se recibió el borrador."
        )

    items = list(items or [])

    borrador.neto_centavos = sum(
        int(item.neto_centavos)
        for item in items
    )
    borrador.iva_centavos = sum(
        int(item.iva_centavos)
        for item in items
    )
    borrador.otros_tributos_centavos = int(
        getattr(
            borrador,
            "otros_tributos_centavos",
            0,
        )
        or 0
    )
    borrador.total_centavos = (
        borrador.neto_centavos
        + borrador.iva_centavos
        + borrador.otros_tributos_centavos
    )

    return borrador


def cambiar_estado_borrador(
    borrador,
    nuevo_estado,
    *,
    db_session,
    commit=True,
):
    if borrador is None:
        raise ValueError(
            "No se recibió el borrador."
        )

    actual = str(
        getattr(
            borrador,
            "estado",
            "",
        )
        or ""
    ).strip().lower()
    nuevo = str(
        nuevo_estado or ""
    ).strip().lower()

    if nuevo == ESTADO_AUTORIZADO:
        raise ValueError(
            "Un borrador no puede autorizarse "
            "desde la administración manual."
        )

    permitidos = TRANSICIONES_BORRADOR.get(
        actual,
        set(),
    )

    if nuevo not in permitidos:
        raise ValueError(
            "La transición del borrador "
            "no está permitida."
        )

    borrador.estado = nuevo

    if commit:
        try:
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    return borrador


def facturacion_habilita_emision_real(
    modulo_facturacion,
    configuracion,
    punto_venta,
):
    """
    Guardia principal.

    Hasta incorporar el adaptador ARCA esta función
    siempre bloquea la emisión real.
    """
    return False
