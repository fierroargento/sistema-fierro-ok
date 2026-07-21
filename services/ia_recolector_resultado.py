"""
Aplicación estructurada del resultado del recolector IA.

Modifica únicamente el pedido recibido.
No hace commit.
No envía mensajes.
No ejecuta handoff ni cross-sell.
"""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any, Callable

from services.ia_recolector_datos import (
    ia_autocompletar_pedido_con_datos,
    ia_extraer_datos_clasico_fierro,
    normalizar_datos_ia_fierro,
)
from services.ia_recolector_logistica import (
    debe_reencauzar_pp6040_sin_faltantes_service,
)
from services.ia_recolector_sync import (
    calcular_faltantes_reales_recolector,
    consolidar_datos_recolector_con_pedido,
    datos_previos_pedido_recolector,
    decidir_estado_recolector,
    persistir_telefono_detectado_recolector,
    resolver_requiere_operador_final_recolector,
)
from services.ubicacion_cp import (
    normalizar_datos_ubicacion_detectados,
)


@dataclass(frozen=True)
class ResultadoAplicacionRecolector:
    aplicado: bool
    exitoso: bool
    estado: str
    motivo: str
    datos: dict[str, Any]
    faltantes: tuple[str, ...]
    completados: tuple[str, ...]
    requiere_operador: bool
    iniciar_handoff: bool


def _hash_texto(texto: Any) -> str:
    return hashlib.sha256(
        str(texto or "").encode(
            "utf-8",
            errors="ignore",
        )
    ).hexdigest()


def aplicar_resultado_recolector(
    pedido: Any,
    texto_cliente: Any,
    resultado: Any,
    *,
    parece_nickname_fn: Callable[[Any, Any], bool],
    es_ml_acordas_entrega_fn: Callable[[Any], bool],
    pedido_es_plegable_pp6040_fn: Callable[[Any], bool],
    ahora_fn: Callable[[], Any] = datetime.utcnow,
    log_fn: Callable[[str], Any] = print,
) -> ResultadoAplicacionRecolector:
    if not pedido:
        return ResultadoAplicacionRecolector(
            aplicado=False,
            exitoso=False,
            estado="no_pedido",
            motivo="no_pedido",
            datos={},
            faltantes=(),
            completados=(),
            requiere_operador=False,
            iniciar_handoff=False,
        )

    pedido.ia_ultimo_mensaje_hash = _hash_texto(
        texto_cliente
    )
    pedido.ia_ultimo_analisis = ahora_fn()
    pedido.ia_error = ""

    if (
        not isinstance(resultado, dict)
        or not resultado.get("ok")
    ):
        estado = (
            resultado.get("estado")
            if isinstance(resultado, dict)
            else "error"
        )
        error = (
            resultado.get("error")
            if isinstance(resultado, dict)
            else "Error IA"
        )

        pedido.ia_recolector_estado = estado
        pedido.ia_error = error or "Error IA"

        return ResultadoAplicacionRecolector(
            aplicado=True,
            exitoso=False,
            estado=str(estado or "error"),
            motivo="resultado_invalido",
            datos={},
            faltantes=(),
            completados=(),
            requiere_operador=bool(
                getattr(
                    pedido,
                    "ia_requiere_operador",
                    False,
                )
            ),
            iniciar_handoff=False,
        )

    datos = normalizar_datos_ia_fierro(
        resultado.get("datos") or {}
    )

    datos_previos = datos_previos_pedido_recolector(
        pedido,
        parece_nickname_fn=parece_nickname_fn,
    )
    datos_clasicos = ia_extraer_datos_clasico_fierro(
        texto_cliente,
        datos_previos,
    )

    for campo, valor in datos_clasicos.items():
        if (
            valor
            and not str(
                datos.get(campo) or ""
            ).strip()
        ):
            datos[campo] = valor

    try:
        datos = normalizar_datos_ubicacion_detectados(
            datos,
            texto_cliente=texto_cliente,
        )
    except Exception as error:
        log_fn(
            "[UBICACION] No se pudieron normalizar "
            "datos detectados pedido "
            f"#{getattr(pedido, 'id', '?')}: {error}"
        )

    completados = list(
        ia_autocompletar_pedido_con_datos(
            pedido,
            datos,
            texto_cliente=texto_cliente,
        )
        or []
    )

    try:
        datos = consolidar_datos_recolector_con_pedido(
            pedido,
            datos,
        )
    except Exception as error:
        log_fn(
            "[IA-RECOLECTOR-SYNC] No se pudo "
            "consolidar datos pedido "
            f"#{getattr(pedido, 'id', '?')}: {error}"
        )

    for campo in persistir_telefono_detectado_recolector(
        pedido,
        datos,
    ):
        if campo not in completados:
            completados.append(campo)

    faltantes = calcular_faltantes_reales_recolector(
        pedido,
        datos,
    )

    requiere_operador = bool(
        resultado.get("requiere_operador")
    )
    requiere_operador_final = (
        resolver_requiere_operador_final_recolector(
            pedido,
            requiere_operador=requiere_operador,
        )
    )

    try:
        if debe_reencauzar_pp6040_sin_faltantes_service(
            pedido=pedido,
            resultado=resultado,
            faltantes=faltantes,
            requiere_operador_final=(
                requiere_operador_final
            ),
            es_ml_acordas_entrega_fn=(
                es_ml_acordas_entrega_fn
            ),
            pedido_es_plegable_pp6040_fn=(
                pedido_es_plegable_pp6040_fn
            ),
        ):
            log_fn(
                f"[IA-RECOLECTOR] Pedido "
                f"#{getattr(pedido, 'id', '?')}: "
                "reencauzado a logística automática "
                "PP6040 sin faltantes reales"
            )
            requiere_operador_final = False
            try:
                pedido.ia_ultimo_timeout_operador = None
            except Exception:
                pass
    except Exception as error:
        log_fn(
            "[IA-RECOLECTOR] No se pudo evaluar "
            "reencauce logístico pedido "
            f"#{getattr(pedido, 'id', '?')}: {error}"
        )

    estado = decidir_estado_recolector(
        faltantes=faltantes,
        requiere_operador=requiere_operador_final,
    )

    pedido.ia_recolector_estado = estado
    pedido.ia_datos_detectados = json.dumps(
        datos,
        ensure_ascii=False,
    )
    pedido.ia_faltantes = json.dumps(
        faltantes,
        ensure_ascii=False,
    )

    resumen = str(
        resultado.get("resumen") or ""
    ).strip()

    if completados:
        extra = (
            "IA autocompletó: "
            + ", ".join(completados)
        )
        resumen = (
            (resumen + " | " + extra).strip(" |")
            if resumen
            else extra
        )

    pedido.ia_resumen = resumen
    pedido.ia_requiere_operador = (
        requiere_operador_final
    )

    iniciar_handoff = bool(
        not requiere_operador_final
        and faltantes
    )

    return ResultadoAplicacionRecolector(
        aplicado=True,
        exitoso=True,
        estado=estado,
        motivo="resultado_aplicado",
        datos=dict(datos),
        faltantes=tuple(faltantes),
        completados=tuple(completados),
        requiere_operador=requiere_operador_final,
        iniciar_handoff=iniciar_handoff,
    )
