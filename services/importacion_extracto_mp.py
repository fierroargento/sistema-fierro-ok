"""Normaliza extractos CSV de Mercado Pago sin conectarse a su API."""

import csv
import hashlib
import io
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

from services.conciliacion_liquidaciones_canal import registrar_movimiento
from services.importacion_productos_costeo import normalizar


ALIASES = {
    "movimiento": {"movement id", "movement_id", "id movimiento", "id"},
    "venta": {"source id", "source_id", "external reference", "external_reference", "id venta", "venta"},
    "pago": {"payment id", "payment_id", "id pago", "pago"},
    "fecha": {"date", "date created", "date_created", "fecha", "fecha movimiento"},
    "neto": {"net amount", "net_amount", "settlement net amount", "settlement_net_amount", "importe neto", "neto"},
    "estado": {"status", "estado"},
    "detalle": {"description", "detalle", "concepto", "record type", "record_type"},
}


def _texto(contenido):
    if len(contenido or b"") > 2_000_000:
        raise ValueError("El extracto supera el limite de 2 MB.")
    for codificacion in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return (contenido or b"").decode(codificacion)
        except UnicodeDecodeError:
            pass
    raise ValueError("No se pudo leer la codificacion del extracto.")


def _columnas(encabezados):
    resultado = {}
    for indice, encabezado in enumerate(encabezados or []):
        limpio = normalizar(encabezado).replace("_", " ")
        for campo, aliases in ALIASES.items():
            if campo not in resultado and limpio in {normalizar(alias).replace("_", " ") for alias in aliases}:
                resultado[campo] = indice
    faltantes = [campo for campo in ("movimiento", "venta", "fecha", "neto") if campo not in resultado]
    if faltantes:
        raise ValueError("Faltan columnas del extracto: " + ", ".join(faltantes) + ".")
    return resultado


def _centavos(valor):
    texto = str(valor or "").strip().replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    try:
        return int((Decimal(texto) * 100).quantize(Decimal("1")))
    except InvalidOperation as error:
        raise ValueError("El importe neto no es valido.") from error


def _fecha(valor):
    texto = str(valor or "").strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(texto).replace(tzinfo=None).isoformat()
    except ValueError:
        for formato in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(texto, formato).isoformat()
            except ValueError:
                pass
    raise ValueError("La fecha del movimiento no es valida.")


def previsualizar_extracto_mp(contenido, *, cuenta_codigo, ventas, movimientos_existentes, organizacion_id, unidad_negocio_id):
    cuenta = str(cuenta_codigo or "").strip()
    if not cuenta:
        raise ValueError("La cuenta MP es obligatoria.")
    texto = _texto(contenido)
    huella_documento = hashlib.sha256(contenido).hexdigest()
    dialecto = csv.Sniffer().sniff(texto[:4096], delimiters=",;\t")
    lector = csv.reader(io.StringIO(texto), dialecto)
    encabezados = next(lector, None)
    columnas = _columnas(encabezados)
    ventas_propias = {(v.cuenta_codigo, v.referencia_venta) for v in ventas if v.organizacion_id == organizacion_id and v.unidad_negocio_id == unidad_negocio_id}
    existentes = {(m.cuenta_codigo, m.referencia_movimiento) for m in movimientos_existentes if m.organizacion_id == organizacion_id and m.unidad_negocio_id == unidad_negocio_id}
    vistos = set(); filas = []
    for numero, valores in enumerate(lector, 2):
        if not any(str(valor).strip() for valor in valores):
            continue
        errores = []
        def valor(campo):
            indice = columnas.get(campo)
            return valores[indice] if indice is not None and indice < len(valores) else ""
        movimiento = str(valor("movimiento")).strip(); venta = str(valor("venta")).strip()
        identidad = (cuenta, movimiento)
        if not movimiento or not venta:
            errores.append("Falta la identidad del movimiento o de la venta")
        if identidad in vistos or identidad in existentes:
            errores.append("El movimiento ya existe o esta duplicado")
        vistos.add(identidad)
        if (cuenta, venta) not in ventas_propias:
            errores.append("No existe la venta para esa cuenta en la unidad activa")
        try:
            importe_firmado = _centavos(valor("neto"))
        except ValueError as error:
            importe_firmado = 0; errores.append(str(error))
        try:
            fecha = _fecha(valor("fecha"))
        except ValueError as error:
            fecha = None; errores.append(str(error))
        estado_origen = normalizar(valor("estado"))
        if estado_origen in {"cancelled", "cancelado", "rejected", "rechazado"}:
            errores.append("El movimiento esta cancelado o rechazado en el extracto")
        datos = {
            "cuenta_codigo": cuenta, "referencia_venta": venta,
            "referencia_pago": str(valor("pago")).strip() or None,
            "referencia_movimiento": movimiento, "tipo": "liquidacion_neta",
            "direccion": "credito" if importe_firmado >= 0 else "debito",
            "importe_centavos": abs(importe_firmado), "impacta_saldo": True,
            "estado": "confirmado", "fecha_movimiento": fecha,
            "detalle": str(valor("detalle")).strip() or "Extracto MP offline",
        }
        filas.append({"numero": numero, "accion": "rechazado" if errores else "crear", "errores": errores, "datos": datos})
        if len(filas) > 500:
            raise ValueError("El extracto supera el limite de 500 movimientos.")
    if not filas:
        raise ValueError("El extracto no contiene movimientos.")
    return {"filas": filas, "huella_documento": huella_documento, "cuenta_codigo": cuenta, "resumen": {"total": len(filas), "validos": sum(f["accion"] == "crear" for f in filas), "rechazados": sum(f["accion"] == "rechazado" for f in filas), "acciones_externas": 0}}


def serializar_vista(vista):
    return json.dumps(vista, ensure_ascii=False, separators=(",", ":"))


def deserializar_vista(documento):
    vista = json.loads(documento or "{}")
    if not isinstance(vista.get("filas"), list) or len(vista["filas"]) > 500:
        raise ValueError("La vista previa MP no es valida.")
    return vista


def validar_confirmacion(vista, *, ventas, movimientos_existentes, organizacion_id, unidad_negocio_id):
    """Revalida el documento del formulario contra el estado actual del tenant."""
    ventas_propias = {(v.cuenta_codigo, v.referencia_venta) for v in ventas if v.organizacion_id == organizacion_id and v.unidad_negocio_id == unidad_negocio_id}
    existentes = {(m.cuenta_codigo, m.referencia_movimiento) for m in movimientos_existentes if m.organizacion_id == organizacion_id and m.unidad_negocio_id == unidad_negocio_id}
    vistos = set()
    for fila in vista.get("filas", []):
        if fila.get("accion") != "crear" or fila.get("errores"):
            raise ValueError("El lote contiene filas no aprobadas.")
        datos = fila.get("datos") or {}
        identidad = (str(datos.get("cuenta_codigo") or ""), str(datos.get("referencia_movimiento") or ""))
        venta = (identidad[0], str(datos.get("referencia_venta") or ""))
        if identidad in vistos or identidad in existentes:
            raise ValueError("Un movimiento del lote ya existe o esta duplicado.")
        if venta not in ventas_propias:
            raise ValueError("Una venta del lote no pertenece a la unidad activa.")
        if datos.get("tipo") != "liquidacion_neta" or datos.get("direccion") not in {"credito", "debito"} or not datos.get("impacta_saldo"):
            raise ValueError("El contrato economico del movimiento fue alterado.")
        if not isinstance(datos.get("importe_centavos"), int) or datos["importe_centavos"] < 0:
            raise ValueError("El importe del movimiento fue alterado.")
        _fecha(datos.get("fecha_movimiento"))
        vistos.add(identidad)
    return vista


def aplicar_extracto_mp(vista, *, organizacion_id, unidad_negocio_id, usuario, nombre_archivo, MovimientoLiquidacionCanal, LoteImportacionMP, db_session):
    if any(fila.get("accion") == "rechazado" for fila in vista.get("filas", [])):
        raise ValueError("El lote contiene filas rechazadas; corregilo antes de confirmar.")
    huella=str(vista.get("huella_documento") or "")
    if len(huella)!=64: raise ValueError("Falta la huella integra del extracto.")
    if LoteImportacionMP.query.filter_by(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,huella_documento=huella).first(): raise ValueError("Este extracto MP ya fue importado.")
    try:
        lote=LoteImportacionMP(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,cuenta_codigo=vista.get("cuenta_codigo"),nombre_archivo=str(nombre_archivo or "extracto.csv")[:255],huella_documento=huella,estado="confirmado",total_filas=len(vista.get("filas",[])),movimientos_creados=len(vista.get("filas",[])),rechazados=0,evidencia_json=json.dumps(vista,ensure_ascii=False,sort_keys=True,separators=(",",":")),puede_ejecutar=False,creado_por_usuario_id=getattr(usuario,"id",None),creado_por_username=getattr(usuario,"username",None))
        db_session.add(lote)
        for fila in vista.get("filas", []):
            datos = dict(fila["datos"])
            datos["fecha_movimiento"] = datetime.fromisoformat(datos["fecha_movimiento"])
            registrar_movimiento(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,origen="extracto_mp",usuario=usuario,MovimientoLiquidacionCanal=MovimientoLiquidacionCanal,db_session=db_session,commit=False,**datos)
        db_session.commit()
    except Exception:
        db_session.rollback(); raise
    return lote

def resumir_lotes(lotes, *, organizacion_id, unidad_negocio_id):
    propios=[l for l in (lotes or []) if l.organizacion_id==organizacion_id and l.unidad_negocio_id==unidad_negocio_id];propios.sort(key=lambda l:(l.fecha_creacion,l.id),reverse=True)
    return {"lotes":propios,"total":len(propios),"movimientos":sum(l.movimientos_creados for l in propios),"acciones_externas":0}

def exportar_evidencia_lote(lote):
    documento={"id":lote.id,"organizacion_id":lote.organizacion_id,"unidad_negocio_id":lote.unidad_negocio_id,"cuenta_codigo":lote.cuenta_codigo,"nombre_archivo":lote.nombre_archivo,"huella_documento":lote.huella_documento,"estado":lote.estado,"total_filas":lote.total_filas,"movimientos_creados":lote.movimientos_creados,"puede_ejecutar":False,"creado_por":lote.creado_por_username,"fecha_creacion":lote.fecha_creacion,"vista":json.loads(lote.evidencia_json)}
    return io.BytesIO(json.dumps(documento,ensure_ascii=False,sort_keys=True,indent=2,default=str).encode("utf-8"))
