"""Validador en memoria de borradores contables no contabilizables."""

import csv
import hashlib
import io
import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

LIMITE_LINEAS = 3000


def _centavos(valor):
    texto=str(valor or "0").strip().replace("$","").replace(" ","")
    if "," in texto and "." in texto:
        texto=texto.replace(".","").replace(",",".") if texto.rfind(",")>texto.rfind(".") else texto.replace(",","")
    elif "," in texto:texto=texto.replace(",",".")
    try:numero=Decimal(texto)
    except InvalidOperation as error:raise ValueError("Importe contable invalido.") from error
    if numero<0:raise ValueError("Debe y Haber no admiten negativos.")
    return int((numero*100).quantize(Decimal("1"),rounding=ROUND_HALF_UP))


def _fecha(valor):
    texto=str(valor or "").strip()
    for formato in ("%Y-%m-%d","%d/%m/%Y","%d-%m-%Y"):
        try:return datetime.strptime(texto,formato).date().isoformat()
        except ValueError:pass
    raise ValueError("Fecha contable invalida.")


def leer_borrador(contenido,nombre_archivo):
    if not contenido or len(contenido)>3_000_000:raise ValueError("El borrador esta vacio o supera 3 MB.")
    try:texto=contenido.decode("utf-8-sig")
    except UnicodeDecodeError as error:raise ValueError("El borrador debe estar codificado en UTF-8.") from error
    nombre=str(nombre_archivo or "").lower()
    if nombre.endswith(".json"):
        bruto=json.loads(texto);filas=bruto.get("lineas",bruto) if isinstance(bruto,dict) else bruto
    elif nombre.endswith(".csv"):
        delimitador=";" if texto[:4096].count(";")>texto[:4096].count(",") else ","
        filas=list(csv.DictReader(io.StringIO(texto),delimiter=delimitador))
    else:raise ValueError("Solo se admiten borradores CSV o JSON.")
    if not isinstance(filas,list) or len(filas)>LIMITE_LINEAS:raise ValueError(f"El borrador debe contener hasta {LIMITE_LINEAS} lineas.")
    lineas=[];errores=[];huellas=set()
    for numero,fila in enumerate(filas,2):
        try:
            if not isinstance(fila,dict):raise ValueError("La linea no es un objeto.")
            asiento=str(fila.get("asiento") or fila.get("referencia") or "").strip()[:80]
            cuenta=str(fila.get("cuenta") or fila.get("cuenta_codigo") or "").strip()[:40]
            concepto=str(fila.get("concepto") or fila.get("detalle") or "").strip()[:220]
            if not asiento or not cuenta or not concepto:raise ValueError("Asiento, cuenta y concepto son obligatorios.")
            debe=_centavos(fila.get("debe"));haber=_centavos(fila.get("haber"))
            if (debe>0)==(haber>0):raise ValueError("Cada linea debe tener importe solo en Debe o solo en Haber.")
            normalizada={"fila":numero,"asiento":asiento,"fecha":_fecha(fila.get("fecha")),"cuenta":cuenta,
                "concepto":concepto,"debe_centavos":debe,"haber_centavos":haber}
            base_duplicado={clave:valor for clave,valor in normalizada.items() if clave!="fila"}
            huella=hashlib.sha256(json.dumps(base_duplicado,sort_keys=True).encode()).hexdigest()
            normalizada["duplicada"]=huella in huellas;huellas.add(huella);lineas.append(normalizada)
        except (ValueError,TypeError) as error:errores.append({"fila":numero,"error":str(error)})
    return lineas,errores


def validar_borrador(*,organizacion_id,unidad_negocio_id,contenido,nombre_archivo):
    lineas,errores=leer_borrador(contenido,nombre_archivo);grupos=defaultdict(list)
    for linea in lineas:grupos[linea["asiento"]].append(linea)
    asientos=[]
    for referencia,items in sorted(grupos.items()):
        debe=sum(x["debe_centavos"] for x in items);haber=sum(x["haber_centavos"] for x in items)
        fechas=sorted({x["fecha"] for x in items});duplicadas=sum(x["duplicada"] for x in items)
        hallazgos=[]
        if debe!=haber:hallazgos.append("desbalanceado")
        if len(items)<2:hallazgos.append("partida_incompleta")
        if len(fechas)!=1:hallazgos.append("fechas_inconsistentes")
        if duplicadas:hallazgos.append("lineas_duplicadas")
        asientos.append({"referencia":referencia,"fecha":fechas[0] if len(fechas)==1 else None,"lineas":len(items),
            "debe_centavos":debe,"haber_centavos":haber,"diferencia_centavos":debe-haber,"hallazgos":hallazgos,"apto_como_borrador":not hallazgos})
    resultado={"organizacion_id":int(organizacion_id),"unidad_negocio_id":int(unidad_negocio_id),
        "modo":"precontabilidad_offline_no_contabilizable","archivo":str(nombre_archivo or ""),"lineas_validas":len(lineas),
        "errores":errores,"asientos":asientos,"resumen":{"asientos":len(asientos),"aptos":sum(x["apto_como_borrador"] for x in asientos),
        "observados":sum(not x["apto_como_borrador"] for x in asientos),"debe_centavos":sum(x["debe_centavos"] for x in asientos),"haber_centavos":sum(x["haber_centavos"] for x in asientos)},
        "controles":{"persistencia":False,"asientos_contabilizados":0,"libros_modificados":0,"saldos_modificados":0,"conexiones_externas":0}}
    resultado["huella_precontable"]=hashlib.sha256(json.dumps(resultado,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
    return resultado


def exportar_validacion(resultado):return io.BytesIO(json.dumps(resultado,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8"))
