"""Presupuesto de caja comparado en memoria con proyecciones internas."""

import csv
import hashlib
import io
import json
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

LIMITE_PARTIDAS = 500


def _centavos(valor):
    texto = str(valor or "").strip().replace("$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".") if texto.rfind(",") > texto.rfind(".") else texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        importe = int((Decimal(texto) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except InvalidOperation as error:
        raise ValueError("Importe presupuestado invalido.") from error
    if importe < 0:
        raise ValueError("El presupuesto no admite importes negativos.")
    return importe


def leer_presupuesto(contenido, nombre_archivo):
    if not contenido or len(contenido) > 1_000_000:
        raise ValueError("El presupuesto esta vacio o supera 1 MB.")
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("El presupuesto debe estar codificado en UTF-8.") from error
    nombre = str(nombre_archivo or "").lower()
    if nombre.endswith(".json"):
        bruto = json.loads(texto)
        filas = bruto.get("partidas", bruto) if isinstance(bruto, dict) else bruto
    elif nombre.endswith(".csv"):
        delimitador = ";" if texto[:4096].count(";") > texto[:4096].count(",") else ","
        filas = list(csv.DictReader(io.StringIO(texto), delimiter=delimitador))
    else:
        raise ValueError("Solo se admite presupuesto CSV o JSON.")
    if not isinstance(filas, list) or len(filas) > LIMITE_PARTIDAS:
        raise ValueError(f"El presupuesto debe contener hasta {LIMITE_PARTIDAS} partidas.")
    partidas=[];errores=[];claves=set()
    for numero,fila in enumerate(filas,2):
        try:
            if not isinstance(fila,dict):raise ValueError("La partida no es un objeto.")
            mes=str(fila.get("mes") or fila.get("periodo") or "").strip()
            if len(mes)!=7 or mes[4]!="-" or not (1<=int(mes[5:])<=12):raise ValueError("El mes debe tener formato AAAA-MM.")
            tipo=str(fila.get("tipo") or "").strip().lower()
            if tipo not in ("ingreso","egreso"):raise ValueError("El tipo debe ser ingreso o egreso.")
            categoria=str(fila.get("categoria") or fila.get("concepto") or "general").strip().lower()[:80]
            clave=(mes,tipo,categoria)
            if clave in claves:raise ValueError("La partida esta duplicada.")
            claves.add(clave)
            partidas.append({"mes":mes,"tipo":tipo,"categoria":categoria,"importe_centavos":_centavos(fila.get("importe") or fila.get("monto"))})
        except (ValueError,TypeError) as error:
            errores.append({"fila":numero,"error":str(error)})
    return partidas,errores


def comparar_presupuesto(*,organizacion_id,unidad_negocio_id,contenido,nombre_archivo,proyecciones):
    partidas,errores=leer_presupuesto(contenido,nombre_archivo)
    presupuestado=defaultdict(lambda:{"ingreso":0,"egreso":0})
    for p in partidas:presupuestado[p["mes"]][p["tipo"]]+=p["importe_centavos"]
    proyectado=defaultdict(lambda:{"ingreso":0,"egreso":0})
    excluidas=0
    for p in proyecciones:
        if int(p.organizacion_id)!=int(organizacion_id) or int(p.unidad_negocio_id)!=int(unidad_negocio_id):
            excluidas+=1;continue
        if p.estado!="proyectado" or p.confirmado or p.afecta_saldo:
            continue
        proyectado[p.fecha_prevista.strftime("%Y-%m")][p.tipo]+=int(p.importe_centavos)
    meses=[];acumulado=0;primer_deficit=None
    for mes in sorted(set(presupuestado)|set(proyectado)):
        pre=presupuestado[mes];pro=proyectado[mes]
        saldo_pre=pre["ingreso"]-pre["egreso"];saldo_pro=pro["ingreso"]-pro["egreso"]
        acumulado+=saldo_pro
        if acumulado<0 and primer_deficit is None:primer_deficit=mes
        meses.append({"mes":mes,"presupuestado_ingresos_centavos":pre["ingreso"],"presupuestado_egresos_centavos":pre["egreso"],
            "proyectado_ingresos_centavos":pro["ingreso"],"proyectado_egresos_centavos":pro["egreso"],
            "desvio_neto_centavos":saldo_pro-saldo_pre,"saldo_proyectado_acumulado_centavos":acumulado})
    resultado={"organizacion_id":int(organizacion_id),"unidad_negocio_id":int(unidad_negocio_id),"modo":"presupuesto_offline_no_ejecutable",
        "archivo":str(nombre_archivo or ""),"partidas_validas":len(partidas),"errores":errores,"proyecciones_ajenas_excluidas":excluidas,
        "primer_mes_deficit":primer_deficit,"meses":meses,
        "controles":{"persistencia":False,"saldos_modificados":0,"pagos":0,"cobros":0,"asientos":0,"conexiones_externas":0}}
    resultado["huella_presupuesto"]=hashlib.sha256(json.dumps(resultado,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
    return resultado


def exportar_presupuesto(resultado):
    return io.BytesIO(json.dumps(resultado,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8"))
