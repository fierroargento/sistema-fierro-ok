import json
import os

from urllib.request import Request, urlopen


def ia_llamar_openai_chat_service(prompt, temperatura=0.4):
    """
    Llamada genérica a OpenAI para el bot de WhatsApp.
    Devuelve el texto de respuesta o lanza excepción.
    """

    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not api_key:
        raise ValueError("OPENAI_API_KEY no configurada")

    modelo = (
        os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        or "gpt-4o-mini"
    )

    payload = {
        "model": modelo,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Sos el asistente de Fierro 100% Argento. "
                    "Respondés en español rioplatense, "
                    "de forma amable y breve."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": temperatura,
    }

    req = Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    return data["choices"][0]["message"]["content"].strip()

def ia_chat_completion_json_service(
    messages,
    temperatura=0,
    timeout=25,
):
    """
    Wrapper genérico OpenAI JSON/APB.
    Devuelve el content del primer choice.
    """

    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not api_key:
        raise ValueError("OPENAI_API_KEY no configurada")

    modelo = (
        os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        or "gpt-4o-mini"
    )

    payload = {
        "model": modelo,
        "messages": messages,
        "temperature": temperatura,
    }

    req = Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")

    data = json.loads(raw)

    return data["choices"][0]["message"]["content"]