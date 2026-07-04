from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import unicodedata


ROLES_POR_TIPO = {
    "imprimir_etiqueta": ("admin", "despacho"),
    "embalar_pedido": ("admin", "despacho"),
    "despachar_pedido": ("admin", "despacho"),
    "completar_carga": ("admin", "carga"),
    "contactar_cliente": ("admin", "carga"),
    "cargar_seguimiento": ("admin", "carga"),
    "confirmar_entrega": ("admin", "carga"),
    "marcar_listo_retirar": ("admin", "carga"),
    "marcar_entregado": ("admin", "carga"),
    "cerrar_pedido": ("admin", "carga"),
    "aviso_ml_confirmado": ("admin", "carga"),
    "gestionar_devolucion": ("admin", "carga"),
    "reclamar_ml_devolucion": ("admin", "carga"),
}


@dataclass(frozen=True)
class ResultadoAccionUI:
    accion_real: str
    texto_boton: str
    puede_ejecutar: bool
    roles_habilitados: tuple[str, ...]
    mensaje: str
    accion: dict[str, Any] | None = None
    accion_sugerida: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "accion_real": self.accion_real,
            "texto_boton": self.texto_boton,
            "puede_ejecutar": self.puede_ejecutar,
            "roles_habilitados": list(self.roles_habilitados),
            "mensaje": self.mensaje,
            "accion": self.accion,
            "accion_sugerida": self.accion_sugerida,
        }


def _normalizar(valor: Any) -> str:
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.split())


def inferir_tipo_accion(texto: Any) -> str:
    normalizado = _normalizar(texto)

    if not normalizado:
        return ""

    reglas = [
        ("imprimir etiqueta", "imprimir_etiqueta"),
        ("embalar pedido", "embalar_pedido"),
        ("despachar pedido", "despachar_pedido"),
        ("completar carga", "completar_carga"),
        ("contactar cliente", "contactar_cliente"),
        ("cargar seguimiento", "cargar_seguimiento"),
        ("hacer seguimiento", "cargar_seguimiento"),
        ("confirmar entrega", "confirmar_entrega"),
        ("marcar listo para retirar", "marcar_listo_retirar"),
        ("marcar entregado", "marcar_entregado"),
        ("cerrar pedido", "cerrar_pedido"),
        ("avisar a mercado libre", "aviso_ml_confirmado"),
        ("ya avise mercado libre", "aviso_ml_confirmado"),
        ("gestionar devolucion", "gestionar_devolucion"),
        ("gestionar reclamo meli", "reclamar_ml_devolucion"),
    ]

    for patron, tipo in reglas:
        if patron in normalizado:
            return tipo

    return ""


def roles_habilitados_para_accion(tipo: Any, texto: Any = "") -> tuple[str, ...]:
    tipo_normalizado = _normalizar(tipo).replace(" ", "_")

    if not tipo_normalizado:
        tipo_normalizado = inferir_tipo_accion(texto)

    return ROLES_POR_TIPO.get(tipo_normalizado, ())


def rol_puede_ejecutar(rol: Any, roles_habilitados: tuple[str, ...]) -> bool:
    rol_normalizado = _normalizar(rol)
    return bool(rol_normalizado and rol_normalizado in roles_habilitados)


def _texto_roles(roles_habilitados: tuple[str, ...]) -> str:
    roles = set(roles_habilitados)

    if roles == {"admin", "despacho"}:
        return "Despacho/Admin"

    if roles == {"admin", "carga"}:
        return "Carga/Admin"

    etiquetas = {
        "admin": "Admin",
        "despacho": "Despacho",
        "carga": "Carga",
    }

    return "/".join(etiquetas.get(rol, rol) for rol in roles_habilitados)


def mensaje_accion_pendiente(texto_boton: Any, roles_habilitados: tuple[str, ...]) -> str:
    texto = str(texto_boton or "").strip()

    if not texto or not roles_habilitados:
        return ""

    return f"Accion pendiente: {texto}. La ejecuta {_texto_roles(roles_habilitados)}."


def resolver_accion_ui_pedido(
    *,
    rol: Any,
    accion_principal: dict[str, Any] | None = None,
    accion_sugerida: Any = "",
) -> dict[str, Any]:
    """
    Contrato central de accion UI.

    Commit 1:
    - No consulta Flask.
    - No consulta base.
    - No cambia pedido.
    - No reemplaza app.py todavia.
    - Solo normaliza la accion real y la accion sugerida actual.
    """

    if accion_principal:
        tipo = str(accion_principal.get("tipo") or "").strip()
        texto = str(accion_principal.get("texto") or "").strip()
        roles = roles_habilitados_para_accion(tipo, texto)

        resultado = ResultadoAccionUI(
            accion_real=tipo or inferir_tipo_accion(texto),
            texto_boton=texto,
            puede_ejecutar=True,
            roles_habilitados=roles,
            mensaje="",
            accion=dict(accion_principal),
            accion_sugerida=str(accion_sugerida or "").strip(),
        )
        return resultado.as_dict()

    texto_sugerido = str(accion_sugerida or "").strip()

    if not texto_sugerido:
        resultado = ResultadoAccionUI(
            accion_real="",
            texto_boton="",
            puede_ejecutar=False,
            roles_habilitados=(),
            mensaje="",
            accion=None,
            accion_sugerida="",
        )
        return resultado.as_dict()

    tipo = inferir_tipo_accion(texto_sugerido)
    roles = roles_habilitados_para_accion(tipo, texto_sugerido)
    puede = rol_puede_ejecutar(rol, roles)

    resultado = ResultadoAccionUI(
        accion_real=tipo,
        texto_boton=texto_sugerido,
        puede_ejecutar=puede,
        roles_habilitados=roles,
        mensaje="" if puede else mensaje_accion_pendiente(texto_sugerido, roles),
        accion=None,
        accion_sugerida=texto_sugerido,
    )
    return resultado.as_dict()
