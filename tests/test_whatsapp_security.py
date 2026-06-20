import hmac
import hashlib

from modules.whatsapp.security import (
    calcular_signature_meta,
    normalizar_signature_meta,
    validar_signature_meta,
)


def test_normalizar_signature_meta_acepta_sha256():
    assert normalizar_signature_meta("sha256=abc123") == "sha256=abc123"


def test_normalizar_signature_meta_rechaza_vacia_o_formato_invalido():
    assert normalizar_signature_meta("") == ""
    assert normalizar_signature_meta("abc123") == ""
    assert normalizar_signature_meta("sha1=abc123") == ""


def test_calcular_signature_meta_genera_hmac_sha256():
    raw_body = b'{"object":"whatsapp_business_account"}'
    secret = "app_secret_test"

    esperado = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    assert calcular_signature_meta(raw_body, secret) == esperado


def test_validar_signature_meta_acepta_firma_correcta():
    raw_body = b'{"entry":[]}'
    secret = "app_secret_test"
    firma = calcular_signature_meta(raw_body, secret)

    assert validar_signature_meta(raw_body, firma, secret) is True


def test_validar_signature_meta_rechaza_firma_incorrecta():
    raw_body = b'{"entry":[]}'
    secret = "app_secret_test"

    assert validar_signature_meta(raw_body, "sha256=mal", secret) is False


def test_validar_signature_meta_rechaza_sin_secret_o_sin_firma():
    raw_body = b'{"entry":[]}'

    assert validar_signature_meta(raw_body, "", "app_secret_test") is False
    assert validar_signature_meta(raw_body, "sha256=abc", "") is False
