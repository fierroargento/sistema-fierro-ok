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
TIPO_ERROR_AUTENTICACION = "error_autenticacion"
TIPO_ERROR_DATOS = "datos_incompletos"
TIPO_ERROR_DATOS_LOGISTICOS = "datos_logisticos_incompletos"
TIPO_ERROR_PRODUCTO_NO_PERMITE_CORREO = "producto_no_permite_correo"
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

    if "autentic" in texto or "credencial" in texto:
        return TIPO_ERROR_AUTENTICACION

    if any(marca in texto for marca in marcas_integracion):
        return TIPO_ERROR_INTEGRACION

    if "producto no permite correo" in texto or "no permite correo argentino" in texto:
        return TIPO_ERROR_PRODUCTO_NO_PERMITE_CORREO

    if "datos logisticos incompletos" in texto:
        return TIPO_ERROR_DATOS_LOGISTICOS

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
    elif tipo in (
        TIPO_ERROR_DATOS,
        TIPO_ERROR_DATOS_LOGISTICOS,
        TIPO_ERROR_PRODUCTO_NO_PERMITE_CORREO,
    ):
        base = f"Transporte con datos logisticos incompletos CP {cp_txt}" if cp_txt else "Transporte con datos logisticos incompletos"
    elif tipo in (TIPO_ERROR_INTEGRACION, TIPO_ERROR_AUTENTICACION):
        base = f"Transporte requiere revision tecnica CP {cp_txt}" if cp_txt else "Transporte requiere revision tecnica"
    else:
        base = f"Transporte requiere revision CP {cp_txt}" if cp_txt else "Transporte requiere revision"

    if motivo_txt:
        return f"{base}: {motivo_txt}"

    return base



def _normalizar_revision_transporte(texto):
    import unicodedata
    import re

    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _tiene_sucursales_correo_resueltas(pedido):
    empresa = _normalizar_revision_transporte(
        getattr(pedido, "empresa_envio", "") or ""
    )
    tipo = _normalizar_revision_transporte(
        getattr(pedido, "tipo_entrega", "") or ""
    )

    if "correo" not in empresa:
        return False

    if "sucursal" not in tipo:
        return False

    if str(getattr(pedido, "sucursal_nombre", "") or "").strip():
        return True

    if str(getattr(pedido, "correo_sucursales_ofrecidas", "") or "").strip():
        return True

    return False


def _es_marca_revision_correo_resuelta(parte):
    texto = _normalizar_revision_transporte(parte)

    if not texto:
        return False

    menciona_correo = "correo" in texto
    menciona_transporte = "transporte" in texto or "cotizar" in texto

    if not (menciona_correo and menciona_transporte):
        return False

    patrones_resueltos = [
        "no se pudo cotizar correo",
        "revisar respuesta de la integracion",
        "transporte requiere revision tecnica",
        "error_integracion_correo",
    ]

    return any(patron in texto for patron in patrones_resueltos)


def _resumen_tiene_otro_pendiente_operador(resumen):
    texto = _normalizar_revision_transporte(resumen)

    if not texto:
        return False

    otros = [
        "cliente consulto sobre sucursal",
        "cliente consultó sobre sucursal",
        "cliente consulto horarios",
        "cliente consultó horarios",
        "horarios de retiro",
        "problema",
        "reclamo",
        "incidencia",
        "cross-sell",
        "revision de carga",
        "revisión de carga",
        "operador",
    ]

    return any(palabra in texto for palabra in otros)


def limpiar_revision_correo_resuelta_por_sucursales(pedido):
    """
    Si Correo ya ofreció o confirmó sucursales, limpia marcas viejas de
    error/revisión técnica de cotización Correo.

    No borra otros pendientes reales, como consulta de horarios, reclamos
    o revisión de carga.
    """
    if not pedido:
        return False

    if not _tiene_sucursales_correo_resueltas(pedido):
        return False

    resumen = str(getattr(pedido, "ia_resumen", "") or "").strip()
    if not resumen:
        return False

    partes = [p.strip() for p in resumen.split("|") if p.strip()]
    nuevas = []
    eliminadas = []

    for parte in partes:
        if _es_marca_revision_correo_resuelta(parte):
            eliminadas.append(parte)
        else:
            nuevas.append(parte)

    if not eliminadas:
        return False

    nuevo_resumen = " | ".join(nuevas).strip()
    pedido.ia_resumen = nuevo_resumen[:1000]

    if not _resumen_tiene_otro_pendiente_operador(nuevo_resumen):
        if hasattr(pedido, "ia_requiere_operador"):
            pedido.ia_requiere_operador = False
        if hasattr(pedido, "ml_mensajes_pendientes"):
            pedido.ml_mensajes_pendientes = False
        if hasattr(pedido, "ml_mensajes_pendientes_count"):
            pedido.ml_mensajes_pendientes_count = 0

    return True
