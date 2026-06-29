"""
services.transporte_revision
----------------------------
Clasificacion operativa de fallos de transporte.

APB:
- No escribe DB.
- No importa app.py.
- No cotiza.
- Solo convierte motivos tecnicos en marcas claras para el operador.
"""

TIPO_ERROR_SIN_COBERTURA = "sin_cobertura"
TIPO_ERROR_INTEGRACION = "error_integracion"
TIPO_ERROR_DATOS = "datos_incompletos"
TIPO_ERROR_REVISION = "revision_operativa"


def _normalizar_texto(valor):
    texto = str(valor or "").strip().lower()
    reemplazos = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ñ": "n",
    }

    for origen, destino in reemplazos.items():
        texto = texto.replace(origen, destino)

    return texto


def clasificar_motivo_transporte(motivo):
    """
    Clasifica el motivo sin asumir cobertura cuando solo fallo la cotizacion.
    """
    texto = _normalizar_texto(motivo)

    if not texto:
        return TIPO_ERROR_REVISION

    marcas_integracion = (
        "no se pudo cotizar",
        "revisar respuesta de la integracion",
        "integracion",
        "autentic",
        "credencial",
        "temporalmente deshabilitada",
        "error asignando",
        "no se pudieron obtener sucursales",
        "no se pudo validar costo",
    )

    if any(marca in texto for marca in marcas_integracion):
        return TIPO_ERROR_INTEGRACION

    marcas_datos = (
        "datos logisticos incompletos",
        "cp destino invalido",
        "falta cp",
        "catalogo",
        "producto no permite correo",
        "no contiene pp6040",
    )

    if any(marca in texto for marca in marcas_datos):
        return TIPO_ERROR_DATOS

    marcas_sin_cobertura = (
        "sin cobertura",
        "no hay cobertura",
    )

    if any(marca in texto for marca in marcas_sin_cobertura):
        return TIPO_ERROR_SIN_COBERTURA

    return TIPO_ERROR_REVISION


def construir_marca_revision_transporte(cp, motivo):
    """
    Construye la marca que se guarda en ia_resumen.

    Regla clave:
    - Solo usa "Sin cobertura" si el motivo realmente habla de cobertura.
    - Si fallo la cotizacion/API/integracion, marca revision tecnica.
    """
    cp_txt = str(cp or "").strip()
    motivo_txt = str(motivo or "").strip()
    tipo = clasificar_motivo_transporte(motivo_txt)

    if tipo == TIPO_ERROR_SIN_COBERTURA:
        base = f"Sin cobertura transportes CP {cp_txt}" if cp_txt else "Sin cobertura transportes"
    elif tipo == TIPO_ERROR_DATOS:
        base = f"Transporte con datos logisticos incompletos CP {cp_txt}" if cp_txt else "Transporte con datos logisticos incompletos"
    elif tipo == TIPO_ERROR_INTEGRACION:
        base = f"Transporte requiere revision tecnica CP {cp_txt}" if cp_txt else "Transporte requiere revision tecnica"
    else:
        base = f"Transporte requiere revision CP {cp_txt}" if cp_txt else "Transporte requiere revision"

    if motivo_txt:
        return f"{base}: {motivo_txt}"

    return base
