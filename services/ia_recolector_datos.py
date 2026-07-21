"""
Primitivas compartidas de datos del recolector IA.

No modifica pedidos.
No importa app.py.
No hace commit ni envía mensajes.
"""

import re
from typing import Any

from modules.bot_ml.billing import (
    parece_nickname_ml,
)
from services.ia_recolector_sync import (
    ia_cp_valido_recolector,
)
from services.telefonos import (
    normalizar_telefono_service,
)


def capitalizar_texto_fierro(valor: Any) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""

    texto = re.sub(r"\s+", " ", texto)
    minusculas = {
        "de",
        "del",
        "la",
        "las",
        "los",
        "y",
        "e",
    }
    siglas = {"dni", "cp"}

    partes = []
    for palabra in texto.split(" "):
        limpia = palabra.strip()
        if not limpia:
            continue

        base = re.sub(
            r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]",
            "",
            limpia,
        ).lower()

        if base in siglas:
            partes.append(limpia.upper())
        elif base in minusculas:
            partes.append(limpia.lower())
        else:
            partes.append(
                "-".join([
                    (
                        parte[:1].upper()
                        + parte[1:].lower()
                        if parte
                        else parte
                    )
                    for parte in limpia.split("-")
                ])
            )

    return " ".join(partes).strip()


def normalizar_direccion_fierro(valor: Any) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""

    texto = re.sub(r"\s+", " ", texto)
    reemplazos = [
        (r"\bav\.?\b", "Av."),
        (r"\bavenida\b", "Av."),
        (r"\bcalle\b", "Calle"),
        (r"\bnro\.?\b", "N°"),
        (r"\bnº\b", "N°"),
        (r"\bnumero\b", "N°"),
        (r"\bpiso\b", "Piso"),
        (r"\bdpto\.?\b", "Dpto."),
        (r"\bdepartamento\b", "Dpto."),
    ]

    texto = capitalizar_texto_fierro(texto)

    for patron, reemplazo in reemplazos:
        texto = re.sub(
            patron,
            reemplazo,
            texto,
            flags=re.IGNORECASE,
        )

    return texto.strip()


def ia_campo_vacio(valor: Any) -> bool:
    return not str(valor or "").strip()


def ia_dni_valido(valor: Any) -> str:
    limpio = re.sub(
        r"\D+",
        "",
        str(valor or ""),
    )
    return limpio if len(limpio) in (7, 8) else ""


def ia_cp_valido(valor: Any) -> str:
    return ia_cp_valido_recolector(valor)


def ia_texto_menciona_autorizado(texto: Any) -> bool:
    t = str(texto or "").lower()
    patrones = [
        r"\bquien\s+recibe\b",
        r"\bquien\s+retira\b",
        r"\bquien\s+va\s+a\s+recibir\b",
        r"\bquien\s+va\s+a\s+retirar\b",
        r"\bel\s+que\s+recibe\b",
        r"\bla\s+que\s+recibe\b",
        r"\bel\s+que\s+retira\b",
        r"\bla\s+que\s+retira\b",
        r"\brecibe\s+[^,.]{2,80}",
        r"\bretira\s+[^,.]{2,80}",
        r"\bretirar\s+[^,.]{2,80}",
        r"\bautorizad[oa]\b",
        r"\bautorizo\s+a\b",
        r"\bentregar\s+a\b",
        r"\bentrega\s+a\b",
        r"\bse\s+lo\s+entregan\s+a\b",
        r"\ba\s+nombre\s+de\b",
    ]

    return any(
        re.search(patron, t)
        for patron in patrones
    )


def normalizar_datos_ia_fierro(
    datos: Any,
) -> dict[str, Any]:
    if not isinstance(datos, dict):
        return {}

    normalizados = dict(datos)

    for campo in [
        "nombre",
        "apellido",
        "localidad",
        "autorizado_nombre",
    ]:
        if normalizados.get(campo):
            normalizados[campo] = (
                capitalizar_texto_fierro(
                    normalizados.get(campo)
                )
            )

    if normalizados.get("direccion"):
        normalizados["direccion"] = (
            normalizar_direccion_fierro(
                normalizados.get("direccion")
            )
        )

    if normalizados.get("dni"):
        normalizados["dni"] = (
            ia_dni_valido(
                normalizados.get("dni")
            )
            or str(
                normalizados.get("dni") or ""
            ).strip()
        )

    if normalizados.get("autorizado_dni"):
        normalizados["autorizado_dni"] = (
            ia_dni_valido(
                normalizados.get("autorizado_dni")
            )
            or str(
                normalizados.get(
                    "autorizado_dni"
                )
                or ""
            ).strip()
        )

    if normalizados.get("autorizado_telefono"):
        normalizados["autorizado_telefono"] = (
            normalizar_telefono_service(
                normalizados.get(
                    "autorizado_telefono"
                )
            )
        )

    if normalizados.get("codigo_postal"):
        normalizados["codigo_postal"] = str(
            normalizados.get("codigo_postal")
            or ""
        ).strip().upper()

    return normalizados


def ia_extraer_datos_clasico_fierro(texto_cliente, datos_previos=None):
    """Parser APB determinístico para datos críticos.

    Motivo: en ML/WhatsApp muchos clientes contestan solo "1617",
    "CP 1617", "Código postal 1617", "32339954" o "DNI 37331234".
    No puede depender solo de la IA porque si falla se repregunta un dato ya pasado.
    Este parser solo completa datos con alta confianza y no pisa valores previos.
    """
    datos_previos = datos_previos or {}
    texto_original = str(texto_cliente or "").strip()
    texto = texto_original.lower()
    extraidos = {}

    def falta(campo):
        return not str((datos_previos or {}).get(campo) or "").strip()

    # DNI etiquetado: DNI: 37331234 / Documento 37.331.234 / doc 37331234
    m_dni = re.search(
        r"(?:\bd\.?n\.?i\.?\b|\bdni\b|\bdocumento\b|\bdoc\.?\b)\s*[:#-]?\s*([0-9][0-9\.\s-]{5,15}[0-9])",
        texto_original,
        flags=re.IGNORECASE,
    )
    if m_dni and falta("dni"):
        dni = ia_dni_valido(m_dni.group(1))
        if dni:
            extraidos["dni"] = dni

    # CP etiquetado: CP 1617 / C.P.: 1888 / Código postal 1617 / codigo postal: 1617
    m_cp = re.search(
        r"(?:\bc\.?p\.?\b|\bcod(?:igo)?\s*postal\b|\bcódigo\s*postal\b|\bpostal\b)\s*[:#-]?\s*([A-Za-z]?[0-9]{3,5}[A-Za-z]{0,3})",
        texto_original,
        flags=re.IGNORECASE,
    )
    if m_cp and falta("codigo_postal"):
        cp = ia_cp_valido(m_cp.group(1).strip().upper())
        if cp:
            extraidos["codigo_postal"] = cp

    # Respuesta suelta: "1617" cuando falta CP.
    # Para evitar confundir con DNI/teléfono, solo se usa si el mensaje es básicamente un único valor de 4 dígitos.
    solo_numero = re.fullmatch(r"\s*(\d{4})\s*", texto_original)
    if solo_numero and falta("codigo_postal"):
        extraidos.setdefault("codigo_postal", solo_numero.group(1))

    # Respuesta suelta: "32339954" / "32.339.954" cuando falta DNI.
    # En Argentina lo tratamos como DNI solo si, al limpiar separadores,
    # queda con 7 u 8 dígitos.
    solo_dni = re.fullmatch(r"\s*([0-9][0-9\s.,-]{5,16}[0-9])\s*", texto_original)
    if solo_dni and falta("dni"):
        dni = ia_dni_valido(solo_dni.group(1))
        if dni:
            extraidos.setdefault("dni", dni)

    # Teléfono etiquetado: tel: 3624100059 / teléfono 2923... / cel 11...
    m_tel = re.search(
        r"(?:\btel[eé]fono\b|\btel\.?\b|\bcelular\b|\bcel\.?\b|\bcontacto\b)\s*[:#-]?\s*(\+?[0-9][0-9\s().-]{5,22}[0-9])",
        texto_original,
        flags=re.IGNORECASE,
    )

    tel_detectado = ""
    tel_span = None

    if m_tel:
        tel_detectado = normalizar_telefono_service(m_tel.group(1))
        tel_span = m_tel.span(1)

        if tel_detectado and falta("telefono"):
            extraidos.setdefault("telefono", tel_detectado)

    # DNI embebido en mensaje compacto:
    # "Nombre Apellido - 40.789.161 - Dirección - tel: 3624..."
    # Permitimos puntos, espacios, comas o guiones, pero validamos
    # que limpio tenga 7 u 8 dígitos.
    if falta("dni") and not extraidos.get("dni"):
        candidatos_dni = []

        for m in re.finditer(r"\b([0-9][0-9\s.,-]{5,16}[0-9])\b", texto_original):
            if tel_span and tel_span[0] <= m.start(1) <= tel_span[1]:
                continue

            valor = ia_dni_valido(m.group(1))
            if valor:
                candidatos_dni.append((valor, m.span(1)))

        if len(candidatos_dni) == 1:
            extraidos.setdefault("dni", candidatos_dni[0][0])

    # Dirección/localidad en formato compacto de alta confianza:
    # "Nombre - DNI - Mayor Torres 634 Zapala Neuquén - tel: 3624..."
    # Solo se usa si hay DNI y teléfono, para no inventar datos en mensajes ambiguos.
    try:
        dni_para_segmento = extraidos.get("dni") or ""

        if dni_para_segmento and tel_span and (falta("direccion") or falta("localidad")):
            # Buscamos el DNI original en el texto, permitiendo separadores.
            dni_regex = r"\s*[.\s,-]*".join(list(dni_para_segmento))
            m_dni_original = re.search(dni_regex, texto_original)

            if m_dni_original:
                idx_fin_dni = m_dni_original.end()
                idx_tel = tel_span[0]

                if idx_tel > idx_fin_dni:
                    segmento = texto_original[idx_fin_dni:idx_tel]
                    segmento = re.sub(r"^[\s\-:|,]+", "", segmento)
                    segmento = re.sub(r"[\s\-:|,]+$", "", segmento)
                    segmento = re.sub(r"\s+", " ", segmento).strip()

                    provincias = [
                        "Buenos Aires", "CABA", "Capital Federal", "Catamarca", "Chaco",
                        "Chubut", "Córdoba", "Cordoba", "Corrientes", "Entre Ríos",
                        "Entre Rios", "Formosa", "Jujuy", "La Pampa", "La Rioja",
                        "Mendoza", "Misiones", "Neuquén", "Neuquen", "Río Negro",
                        "Rio Negro", "Salta", "San Juan", "San Luis", "Santa Cruz",
                        "Santa Fe", "Santiago del Estero", "Tierra del Fuego", "Tucumán",
                        "Tucuman",
                    ]

                    segmento_sin_provincia = segmento

                    for provincia in sorted(provincias, key=len, reverse=True):
                        if re.search(
                            rf"\b{re.escape(provincia)}\b\s*$",
                            segmento_sin_provincia,
                            flags=re.IGNORECASE,
                        ):
                            segmento_sin_provincia = re.sub(
                                rf"\b{re.escape(provincia)}\b\s*$",
                                "",
                                segmento_sin_provincia,
                                flags=re.IGNORECASE,
                            ).strip(" -,.")
                            break

                    # Buscar número de calle.
                    # Todo hasta el número queda como dirección.
                    # Lo posterior, si existe, se toma como localidad.
                    m_numero_calle = re.search(r"\b\d{1,6}\b", segmento_sin_provincia)

                    if m_numero_calle:
                        fin_numero = m_numero_calle.end()
                        direccion = segmento_sin_provincia[:fin_numero].strip(" -,.")
                        localidad = segmento_sin_provincia[fin_numero:].strip(" -,.")

                        if direccion and falta("direccion"):
                            extraidos.setdefault("direccion", direccion)

                        # APB / modularización:
                        # El parser clásico solo propone una localidad candidata.
                        # La validación final vive en services.ubicacion_cp para no
                        # duplicar reglas dentro de app.py.
                        if localidad and falta("localidad"):
                            extraidos.setdefault("localidad", localidad)

                    elif segmento_sin_provincia and falta("direccion"):
                        extraidos.setdefault("direccion", segmento_sin_provincia)

    except Exception:
        pass

    return extraidos


def ia_autocompletar_pedido_con_datos(pedido, datos, texto_cliente=""):
    """
    Fase 4 segura: usa datos detectados por IA para completar la carga.
    Regla APB: solo completa campos vacíos. No pisa datos ya cargados manualmente,
    salvo cliente cuando todavía parece nick de Mercado Libre. No cambia estados.
    """
    if not pedido or not isinstance(datos, dict):
        return []

    completados = []

    datos = normalizar_datos_ia_fierro(datos)

    nombre = str(datos.get("nombre") or "").strip()
    apellido = str(datos.get("apellido") or "").strip()
    nombre_completo = " ".join([x for x in [nombre, apellido] if x]).strip()

    autorizado_nombre = str(datos.get("autorizado_nombre") or "").strip()
    autorizado_dni = ia_dni_valido(datos.get("autorizado_dni"))
    autorizado_telefono = normalizar_telefono_service(datos.get("autorizado_telefono")) if datos.get("autorizado_telefono") else ""
    texto_indica_autorizado = ia_texto_menciona_autorizado(texto_cliente)

    if texto_indica_autorizado:
        # APB: si el texto habla de quien recibe/retira/autorizado, NO pisar titular.
        # Si la IA no separó los campos, usamos los datos comunes como autorizado.
        autorizado_nombre = autorizado_nombre or nombre_completo
        autorizado_dni = autorizado_dni or ia_dni_valido(datos.get("dni"))
        autorizado_telefono = autorizado_telefono or (normalizar_telefono_service(datos.get("telefono")) if datos.get("telefono") else "")

        if autorizado_nombre and ia_campo_vacio(getattr(pedido, "autorizado_nombre", "")):
            pedido.autorizado_nombre = autorizado_nombre
            completados.append("autorizado_nombre")
        if autorizado_dni and ia_campo_vacio(getattr(pedido, "autorizado_dni", "")):
            pedido.autorizado_dni = autorizado_dni
            completados.append("autorizado_dni")
        if autorizado_telefono and ia_campo_vacio(getattr(pedido, "autorizado_telefono", "")):
            pedido.autorizado_telefono = autorizado_telefono
            completados.append("autorizado_telefono")
    else:
        cliente_actual = str(getattr(pedido, "cliente", "") or "").strip()
        puede_reemplazar_cliente = ia_campo_vacio(cliente_actual) or parece_nickname_ml(cliente_actual, getattr(pedido, "ml_buyer_nickname", ""))
        if nombre_completo and puede_reemplazar_cliente:
            pedido.cliente = nombre_completo
            completados.append("cliente")

        dni = ia_dni_valido(datos.get("dni"))
        if dni and ia_campo_vacio(getattr(pedido, "dni", "")):
            pedido.dni = dni
            completados.append("dni")

        telefono = normalizar_telefono_service(datos.get("telefono"))
        if telefono and ia_campo_vacio(getattr(pedido, "telefono", "")):
            pedido.telefono = telefono
            completados.append("telefono")

    direccion = str(datos.get("direccion") or "").strip()
    if direccion and ia_campo_vacio(getattr(pedido, "direccion", "")):
        pedido.direccion = direccion
        completados.append("direccion")

    localidad = str(datos.get("localidad") or "").strip()

    # APB / modularización:
    # La localidad detectada por IA/parser clásico NO se guarda cruda.
    # Pasa por services.ubicacion_cp para evitar contaminar el pedido con
    # restos del mensaje como "de Mayo 670 Teléfono".
    try:
        from services.ubicacion_cp import limpiar_localidad_detectada

        localidad = limpiar_localidad_detectada(
            localidad,
            texto_cliente=texto_cliente,
        )

    except Exception as e:
        print(
            f"[UBICACION] No se pudo validar localidad detectada "
            f"pedido #{getattr(pedido, 'id', '?')}: {e}"
        )

    if localidad and ia_campo_vacio(getattr(pedido, "localidad", "")):
        pedido.localidad = localidad
        completados.append("localidad")

    codigo_postal = ia_cp_valido(datos.get("codigo_postal"))
    if codigo_postal and ia_campo_vacio(getattr(pedido, "codigo_postal", "")):
        pedido.codigo_postal = codigo_postal
        completados.append("codigo_postal")

    # APB logística / SaaS:
    # Si tenemos CP/dirección, intentamos normalizar ubicación internamente.
    # Esto puede completar localidad/provincia, coordenadas y CPA si corresponde.
    # No se le pide al cliente un dato que el sistema puede resolver.
    try:
        from services.ubicacion_cp import normalizar_ubicacion_pedido

        resultado_ubicacion = normalizar_ubicacion_pedido(pedido)
        completados_ubicacion = resultado_ubicacion.get("completados", [])

        for campo in completados_ubicacion:
            if campo not in completados:
                completados.append(campo)

    except Exception as e:
        print(
            f"[UBICACION] No se pudo normalizar ubicación "
            f"pedido #{getattr(pedido, 'id', '?')}: {e}"
        )

    return completados
