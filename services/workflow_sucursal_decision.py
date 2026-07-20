from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class DecisionSucursal:
    seleccionada: bool
    sucursal: dict[str, Any] | None = None
    indice: int | None = None
    transporte: str = ""
    motivo: str = ""
    requiere_operador: bool = False
    consulta_secundaria: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "seleccionada": self.seleccionada,
            "sucursal": self.sucursal,
            "indice": self.indice,
            "transporte": self.transporte,
            "motivo": self.motivo,
            "requiere_operador": self.requiere_operador,
            "consulta_secundaria": self.consulta_secundaria,
        }


@dataclass(frozen=True)
class ResultadoDeteccionSucursalesOfrecidas:
    correo_ofrecidas: bool
    via_cargo_ofrecidas: bool
    puede_detectar: bool


def evaluar_sucursales_ofrecidas_pedido(
    pedido: Any,
    *,
    pedido_es_plegable_fn: Callable[[Any], bool],
) -> ResultadoDeteccionSucursalesOfrecidas:
    """Evalúa si corresponde detectar una sucursal ofrecida."""

    if not pedido:
        return ResultadoDeteccionSucursalesOfrecidas(
            correo_ofrecidas=False,
            via_cargo_ofrecidas=False,
            puede_detectar=False,
        )

    correo_ofrecidas = bool(
        getattr(
            pedido,
            "correo_sucursales_ofrecidas",
            None,
        )
    )
    via_cargo_ofrecidas = bool(
        getattr(
            pedido,
            "ia_sucursales_ofrecidas",
            None,
        )
    )

    puede_detectar = correo_ofrecidas

    if not puede_detectar and via_cargo_ofrecidas:
        puede_detectar = not bool(
            pedido_es_plegable_fn(pedido)
        )

    return ResultadoDeteccionSucursalesOfrecidas(
        correo_ofrecidas=correo_ofrecidas,
        via_cargo_ofrecidas=via_cargo_ofrecidas,
        puede_detectar=puede_detectar,
    )


def _normalizar_texto(valor: Any) -> str:
    import re
    import unicodedata

    texto = str(valor or "").strip().lower()
    if not texto:
        return ""

    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(ch for ch in texto if unicodedata.category(ch) != "Mn")
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return " ".join(texto.split())


def _normalizar_sucursal(sucursal: dict[str, Any] | None) -> dict[str, Any] | None:
    if not sucursal:
        return None

    return {
        "id": sucursal.get("id") or sucursal.get("agencyId") or sucursal.get("codigo"),
        "nombre": sucursal.get("nombre") or sucursal.get("name") or sucursal.get("descripcion") or "",
        "direccion": sucursal.get("direccion") or sucursal.get("address") or sucursal.get("domicilio") or "",
        "localidad": sucursal.get("localidad") or sucursal.get("city") or "",
        "provincia": sucursal.get("provincia") or sucursal.get("province") or "",
        "cp": sucursal.get("cp") or sucursal.get("codigo_postal") or sucursal.get("postalCode") or "",
        "raw": sucursal,
    }


def texto_consulta_sucursal(texto: Any) -> bool:
    import re

    texto_original = str(texto or "")
    if "?" in texto_original:
        return True

    normalizado = _normalizar_texto(texto_original)
    if not normalizado:
        return False

    marcas = [
        "horario",
        "horarios",
        "hora",
        "cuando",
        "donde queda",
        "direccion",
        "telefono",
        "atienden",
        "abre",
        "abren",
        "cerrado",
        "cerrada",
        "retirar",
        "retiro",
        "no lo tienen",
        "ese no",
        "tienen ese",
        "queda cerca",
        "esta cerca",
        "me queda",
        "hay alguna",
        "tienen alguna",
        "podria ser",
        "o ese",
        "sino",
        "si no",
        "en cambio",
        "por ejemplo",
        "me parece",
        "creo que",
    ]

    if any(
        marca in normalizado
        for marca in marcas
    ):
        return True

    patrones = [
        r"\bno\b.*\bse\b",
    ]

    return any(
        re.search(patron, normalizado)
        for patron in patrones
    )


def texto_parece_eleccion_sucursal(texto: Any) -> bool:
    from services.mensajes_sucursales import (
        extraer_opcion_sucursal_explicita,
    )

    normalizado = _normalizar_texto(texto)
    if not normalizado:
        return False

    marcas_eleccion = [
        "elijo",
        "elegi",
        "elegimos",
        "prefiero",
        "quiero la",
        "quiero esa",
        "me quedo",
        "opcion",
        "numero",
        "la 1",
        "la 2",
        "la 3",
        "la 4",
        "la 5",
        "primera",
        "segunda",
        "tercera",
        "cuarta",
        "quinta",
        "la de",
        "sucursal",
        "nro",
    ]
    palabras_datos = [
        "dni",
        "documento",
        "direccion",
        "cp",
        "codigo",
        "telefono",
        "contacto",
        "envio",
        "calle",
        "altura",
    ]

    tiene_marca_eleccion = any(
        marca in normalizado
        for marca in marcas_eleccion
    )
    contiene_datos = any(
        palabra in normalizado
        for palabra in palabras_datos
    )
    es_corto = len(normalizado) <= 45

    indice = extraer_opcion_sucursal_explicita(
        normalizado,
        cantidad_opciones=5,
    )

    if (
        indice is not None
        and (
            es_corto
            or tiene_marca_eleccion
        )
    ):
        return True

    if tiene_marca_eleccion:
        return True

    return bool(
        es_corto
        and not contiene_datos
    )


def seleccionar_sucursal_via_cargo_ofrecida_por_texto(
    *,
    texto: Any,
    sucursales_catalogo: list[dict[str, Any]],
    ids_ofrecidas: list[Any],
) -> dict[str, Any] | None:
    """
    Busca una sucursal ofrecida por nombre o dirección.

    No modifica el pedido.
    No lee archivos.
    No hace commit.
    No envía mensajes.
    """

    import re

    if not texto_parece_eleccion_sucursal(texto):
        return None

    normalizado = _normalizar_texto(texto)
    ids = {
        str(valor)
        for valor in ids_ofrecidas or []
        if valor is not None
    }

    if not normalizado or not ids:
        return None

    candidatas = [
        sucursal
        for sucursal in sucursales_catalogo or []
        if (
            isinstance(sucursal, dict)
            and str(
                sucursal.get("id")
                or sucursal.get("agencyId")
                or sucursal.get("codigo")
                or ""
            ) in ids
        )
    ]

    for sucursal in candidatas:
        nombre = _normalizar_texto(
            sucursal.get("nombre")
            or sucursal.get("name")
            or sucursal.get("descripcion")
            or ""
        )
        palabras = [
            palabra
            for palabra in re.split(r"\W+", nombre)
            if (
                len(palabra) > 3
                and palabra not in {
                    "agencia",
                    "encomiendas",
                    "logistica",
                }
            )
        ]

        if palabras and all(
            palabra in normalizado
            for palabra in palabras
        ):
            return sucursal

    for sucursal in candidatas:
        direccion = _normalizar_texto(
            sucursal.get("direccion")
            or sucursal.get("address")
            or sucursal.get("domicilio")
            or ""
        )
        direccion = re.sub(
            r"\bnro\.?\s*",
            "",
            direccion,
        ).strip()

        if (
            len(direccion) > 5
            and direccion in normalizado
        ):
            return sucursal

    return None


def _crear_decision_via_cargo_por_texto(
    *,
    texto: Any,
    sucursales_catalogo: list[dict[str, Any]],
    ids_ofrecidas: list[Any],
    motivo: str,
    consulta: bool,
) -> DecisionSucursal | None:
    sucursal = (
        seleccionar_sucursal_via_cargo_ofrecida_por_texto(
            texto=texto,
            sucursales_catalogo=sucursales_catalogo,
            ids_ofrecidas=ids_ofrecidas,
        )
    )

    if not sucursal:
        return None

    sucursal_id = str(
        sucursal.get("id")
        or sucursal.get("agencyId")
        or sucursal.get("codigo")
        or ""
    )
    indice = next(
        (
            posicion
            for posicion, valor in enumerate(
                ids_ofrecidas
            )
            if str(valor) == sucursal_id
        ),
        None,
    )

    return DecisionSucursal(
        seleccionada=True,
        sucursal=_normalizar_sucursal(sucursal),
        indice=indice,
        transporte="via_cargo",
        motivo=motivo,
        requiere_operador=consulta,
        consulta_secundaria=consulta,
    )


def decidir_sucursal_via_cargo_ofrecida(
    *,
    texto: Any,
    sucursales_catalogo: list[dict[str, Any]],
    ids_ofrecidas: list[Any],
    es_afirmativo_fn: Callable[[Any], bool] | None = None,
) -> DecisionSucursal:
    from services.mensajes_sucursales import (
        extraer_opcion_sucursal_explicita,
        normalizar_numero_opcion_sucursal,
        seleccionar_sucursal_ofrecida_por_opcion,
    )

    texto_original = str(texto or "").strip()
    if not texto_original:
        return DecisionSucursal(
            seleccionada=False,
            transporte="via_cargo",
            motivo="texto_vacio",
        )

    ids = list(ids_ofrecidas or [])
    if not ids:
        return DecisionSucursal(
            seleccionada=False,
            transporte="via_cargo",
            motivo="sin_sucursales_ofrecidas",
        )

    consulta = texto_consulta_sucursal(texto_original)

    indice = extraer_opcion_sucursal_explicita(texto_original, cantidad_opciones=len(ids))
    if indice is None:
        indice = normalizar_numero_opcion_sucursal(texto_original)

    if (
        indice is None
        and len(ids) == 1
        and es_afirmativo_fn is not None
    ):
        try:
            if es_afirmativo_fn(texto_original):
                indice = 0
        except Exception:
            pass

    if indice is None:
        decision_por_texto = (
            _crear_decision_via_cargo_por_texto(
                texto=texto_original,
                sucursales_catalogo=sucursales_catalogo,
                ids_ofrecidas=ids,
                motivo="sucursal_confirmada_por_texto",
                consulta=consulta,
            )
        )
        if decision_por_texto:
            return decision_por_texto

    if indice is None:
        return DecisionSucursal(
            seleccionada=False,
            transporte="via_cargo",
            motivo="sin_eleccion_explicita",
            requiere_operador=consulta,
            consulta_secundaria=consulta,
        )

    sucursal = seleccionar_sucursal_ofrecida_por_opcion(
        sucursales_catalogo,
        ids,
        indice,
    )

    if not sucursal:
        return DecisionSucursal(
            seleccionada=False,
            indice=indice,
            transporte="via_cargo",
            motivo="opcion_fuera_de_rango_o_id_no_encontrado",
            requiere_operador=True,
            consulta_secundaria=consulta,
        )

    return DecisionSucursal(
        seleccionada=True,
        sucursal=_normalizar_sucursal(sucursal),
        indice=indice,
        transporte="via_cargo",
        motivo="sucursal_confirmada_por_opcion",
        requiere_operador=consulta,
        consulta_secundaria=consulta,
    )


def decidir_sucursal_correo_ofrecida(
    *,
    pedido: Any,
    texto: Any,
    detector_correo_fn: Callable[[Any, Any], dict[str, Any] | None] | None = None,
) -> DecisionSucursal:
    texto_original = str(texto or "").strip()
    if not texto_original:
        return DecisionSucursal(
            seleccionada=False,
            transporte="correo",
            motivo="texto_vacio",
        )

    consulta = texto_consulta_sucursal(texto_original)

    if detector_correo_fn is None:
        from services.correo_sucursales_eleccion import detectar_sucursal_correo_ofrecida

        detector_correo_fn = detectar_sucursal_correo_ofrecida

    sucursal = detector_correo_fn(pedido, texto_original)

    if not sucursal:
        return DecisionSucursal(
            seleccionada=False,
            transporte="correo",
            motivo="sin_sucursal_detectada",
            requiere_operador=consulta,
            consulta_secundaria=consulta,
        )

    return DecisionSucursal(
        seleccionada=True,
        sucursal=_normalizar_sucursal(sucursal),
        indice=None,
        transporte="correo",
        motivo="sucursal_correo_confirmada",
        requiere_operador=consulta,
        consulta_secundaria=consulta,
    )


def decidir_sucursal_ofrecida(
    *,
    transporte: Any,
    texto: Any,
    pedido: Any = None,
    sucursales_catalogo: list[dict[str, Any]] | None = None,
    ids_ofrecidas: list[Any] | None = None,
    detector_correo_fn: Callable[[Any, Any], dict[str, Any] | None] | None = None,
) -> DecisionSucursal:
    transporte_norm = _normalizar_texto(transporte)

    if "correo" in transporte_norm:
        return decidir_sucursal_correo_ofrecida(
            pedido=pedido,
            texto=texto,
            detector_correo_fn=detector_correo_fn,
        )

    if "via" in transporte_norm or "cargo" in transporte_norm:
        return decidir_sucursal_via_cargo_ofrecida(
            texto=texto,
            sucursales_catalogo=list(sucursales_catalogo or []),
            ids_ofrecidas=list(ids_ofrecidas or []),
        )

    return DecisionSucursal(
        seleccionada=False,
        transporte=transporte_norm,
        motivo="transporte_no_soportado",
    )

def decidir_sucursal_via_cargo_para_pedido(
    *,
    pedido: Any,
    texto: Any,
    sucursales_catalogo: list[dict[str, Any]],
    es_afirmativo_fn: Callable[[Any], bool] | None = None,
    log_error_fn: Callable[[Exception], None] | None = None,
) -> DecisionSucursal:
    """
    Decide una sucursal Via Cargo usando las opciones del pedido.

    No modifica el pedido.
    No lee archivos.
    No hace commit.
    No envia mensajes.
    """

    import json

    ids_raw = str(
        getattr(
            pedido,
            "ia_sucursales_ofrecidas",
            "",
        )
        or ""
    ).strip()

    if not ids_raw:
        return DecisionSucursal(
            seleccionada=False,
            transporte="via_cargo",
            motivo="sin_sucursales_ofrecidas",
        )

    try:
        ids_ofrecidas = json.loads(ids_raw)
    except Exception:
        ids_ofrecidas = []

    if not isinstance(ids_ofrecidas, list):
        ids_ofrecidas = []

    if not ids_ofrecidas:
        return DecisionSucursal(
            seleccionada=False,
            transporte="via_cargo",
            motivo="sin_sucursales_ofrecidas",
        )

    try:
        return decidir_sucursal_via_cargo_ofrecida(
            texto=texto,
            sucursales_catalogo=sucursales_catalogo,
            ids_ofrecidas=ids_ofrecidas,
            es_afirmativo_fn=es_afirmativo_fn,
        )
    except Exception as error:
        if log_error_fn is not None:
            try:
                log_error_fn(error)
            except Exception:
                pass

    from services.mensajes_sucursales import (
        extraer_opcion_sucursal_explicita,
        normalizar_numero_opcion_sucursal,
        seleccionar_sucursal_ofrecida_por_opcion,
    )

    texto_original = str(texto or "").strip()
    consulta = texto_consulta_sucursal(texto_original)

    indice = extraer_opcion_sucursal_explicita(
        texto_original,
        cantidad_opciones=len(ids_ofrecidas),
    )

    if indice is None:
        indice = normalizar_numero_opcion_sucursal(
            texto_original,
        )

    if (
        indice is None
        and len(ids_ofrecidas) == 1
        and es_afirmativo_fn is not None
    ):
        try:
            if es_afirmativo_fn(texto_original):
                indice = 0
        except Exception:
            pass

    if indice is None:
        decision_por_texto = (
            _crear_decision_via_cargo_por_texto(
                texto=texto_original,
                sucursales_catalogo=sucursales_catalogo,
                ids_ofrecidas=ids_ofrecidas,
                motivo=(
                    "fallback_sucursal_"
                    "confirmada_por_texto"
                ),
                consulta=consulta,
            )
        )
        if decision_por_texto:
            return decision_por_texto

    if (
        indice is None
        or indice < 0
        or indice >= len(ids_ofrecidas)
    ):
        return DecisionSucursal(
            seleccionada=False,
            transporte="via_cargo",
            motivo="fallback_sin_eleccion_valida",
            requiere_operador=consulta,
            consulta_secundaria=consulta,
        )

    sucursal = seleccionar_sucursal_ofrecida_por_opcion(
        sucursales_catalogo,
        ids_ofrecidas,
        indice,
    )

    if not sucursal:
        return DecisionSucursal(
            seleccionada=False,
            indice=indice,
            transporte="via_cargo",
            motivo="fallback_sucursal_no_encontrada",
            requiere_operador=True,
            consulta_secundaria=consulta,
        )

    return DecisionSucursal(
        seleccionada=True,
        sucursal=_normalizar_sucursal(sucursal),
        indice=indice,
        transporte="via_cargo",
        motivo="fallback_legacy",
        requiere_operador=consulta,
        consulta_secundaria=consulta,
    )
