"""
tests/test_ia.py
────────────────
Tests sobre las funciones de extracción IA y validación de datos.
Estas son las funciones que cuando fallan generan loops de mensajes.
No requieren DB ni Flask.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import re
import pytest
from tests.fixtures.pedido_factory import PedidoFake


# ── Importar funciones puras de app.py ───────────────────────────────────────
# Solo importamos lo que necesitamos, evitando ejecutar el bloque with app.app_context()

# Extraemos las funciones directamente para no depender de la app completa
def ia_cp_valido(valor):
    limpio = str(valor or "").strip()
    return limpio if 3 <= len(limpio) <= 12 else ""


def ia_dni_valido(valor):
    limpio = re.sub(r"\D+", "", str(valor or ""))
    return limpio if 7 <= len(limpio) <= 11 else ""


def normalizar_telefono(raw):
    telefono = "" if raw is None else str(raw).strip()
    if not telefono:
        return ""
    telefono = telefono.replace("+", "")
    solo_digitos = re.sub(r"\D", "", telefono)
    if solo_digitos.startswith("549"):
        return solo_digitos
    if solo_digitos.startswith("54"):
        resto = solo_digitos[2:]
        if resto.startswith("9"):
            return "54" + resto
        return "549" + resto
    if solo_digitos.startswith("15"):
        solo_digitos = solo_digitos[2:]
    return "549" + solo_digitos


def ia_extraer_datos_clasico_fierro(texto_cliente, datos_previos=None):
    """Copia exacta de la función en app.py para testeo aislado."""
    datos_previos = datos_previos or {}
    texto_original = str(texto_cliente or "").strip()
    texto = texto_original.lower()
    extraidos = {}

    def falta(campo):
        return not str((datos_previos or {}).get(campo) or "").strip()

    m_dni = re.search(
        r"(?:\bd\.?n\.?i\.?\b|\bdni\b|\bdocumento\b|\bdoc\.?\b)\s*[:#-]?\s*([0-9][0-9\.\s-]{5,15}[0-9])",
        texto_original,
        flags=re.IGNORECASE,
    )
    if m_dni and falta("dni"):
        dni = ia_dni_valido(m_dni.group(1))
        if dni:
            extraidos["dni"] = dni

    m_cp = re.search(
        r"(?:\bc\.?p\.?\b|\bcod(?:igo)?\s*postal\b|\bcódigo\s*postal\b|\bpostal\b)\s*[:#-]?\s*([A-Za-z]?[0-9]{3,5}[A-Za-z]{0,3})",
        texto_original,
        flags=re.IGNORECASE,
    )
    if m_cp and falta("codigo_postal"):
        cp = ia_cp_valido(m_cp.group(1).strip().upper())
        if cp:
            extraidos["codigo_postal"] = cp

    solo_numero = re.fullmatch(r"\s*(\d{4})\s*", texto_original)
    if solo_numero and falta("codigo_postal"):
        extraidos.setdefault("codigo_postal", solo_numero.group(1))

    solo_dni = re.fullmatch(r"\s*([0-9][0-9\.\s-]{5,15}[0-9])\s*", texto_original)
    if solo_dni and falta("dni"):
        dni = ia_dni_valido(solo_dni.group(1))
        if dni and len(dni) >= 7:
            extraidos.setdefault("dni", dni)

    return extraidos


def ia_texto_menciona_autorizado(texto):
    t = str(texto or "").lower()
    patrones = [
        r"\bquien\s+recibe\b",
        r"\bquien\s+retira\b",
        r"\bautorizad[oa]\b",
        r"\bautorizo\s+a\b",
        r"\bentregar\s+a\b",
        r"\ba\s+nombre\s+de\b",
        r"\brecibe\s+[^,.]{2,80}",
        r"\bretira\s+[^,.]{2,80}",
    ]
    return any(re.search(p, t) for p in patrones)


# ── Tests: ia_cp_valido ───────────────────────────────────────────────────────

class TestIaCpValido:
    def test_cp_4_digitos(self):
        assert ia_cp_valido("3500") == "3500"

    def test_cp_4_digitos_con_espacios(self):
        assert ia_cp_valido(" 1612 ") == "1612"

    def test_cp_vacio(self):
        assert ia_cp_valido("") == ""

    def test_cp_muy_corto(self):
        assert ia_cp_valido("12") == ""

    def test_cp_muy_largo(self):
        assert ia_cp_valido("1234567890123") == ""

    def test_cp_none(self):
        assert ia_cp_valido(None) == ""

    def test_cp_5_digitos(self):
        assert ia_cp_valido("12345") == "12345"

    def test_cp_alfanumerico_arg(self):
        # CPs de Argentina pueden tener letras (B1650)
        assert ia_cp_valido("B1650") == "B1650"


# ── Tests: ia_dni_valido ──────────────────────────────────────────────────────

class TestIaDniValido:
    def test_dni_valido_8_digitos(self):
        assert ia_dni_valido("17144245") == "17144245"

    def test_dni_con_puntos(self):
        assert ia_dni_valido("17.144.245") == "17144245"

    def test_dni_muy_corto(self):
        assert ia_dni_valido("12345") == ""

    def test_dni_vacio(self):
        assert ia_dni_valido("") == ""

    def test_dni_none(self):
        assert ia_dni_valido(None) == ""

    def test_dni_con_espacios(self):
        assert ia_dni_valido("17 144 245") == "17144245"

    def test_dni_con_guiones(self):
        assert ia_dni_valido("17-144-245") == "17144245"

    def test_dni_7_digitos_valido(self):
        assert ia_dni_valido("1234567") == "1234567"

    def test_dni_muy_largo(self):
        # 12 dígitos → inválido
        assert ia_dni_valido("123456789012") == ""


# ── Tests: normalizar_telefono ────────────────────────────────────────────────

class TestNormalizarTelefono:
    def test_ya_normalizado(self):
        assert normalizar_telefono("5491164445369") == "5491164445369"

    def test_con_plus(self):
        assert normalizar_telefono("+5491164445369") == "5491164445369"

    def test_sin_prefijo_pais(self):
        resultado = normalizar_telefono("1164445369")
        assert resultado.startswith("549")

    def test_con_15(self):
        resultado = normalizar_telefono("1511644453")
        assert resultado.startswith("549")
        assert "15" not in resultado[3:]  # el 15 se eliminó

    def test_vacio(self):
        assert normalizar_telefono("") == ""

    def test_none(self):
        assert normalizar_telefono(None) == ""

    def test_solo_digitos_sin_codigo(self):
        resultado = normalizar_telefono("1164445369")
        assert len(resultado) >= 11

    def test_ya_tiene_54(self):
        # 54 + 9 + número → debe devolver 549 + número
        resultado = normalizar_telefono("541164445369")
        assert resultado.startswith("549")


# ── Tests: ia_extraer_datos_clasico_fierro ────────────────────────────────────

class TestIaExtractorClasico:

    def test_cp_solo_numero_4_digitos(self):
        """Caso crítico: cliente manda '3500' como único mensaje."""
        result = ia_extraer_datos_clasico_fierro("3500", {})
        assert result.get("codigo_postal") == "3500"

    def test_cp_con_prefijo_cp(self):
        result = ia_extraer_datos_clasico_fierro("CP 3500", {})
        assert result.get("codigo_postal") == "3500"

    def test_cp_con_prefijo_codigo_postal(self):
        result = ia_extraer_datos_clasico_fierro("Código postal 1612", {})
        assert result.get("codigo_postal") == "1612"

    def test_cp_con_prefijo_cod_postal(self):
        result = ia_extraer_datos_clasico_fierro("cod postal: 1888", {})
        assert result.get("codigo_postal") == "1888"

    def test_cp_no_pisa_existente(self):
        """Si ya hay CP, no debe extraer nuevo."""
        result = ia_extraer_datos_clasico_fierro("3500", {"codigo_postal": "1234"})
        assert result.get("codigo_postal") is None

    def test_dni_etiquetado(self):
        result = ia_extraer_datos_clasico_fierro("DNI 17144245", {})
        assert result.get("dni") == "17144245"

    def test_dni_etiquetado_con_puntos(self):
        result = ia_extraer_datos_clasico_fierro("DNI: 17.144.245", {})
        assert result.get("dni") == "17144245"

    def test_dni_solo_numero(self):
        result = ia_extraer_datos_clasico_fierro("17144245", {})
        assert result.get("dni") == "17144245"

    def test_dni_no_pisa_existente(self):
        result = ia_extraer_datos_clasico_fierro("17144245", {"dni": "99999999"})
        assert result.get("dni") is None

    def test_texto_vacio(self):
        result = ia_extraer_datos_clasico_fierro("", {})
        assert result == {}

    def test_mensaje_generico_no_extrae_nada(self):
        result = ia_extraer_datos_clasico_fierro("Hola, cómo están?", {})
        assert result == {}

    def test_no_confunde_cp_con_dni(self):
        """4 dígitos → CP. 8 dígitos → DNI. No mezclar."""
        result_cp = ia_extraer_datos_clasico_fierro("3500", {})
        assert "codigo_postal" in result_cp
        assert "dni" not in result_cp

        result_dni = ia_extraer_datos_clasico_fierro("17144245", {})
        assert "dni" in result_dni
        assert "codigo_postal" not in result_dni


# ── Tests: ia_texto_menciona_autorizado ──────────────────────────────────────

class TestIaTextoMencionaAutorizado:

    def test_recibe_nombre(self):
        assert ia_texto_menciona_autorizado("Recibe Juan Pérez DNI 12345678") is True

    def test_quien_recibe(self):
        assert ia_texto_menciona_autorizado("quien recibe es mi mamá") is True

    def test_autorizado(self):
        assert ia_texto_menciona_autorizado("El autorizado es Pedro") is True

    def test_a_nombre_de(self):
        assert ia_texto_menciona_autorizado("a nombre de María López") is True

    def test_mensaje_normal_no_es_autorizado(self):
        assert ia_texto_menciona_autorizado("Vivo en Avenida Corrientes 1234") is False

    def test_datos_propios_no_es_autorizado(self):
        assert ia_texto_menciona_autorizado("Mi DNI es 17144245") is False

    def test_texto_vacio(self):
        assert ia_texto_menciona_autorizado("") is False

    def test_none(self):
        assert ia_texto_menciona_autorizado(None) is False
