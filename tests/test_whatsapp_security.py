from modules.whatsapp.security import (
    calcular_signature_meta,
    normalizar_signature_meta,
    validar_signature_meta,
)


def test_calcular_signature_meta_formato_correcto():
    firma = calcular_signature_meta(b'{"ok":true}', "secreto")

    assert firma.startswith("sha256=")
    assert len(firma) == len("sha256=") + 64


def test_validar_signature_meta_acepta_firma_correcta():
    raw = b'{"entry":[{"id":"1"}]}'
    secret = "mi_app_secret"
    firma = calcular_signature_meta(raw, secret)

    assert validar_signature_meta(raw, firma, secret) is True


def test_validar_signature_meta_rechaza_firma_incorrecta():
    raw = b'{"entry":[{"id":"1"}]}'
    secret = "mi_app_secret"

    assert validar_signature_meta(raw, "sha256=abc123", secret) is False


def test_validar_signature_meta_rechaza_firma_ausente():
    raw = b'{"entry":[{"id":"1"}]}'
    secret = "mi_app_secret"

    assert validar_signature_meta(raw, "", secret) is False


def test_validar_signature_meta_rechaza_secret_ausente():
    raw = b'{"entry":[{"id":"1"}]}'
    firma = calcular_signature_meta(raw, "mi_app_secret")

    assert validar_signature_meta(raw, firma, "") is False


def test_normalizar_signature_meta_rechaza_formato_invalido():
    assert normalizar_signature_meta("abc123") == ""
    assert normalizar_signature_meta("") == ""