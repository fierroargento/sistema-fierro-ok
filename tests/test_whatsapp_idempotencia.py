from datetime import datetime, timedelta

from services.whatsapp_idempotencia import (
    normalizar_texto_mensaje_manual,
    mensaje_texto_duplicado_en_lista,
)


class MensajeFake:
    def __init__(self, texto, fecha):
        self.texto = texto
        self.fecha = fecha


def test_normalizar_texto_mensaje_manual_colapsa_espacios():
    texto = "  Hola   cliente   "

    assert normalizar_texto_mensaje_manual(texto) == "Hola cliente"


def test_normalizar_texto_mensaje_manual_respeta_lineas_utiles():
    texto = "Hola   cliente\n\nSeguimos   por acá"

    assert normalizar_texto_mensaje_manual(texto) == "Hola cliente\nSeguimos por acá"


def test_mensaje_texto_duplicado_en_lista_detecta_duplicado_reciente():
    ahora = datetime(2026, 6, 9, 21, 13, 15)

    mensajes = [
        MensajeFake(
            "Perdón se nos puso toxico el bot de Whatsapp!!",
            ahora - timedelta(seconds=3),
        )
    ]

    assert mensaje_texto_duplicado_en_lista(
        mensajes,
        "Perdón se nos puso toxico el bot de Whatsapp!!",
        ahora=ahora,
        ventana_segundos=10,
    ) is True


def test_mensaje_texto_duplicado_en_lista_no_bloquea_fuera_de_ventana():
    ahora = datetime(2026, 6, 9, 21, 13, 15)

    mensajes = [
        MensajeFake(
            "Perdón se nos puso toxico el bot de Whatsapp!!",
            ahora - timedelta(seconds=20),
        )
    ]

    assert mensaje_texto_duplicado_en_lista(
        mensajes,
        "Perdón se nos puso toxico el bot de Whatsapp!!",
        ahora=ahora,
        ventana_segundos=10,
    ) is False


def test_mensaje_texto_duplicado_en_lista_no_bloquea_texto_distinto():
    ahora = datetime(2026, 6, 9, 21, 13, 15)

    mensajes = [
        MensajeFake(
            "Mensaje anterior",
            ahora - timedelta(seconds=3),
        )
    ]

    assert mensaje_texto_duplicado_en_lista(
        mensajes,
        "Mensaje nuevo",
        ahora=ahora,
        ventana_segundos=10,
    ) is False