"""
modules/whatsapp/security.py
────────────────────────────
Seguridad de webhooks Meta / WhatsApp.

APB:
- No procesar POSTs de WhatsApp si la firma no valida.
- No imprimir secretos.
- Mantener la validación aislada del flujo conversacional.
"""

import hmac
import hashlib


def normalizar_signature_meta(signature_header):
    """
    Meta envía la firma como:
    X-Hub-Signature-256: sha256=<hex>
    """
    signature = str(signature_header or "").strip()

    if not signature:
        return ""

    if signature.startswith("sha256="):
        return signature

    return ""


def calcular_signature_meta(raw_body, app_secret):
    if raw_body is None:
        raw_body = b""

    if isinstance(raw_body, str):
        raw_body = raw_body.encode("utf-8")

    secret = str(app_secret or "").strip()
    if not secret:
        return ""

    digest = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return f"sha256={digest}"


def validar_signature_meta(raw_body, signature_header, app_secret):
    """
    Devuelve True solo si la firma recibida coincide con la firma esperada.
    """
    signature_recibida = normalizar_signature_meta(signature_header)
    signature_esperada = calcular_signature_meta(raw_body, app_secret)

    if not signature_recibida or not signature_esperada:
        return False

    return hmac.compare_digest(signature_recibida, signature_esperada)