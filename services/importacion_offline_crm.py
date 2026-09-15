"""Previsualización masiva del CRM por tenant, sin persistencia ni mensajería."""

import csv
import hashlib
import io
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


TIPOS = {"cliente", "oportunidad", "actividad"}
ESTADOS_CLIENTE = {"potencial", "cliente", "inactivo"}
ESTADOS_OPORTUNIDAD = {"abierta", "ganada", "perdida", "cancelada"}
ESTADOS_ACTIVIDAD = {"pendiente", "completada", "cancelada"}
ALIASES = {
    "tipo": {"tipo", "tipo registro", "registro"},
    "codigo": {"codigo", "codigo cliente", "cliente codigo"},
    "nombre": {"nombre", "cliente", "razon social"},
    "unidad": {"unidad", "unidad negocio", "codigo unidad"},
    "documento": {"documento", "dni", "cuit"},
    "email": {"email", "correo"},
    "telefono": {"telefono", "whatsapp"},
    "canal": {"canal", "canal identidad"},
    "identidad": {"identidad externa", "identificador externo", "id externo"},
    "referencia": {"referencia", "codigo oportunidad", "oportunidad"},
    "titulo": {"titulo", "asunto"},
    "etapa": {"etapa", "codigo etapa"},
    "estado": {"estado"},
    "importe": {"importe", "importe estimado"},
    "probabilidad": {"probabilidad", "probabilidad porcentaje"},
    "detalle": {"detalle", "descripcion", "observaciones"},
}


def _normalizar(valor):
    texto = unicodedata.normalize("NFKD", str(valor or "").strip().lower())
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).replace("_", " ").split())


def _texto(contenido):
    if not contenido:
        raise ValueError("El archivo está vacío.")
    if len(contenido) > 2_000_000:
        raise ValueError("El archivo supera el límite de 2 MB.")
    for codificacion in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    raise ValueError("No se pudo leer la codificación del archivo.")


def _columnas(encabezados):
    resultado = {}
    for indice, encabezado in enumerate(encabezados or []):
        limpio = _normalizar(encabezado)
        for campo, aliases in ALIASES.items():
            if campo not in resultado and limpio in {_normalizar(a) for a in aliases}:
                resultado[campo] = indice
    faltantes = [campo for campo in ("tipo", "codigo", "nombre") if campo not in resultado]
    if faltantes:
        raise ValueError("Faltan columnas: " + ", ".join(faltantes) + ".")
    return resultado


def _centavos(valor):
    texto = str(valor or "0").strip().replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    try:
        numero = Decimal(texto or "0")
    except InvalidOperation as error:
        raise ValueError("El importe no es válido.") from error
    if numero < 0:
        raise ValueError("El importe no puede ser negativo.")
    return int((numero * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def previsualizar_importacion(contenido, *, organizacion_id, unidades, etapas, clientes, identidades):
    """Genera un plan inmutable y tenant-aware; no recibe sesión de base de datos."""
    texto = _texto(contenido)
    try:
        dialecto = csv.Sniffer().sniff(texto[:4096], delimiters=",;\t")
    except csv.Error as error:
        raise ValueError("No se pudo reconocer el separador del archivo.") from error
    lector = csv.reader(io.StringIO(texto), dialecto)
    columnas = _columnas(next(lector, None))
    unidades_tenant = {_normalizar(x.codigo): x.id for x in unidades if x.organizacion_id == organizacion_id}
    etapas_tenant = {_normalizar(x.codigo): x.id for x in etapas if x.organizacion_id == organizacion_id}
    codigos_existentes = {_normalizar(x.codigo) for x in clientes if x.organizacion_id == organizacion_id}
    identidades_existentes = {
        (_normalizar(x.canal), str(x.identificador_externo or "").strip())
        for x in identidades if x.organizacion_id == organizacion_id
    }
    codigos_archivo = set()
    identidades_archivo = set()
    referencias = set()
    filas = []

    for numero, valores in enumerate(lector, 2):
        if not any(str(v).strip() for v in valores):
            continue
        if len(filas) >= 1000:
            raise ValueError("El archivo supera las 1000 filas.")
        if sum(len(str(v)) for v in valores) > 5000:
            raise ValueError(f"La fila {numero} supera el tamaño permitido.")

        def valor(campo):
            indice = columnas.get(campo)
            return valores[indice].strip() if indice is not None and indice < len(valores) else ""

        tipo = _normalizar(valor("tipo"))
        codigo = valor("codigo")[:80]
        codigo_normalizado = _normalizar(codigo)
        errores = []
        if tipo not in TIPOS:
            errores.append("Tipo de registro inválido")
        if not codigo:
            errores.append("Falta el código de cliente")
        elif tipo == "cliente" and (codigo_normalizado in codigos_existentes or codigo_normalizado in codigos_archivo):
            errores.append("El código de cliente ya existe o está duplicado")
        elif tipo != "cliente" and codigo_normalizado not in codigos_existentes | codigos_archivo:
            errores.append("El cliente referenciado no pertenece al tenant ni al archivo")
        if tipo == "cliente":
            codigos_archivo.add(codigo_normalizado)

        unidad = _normalizar(valor("unidad"))
        if unidad and unidad not in unidades_tenant:
            errores.append("La unidad de negocio no pertenece al tenant")
        estado = _normalizar(valor("estado")) or {
            "cliente": "potencial", "oportunidad": "abierta", "actividad": "pendiente"
        }.get(tipo, "")
        permitidos = {
            "cliente": ESTADOS_CLIENTE,
            "oportunidad": ESTADOS_OPORTUNIDAD,
            "actividad": ESTADOS_ACTIVIDAD,
        }.get(tipo, set())
        if estado not in permitidos:
            errores.append("El estado no es válido para el tipo de registro")

        email = valor("email")[:200]
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errores.append("El correo electrónico no tiene formato válido")
        canal = _normalizar(valor("canal"))
        identidad = valor("identidad")[:150]
        clave_identidad = (canal, identidad)
        if bool(canal) != bool(identidad):
            errores.append("Canal e identidad externa deben informarse juntos")
        elif canal and (clave_identidad in identidades_existentes or clave_identidad in identidades_archivo):
            errores.append("La identidad externa ya existe o está duplicada")
        elif canal:
            identidades_archivo.add(clave_identidad)

        referencia = valor("referencia")[:100]
        etapa = _normalizar(valor("etapa"))
        importe = 0
        probabilidad = 0
        if tipo == "oportunidad":
            if not referencia or referencia in referencias:
                errores.append("La referencia de oportunidad falta o está duplicada")
            referencias.add(referencia)
            if etapa and etapa not in etapas_tenant:
                errores.append("La etapa no pertenece al tenant")
            try:
                importe = _centavos(valor("importe"))
                probabilidad = int(valor("probabilidad") or 0)
                if not 0 <= probabilidad <= 100:
                    raise ValueError
            except ValueError:
                errores.append("Importe o probabilidad inválidos")
        if tipo in {"cliente", "oportunidad", "actividad"} and not valor("nombre"):
            errores.append("Falta el nombre, título o asunto")

        filas.append({
            "numero": numero,
            "tipo": tipo,
            "codigo_cliente": codigo,
            "nombre": valor("nombre")[:200],
            "unidad_negocio_id": unidades_tenant.get(unidad),
            "documento": valor("documento")[:30],
            "email": email,
            "telefono": valor("telefono")[:50],
            "canal": canal,
            "identificador_externo": identidad,
            "referencia": referencia,
            "etapa_crm_id": etapas_tenant.get(etapa),
            "estado": estado,
            "importe_estimado_centavos": importe,
            "probabilidad": probabilidad,
            "detalle": valor("detalle")[:500],
            "errores": errores,
            "resultado": "rechazado" if errores else "preparado",
        })

    if not filas:
        raise ValueError("El archivo no contiene registros.")
    resumen = {
        "filas": len(filas),
        "clientes": sum(x["tipo"] == "cliente" for x in filas),
        "oportunidades": sum(x["tipo"] == "oportunidad" for x in filas),
        "actividades": sum(x["tipo"] == "actividad" for x in filas),
        "preparados": sum(x["resultado"] == "preparado" for x in filas),
        "rechazados": sum(x["resultado"] == "rechazado" for x in filas),
        "escrituras": 0,
        "mensajes_enviados": 0,
        "acciones_externas": 0,
    }
    resultado = {
        "organizacion_id": organizacion_id,
        "modo": "offline",
        "huella_documento": hashlib.sha256(contenido).hexdigest(),
        "resumen": resumen,
        "filas": filas,
        "confirmacion_habilitada": False,
        "automatizaciones": False,
    }
    resultado["huella_plan"] = hashlib.sha256(
        json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return resultado


def exportar_previsualizacion(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
