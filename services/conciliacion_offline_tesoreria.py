"""Lectura y conciliacion en memoria de extractos descargados manualmente."""

import csv
import hashlib
import io
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

LIMITE_FILAS = 2000
FORMATOS_FECHA = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d")


def _texto(valor):
    return str(valor or "").strip()


def _fecha(valor):
    texto = _texto(valor)
    for formato in FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            pass
    raise ValueError(f"Fecha invalida: {texto}.")


def _centavos(valor):
    texto = _texto(valor).replace("$", "").replace(" ", "")
    if not texto:
        raise ValueError("El importe es obligatorio.")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".") if texto.rfind(",") > texto.rfind(".") else texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return int((Decimal(texto) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except InvalidOperation as error:
        raise ValueError(f"Importe invalido: {valor}.") from error


def _normalizar_fila(fila, numero):
    datos = {str(k or "").strip().lower(): v for k, v in fila.items()}
    fecha_mov = _fecha(datos.get("fecha") or datos.get("date"))
    concepto = _texto(datos.get("concepto") or datos.get("descripcion") or datos.get("detalle"))
    referencia = _texto(datos.get("referencia") or datos.get("id") or datos.get("comprobante"))
    if "importe" in datos or "monto" in datos:
        importe = _centavos(datos.get("importe") if "importe" in datos else datos.get("monto"))
    else:
        credito = _centavos(datos["credito"]) if _texto(datos.get("credito")) else 0
        debito = _centavos(datos["debito"]) if _texto(datos.get("debito")) else 0
        importe = credito - debito
    if importe == 0:
        raise ValueError("El importe no puede ser cero.")
    clave = hashlib.sha256(f"{fecha_mov.isoformat()}|{importe}|{concepto.lower()}|{referencia.lower()}".encode("utf-8")).hexdigest()
    return {"fila": numero, "fecha": fecha_mov.isoformat(), "tipo": "ingreso" if importe > 0 else "egreso",
            "importe_centavos": abs(importe), "concepto": concepto[:220], "referencia": referencia[:140], "clave_extracto": clave}


def leer_extracto(contenido, nombre_archivo):
    if not contenido:
        raise ValueError("El extracto esta vacio.")
    if len(contenido) > 2_000_000:
        raise ValueError("El extracto supera 2 MB.")
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("El extracto debe estar codificado en UTF-8.") from error
    nombre = _texto(nombre_archivo).lower()
    if nombre.endswith(".json"):
        bruto = json.loads(texto)
        filas = bruto.get("movimientos", bruto) if isinstance(bruto, dict) else bruto
        if not isinstance(filas, list):
            raise ValueError("El JSON debe contener una lista de movimientos.")
    elif nombre.endswith(".csv"):
        muestra = texto[:4096]
        delimitador = ";" if muestra.count(";") > muestra.count(",") else ","
        filas = list(csv.DictReader(io.StringIO(texto), delimiter=delimitador))
    else:
        raise ValueError("Solo se admiten extractos CSV o JSON.")
    if len(filas) > LIMITE_FILAS:
        raise ValueError(f"El extracto supera {LIMITE_FILAS} movimientos.")
    normalizadas = []
    errores = []
    vistas = set()
    for numero, fila in enumerate(filas, 2):
        try:
            if not isinstance(fila, dict):
                raise ValueError("La fila no es un objeto.")
            item = _normalizar_fila(fila, numero)
            item["duplicado_en_archivo"] = item["clave_extracto"] in vistas
            vistas.add(item["clave_extracto"])
            normalizadas.append(item)
        except (ValueError, TypeError) as error:
            errores.append({"fila": numero, "error": str(error)})
    return normalizadas, errores


def conciliar_extracto(*, organizacion_id, unidad_negocio_id, cuenta_id, contenido, nombre_archivo, proyecciones):
    movimientos, errores = leer_extracto(contenido, nombre_archivo)
    disponibles = []
    for p in proyecciones:
        if int(p.organizacion_id) != int(organizacion_id) or int(p.unidad_negocio_id) != int(unidad_negocio_id):
            continue
        if int(p.cuenta_tesoreria_id) != int(cuenta_id) or p.estado != "proyectado" or p.confirmado or p.afecta_saldo:
            continue
        disponibles.append(p)
    candidatos = []
    usados = set()
    for movimiento in movimientos:
        opciones = []
        if not movimiento["duplicado_en_archivo"]:
            fecha_mov = date.fromisoformat(movimiento["fecha"])
            for p in disponibles:
                if int(p.id) in usados or p.tipo != movimiento["tipo"] or int(p.importe_centavos) != int(movimiento["importe_centavos"]):
                    continue
                distancia = abs((p.fecha_prevista - fecha_mov).days)
                if distancia <= 7:
                    opciones.append((distancia, int(p.id), p))
        opciones.sort(key=lambda x: (x[0], x[1]))
        elegido = opciones[0][2] if opciones else None
        if elegido is not None:
            usados.add(int(elegido.id))
        candidatos.append({**movimiento, "proyeccion_id": getattr(elegido, "id", None),
            "dias_diferencia": opciones[0][0] if elegido is not None else None,
            "estado_conciliacion": "candidato" if elegido is not None else ("duplicado" if movimiento["duplicado_en_archivo"] else "sin_coincidencia")})
    resultado = {"organizacion_id": int(organizacion_id), "unidad_negocio_id": int(unidad_negocio_id),
        "cuenta_id": int(cuenta_id), "modo": "conciliacion_offline_no_ejecutable", "archivo": _texto(nombre_archivo),
        "resumen": {"filas_validas": len(movimientos), "errores": len(errores),
                    "duplicados": sum(x["duplicado_en_archivo"] for x in movimientos),
                    "candidatos": sum(x["estado_conciliacion"] == "candidato" for x in candidatos),
                    "sin_coincidencia": sum(x["estado_conciliacion"] == "sin_coincidencia" for x in candidatos)},
        "movimientos": candidatos, "errores": errores,
        "controles": {"persistencia": False, "conciliaciones_confirmadas": 0, "saldos_modificados": 0,
                      "pagos": 0, "cobros": 0, "asientos": 0, "conexiones_externas": 0}}
    resultado["huella_conciliacion"] = hashlib.sha256(json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return resultado


def exportar_conciliacion(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
