"""
Análisis estructurado de mensajes del recolector ML.

Construye el prompt, consulta el proveedor IA y devuelve
un diccionario normalizado.

No modifica pedidos.
No persiste.
No envía mensajes.
No importa app.
"""

import json
import os
from typing import Any, Callable
from urllib.error import HTTPError

from services.ia import (
    ia_chat_completion_json_service,
)
from services.ia_recolector_datos import (
    ia_extraer_datos_clasico_fierro,
)
from services.ia_recolector_sync import (
    json_loads_seguro_recolector,
)


def analizar_datos_cliente_ml_acordas(
    texto_cliente: Any,
    datos_previos: dict[str, Any] | None = None,
    *,
    getenv_fn: Callable[[str, str], str] = os.getenv,
    chat_completion_fn: Callable[..., Any] = (
        ia_chat_completion_json_service
    ),
    json_loads_fn: Callable[[Any], dict[str, Any]] = (
        json_loads_seguro_recolector
    ),
    extraer_datos_clasicos_fn: Callable[
        ...,
        dict[str, Any],
    ] = ia_extraer_datos_clasico_fierro,
):
    """Llama a OpenAI para extraer datos. Fase 2: NO responde al cliente."""
    api_key = getenv_fn("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {
            "ok": False,
            "error": "OPENAI_API_KEY no está configurada",
            "estado": "sin_configurar",
        }

    datos_previos = datos_previos or {}
    campos = ["nombre", "apellido", "dni", "telefono", "direccion", "localidad", "codigo_postal"]
    campos_autorizado = ["autorizado_nombre", "autorizado_dni", "autorizado_telefono"]

    prompt = '''
Sos el recolector de datos de Fierro 100% Argento para pedidos de Mercado Libre / Acordás la Entrega.

OBJETIVO PRINCIPAL:
Analizar la respuesta del comprador, extraer datos para coordinar el envío y clasificar la intención del mensaje.
No inventes datos. Si no estás seguro, dejá el campo vacío y ponelo como faltante.

DATOS OBLIGATORIOS DEL COMPRADOR / TITULAR:
- nombre
- apellido
- dni
- telefono
- direccion
- localidad
- codigo_postal

DATOS DE AUTORIZADO / QUIEN RECIBE O RETIRA:
Si el comprador dice que recibe, retira, está autorizado, se entrega a otra persona, o usa frases como "quien recibe", "quien retira", "autorizo a", "entregar a", NO pongas esos datos como titular. Cargalos en:
- autorizado_nombre
- autorizado_dni
- autorizado_telefono

Si no hay señal explícita de autorizado, dejá autorizado_* vacío.

REGLAS DE NEGOCIO ML / ACORDÁS:
1. En esta modalidad no vemos siempre todos los datos completos que el comprador cargó en Mercado Libre. Si el comprador dice "están en Mercado Libre", "son los mismos de la compra", "ya figuran", "están en mis datos" o similar, NO lo marques como conflicto: resumí que reclama que los datos ya están en ML y mantené los faltantes.
2. El envío es sin cargo. Si pregunta cuánto sale el envío, resumí que pregunta por costo de envío.
3. La demora habitual es de entre 3 y 5 días hábiles a partir del despacho. Si pregunta cuánto demora o cuándo llega, resumí que pregunta por demora.
4. Si pregunta por qué pedimos los datos, resumí que pide explicación sobre los datos.
5. Si dice "ya los pasé", verificá contra datos_previos + mensaje nuevo. Si siguen faltando datos, mantené solo los faltantes reales.
6. Si falta código postal pero hay localidad clara, extraé y conservá la localidad. El sistema intentará completar el código postal automáticamente con la base local si la localidad/provincia son confiables.
7. Si el comprador solo quiere que lo llamen o pasar WhatsApp, extraé el teléfono si está, pero seguí marcando los datos faltantes.
8. Si el mensaje mezcla datos del titular y de un autorizado, mantené separados: titular en nombre/apellido/dni/teléfono; autorizado en autorizado_nombre/autorizado_dni/autorizado_telefono.
9. No reemplaces el titular por el autorizado.

ESCALAR A OPERADOR:
Marcá requiere_operador=true SOLO si detectás intención de cancelar, reclamo/problema, enojo fuerte, insultos, cambio de modalidad de entrega/retiro, problema con el producto o una pregunta que no se pueda responder con estas reglas. En esos casos, el resumen debe incluir un llamado a la acción claro para el operador.

NO HACER:
- No prometas fechas exactas.
- No elijas transporte.
- No confirmes despacho.
- No resuelvas reclamos.
- No cambies estados.

Datos ya conocidos del pedido, si existen:
{datos_previos}

Mensaje nuevo del comprador:
"""{texto_cliente}"""

Respondé SOLO JSON válido con esta estructura exacta:
{{
  "datos": {{
    "nombre": "",
    "apellido": "",
    "dni": "",
    "telefono": "",
    "direccion": "",
    "localidad": "",
    "codigo_postal": "",
    "autorizado_nombre": "",
    "autorizado_dni": "",
    "autorizado_telefono": ""
  }},
  "faltantes": [],
  "datos_completos": false,
  "requiere_operador": false,
  "motivo_operador": "",
  "resumen": "",
  "confianza": "baja|media|alta"
}}

En resumen, indicá claramente si aplica alguno de estos casos: datos en Mercado Libre, ya los pasé, pregunta por demora, pregunta por costo de envío, pregunta por qué pedimos datos, quiere llamada/WhatsApp, requiere operador.
'''.format(
        datos_previos=json.dumps(datos_previos, ensure_ascii=False),
        texto_cliente=str(texto_cliente or "").strip(),
    )

    try:
        contenido = chat_completion_fn(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Respondés únicamente JSON válido. "
                        "Sos preciso, conservador y APB."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperatura=0,
            timeout=25,
        )
        resultado = json_loads_fn(contenido)
        if not resultado:
            raise ValueError("La IA no devolvió JSON válido")

        datos = resultado.get("datos") or {}

        # APB: refuerzo determinístico para DNI/CP.
        # Si el comprador respondió "1617", "Código postal 1617", "32339954" o "DNI 37331234",
        # lo tomamos aunque la IA no lo haya extraído.
        datos_clasicos = extraer_datos_clasicos_fn(texto_cliente, datos_previos)
        for c, v in datos_clasicos.items():
            if v and not str(datos.get(c) or "").strip():
                datos[c] = v

        fusionados = dict(datos_previos)
        for c in campos:
            valor = str(datos.get(c) or "").strip()
            if valor:
                fusionados[c] = valor
            else:
                fusionados.setdefault(c, "")
        for c in campos_autorizado:
            valor = str(datos.get(c) or "").strip()
            if valor:
                fusionados[c] = valor
            else:
                fusionados.setdefault(c, "")

        faltantes = [c for c in campos if not str(fusionados.get(c) or "").strip()]
        resultado["datos"] = {c: str(fusionados.get(c) or "").strip() for c in campos + campos_autorizado}
        resultado["faltantes"] = faltantes
        resultado["datos_completos"] = len(faltantes) == 0
        resultado["ok"] = True
        return resultado
    except HTTPError as e:
        detalle = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
        return {"ok": False, "estado": "error", "error": f"OpenAI HTTP {e.code}: {detalle[:500]}"}
    except Exception as e:
        return {"ok": False, "estado": "error", "error": str(e)[:500]}
