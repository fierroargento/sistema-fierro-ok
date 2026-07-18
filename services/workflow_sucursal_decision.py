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
    normalizado = _normalizar_texto(texto)
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
    ]

    return any(marca in normalizado for marca in marcas)


def texto_parece_eleccion_sucursal(texto: Any) -> bool:
    from services.mensajes_sucursales import extraer_opcion_sucursal_explicita

    normalizado = _normalizar_texto(texto)
    if not normalizado:
        return False

    if extraer_opcion_sucursal_explicita(normalizado, cantidad_opciones=3) is not None:
        return True

    marcas = [
        "sucursal",
        "opcion",
        "op",
        "nro",
        "numero",
        "la primera",
        "la segunda",
        "la tercera",
        "quiero",
        "elijo",
        "prefiero",
        "esa",
    ]

    return any(marca in normalizado for marca in marcas)


def decidir_sucursal_via_cargo_ofrecida(
    *,
    texto: Any,
    sucursales_catalogo: list[dict[str, Any]],
    ids_ofrecidas: list[Any],
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
