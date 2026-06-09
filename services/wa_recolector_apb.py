"""
services/wa_recolector_apb.py
──────────────────────────────
Reglas APB para el recolector de datos por WhatsApp.

Objetivo:
- Evitar respuestas repetitivas/tóxicas cuando el comprador pregunta
  por qué se piden datos o dice que ya los cargó en Mercado Libre.
- Mantener la lógica fuera de modules/whatsapp/flows.py.
"""

import re
import unicodedata


def _norm_texto(valor):
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(ch for ch in texto if unicodedata.category(ch) != "Mn")
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return " ".join(texto.split())


def cliente_cuestiona_pedido_de_datos(texto_cliente):
    """
    Detecta mensajes donde el cliente no está negándose necesariamente,
    sino preguntando/reclamando por qué se le piden datos que cree ya cargados.
    """
    texto = _norm_texto(texto_cliente)

    if not texto:
        return False

    patrones = [
        "por que",
        "porque me piden",
        "porque piden",
        "para que",
        "ya los pase",
        "ya lo pase",
        "ya pase",
        "ya estan",
        "ya estan cargados",
        "ya esta cargado",
        "ya figura",
        "ya figuran",
        "estan en mercado libre",
        "esta en mercado libre",
        "mercado libre ya",
        "en la compra",
        "en mis datos",
        "en la aplicacion",
        "en la app",
        "de vuelta",
        "otra vez",
        "nuevamente",
    ]

    return any(patron in texto for patron in patrones)


def armar_mensaje_faltantes_recolector(faltantes, campos_amigables, texto_cliente=""):
    """
    Arma la respuesta del recolector cuando todavía faltan datos.

    Si el cliente cuestiona el pedido de datos, primero explica el motivo
    y recién después pide solo los faltantes reales.
    """
    faltantes = list(faltantes or [])

    lista_faltantes = "\n".join(
        f"• {campos_amigables.get(f, f)}"
        for f in faltantes
    )

    if cliente_cuestiona_pedido_de_datos(texto_cliente):
        return (
            "Te entiendo. En publicaciones con modalidad “Acordás la Entrega”, "
            "Mercado Libre no siempre nos muestra todos los datos completos para coordinar el envío. "
            "Por eso los confirmamos por acá, para evitar errores en el despacho.\n\n"
            "Con lo que tenemos registrado, todavía nos faltaría confirmar:\n\n"
            f"{lista_faltantes}\n\n"
            "Me lo pasás por acá?"
        )

    return (
        "Perfecto, gracias.\n\n"
        "Todavía me faltaría confirmar:\n\n"
        f"{lista_faltantes}\n\n"
        "Me lo pasás por acá?"
    )
