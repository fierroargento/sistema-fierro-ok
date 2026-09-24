"""
Reglas puras para catálogos y precios comerciales.
"""

from decimal import Decimal
from decimal import InvalidOperation
from decimal import ROUND_HALF_UP

from services.modulos_organizacion import (
    ESTADOS_MODULO,
)


def normalizar_estado_catalogo(estado):
    estado_normalizado = str(
        estado or ""
    ).strip().lower()

    if estado_normalizado not in ESTADOS_MODULO:
        raise ValueError(
            "Estado de catálogo inválido: "
            f"{estado_normalizado or '(vacío)'}."
        )

    return estado_normalizado


def importe_a_centavos(valor):
    """
    Convierte pesos a centavos sin usar coma flotante.
    """
    try:
        if isinstance(valor, str):
            texto = valor.strip().replace(" ", "")
            if not texto:
                raise InvalidOperation
            if "," in texto:
                if texto.count(",") != 1:
                    raise InvalidOperation
                entero, decimal = texto.rsplit(",", 1)
                if not decimal.isdigit() or len(decimal) > 2:
                    raise InvalidOperation
                if "." in entero:
                    grupos = entero.split(".")
                    if not grupos[0].isdigit() or any(
                        not grupo.isdigit() or len(grupo) != 3 for grupo in grupos[1:]
                    ):
                        raise InvalidOperation
                    entero = "".join(grupos)
                texto = f"{entero}.{decimal}"
            elif "." in texto:
                # 1.500 es ambiguo en Argentina: se exige 1500 o 1.500,00.
                partes = texto.split(".")
                if (
                    len(partes) == 2
                    and 1 <= len(partes[0]) <= 3
                    and len(partes[1]) == 3
                    and all(p.isdigit() for p in partes)
                ):
                    raise ValueError(
                        "El importe es ambiguo. Usá 1500 o 1.500,00."
                    )
            importe = Decimal(texto)
        else:
            importe = Decimal(str(valor))
    except (
        InvalidOperation,
        AttributeError,
        ValueError,
    ) as error:
        raise ValueError(
            "El importe ingresado no es válido."
        ) from error

    if importe < 0:
        raise ValueError(
            "El importe no puede ser negativo."
        )

    return int(
        (
            importe * Decimal("100")
        ).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def centavos_a_importe(centavos):
    try:
        valor = int(centavos)
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "La cantidad de centavos no es válida."
        ) from error

    if valor < 0:
        raise ValueError(
            "La cantidad de centavos no puede "
            "ser negativa."
        )

    return Decimal(valor) / Decimal("100")


def cambiar_estado_catalogo(
    catalogo,
    nuevo_estado,
    *,
    db_session,
    commit=True,
):
    if catalogo is None:
        raise ValueError(
            "No se recibió el catálogo a modificar."
        )

    catalogo.estado = normalizar_estado_catalogo(
        nuevo_estado
    )

    if commit:
        try:
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    return catalogo


def configurar_precio_catalogo(
    inclusion,
    *,
    precio,
    precio_lista=None,
):
    if inclusion is None:
        raise ValueError(
            "No se recibió el producto del catálogo."
        )

    inclusion.precio_centavos = (
        importe_a_centavos(precio)
    )

    if precio_lista in (
        None,
        "",
    ):
        inclusion.precio_lista_centavos = None
    else:
        inclusion.precio_lista_centavos = (
            importe_a_centavos(precio_lista)
        )

    return inclusion
