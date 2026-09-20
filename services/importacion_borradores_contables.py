"""Importacion transaccional de asientos multilínea, siempre como borrador."""

import hashlib
from collections import defaultdict
from datetime import date
from services.precontabilidad_offline import leer_borrador


def importar_borradores(*,organizacion_id,unidad_negocio_id,contenido,nombre_archivo,cuentas,
    Asiento,Linea,db_session,usuario_id=None):
    lineas,errores=leer_borrador(contenido,nombre_archivo)
    if errores:raise ValueError(f"El archivo contiene {len(errores)} lineas invalidas.")
    mapa={str(c.codigo):c for c in cuentas if int(c.organizacion_id)==int(organizacion_id) and int(c.unidad_negocio_id)==int(unidad_negocio_id)}
    grupos=defaultdict(list)
    for linea in lineas:grupos[linea["asiento"]].append(linea)
    if not grupos:raise ValueError("El archivo no contiene asientos.")
    preparados=[]
    for referencia,items in sorted(grupos.items()):
        debe=sum(x["debe_centavos"] for x in items);haber=sum(x["haber_centavos"] for x in items)
        fechas={x["fecha"] for x in items}
        if len(items)<2 or debe!=haber or debe<=0:raise ValueError(f"El asiento {referencia} no esta balanceado.")
        if len(fechas)!=1 or any(x["duplicada"] for x in items):raise ValueError(f"El asiento {referencia} tiene fechas o lineas inconsistentes.")
        faltantes=sorted({x["cuenta"] for x in items if x["cuenta"] not in mapa})
        if faltantes:raise ValueError(f"El asiento {referencia} usa cuentas inexistentes: {', '.join(faltantes)}.")
        if any(not mapa[x["cuenta"]].imputable for x in items):raise ValueError(f"El asiento {referencia} usa cuentas no imputables.")
        preparados.append((referencia,items,debe))
    creados=[]
    try:
        for referencia,items,total in preparados:
            primera_debe=next(x for x in items if x["debe_centavos"]>0);primera_haber=next(x for x in items if x["haber_centavos"]>0)
            base=f"{organizacion_id}:{unidad_negocio_id}:{referencia}:{items[0]['fecha']}:{total}:"+"|".join(f"{x['cuenta']}:{x['debe_centavos']}:{x['haber_centavos']}" for x in items)
            asiento=Asiento(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,fecha=date.fromisoformat(items[0]["fecha"]),
                concepto=items[0]["concepto"],cuenta_debe_id=mapa[primera_debe["cuenta"]].id,cuenta_haber_id=mapa[primera_haber["cuenta"]].id,
                total_debe_centavos=total,total_haber_centavos=total,referencia=referencia,clave_idempotencia=hashlib.sha256(base.encode()).hexdigest(),
                estado="borrador",contabilizado=False,afecta_saldos=False,creado_por_usuario_id=usuario_id)
            db_session.add(asiento);db_session.flush()
            for renglon,item in enumerate(items,1):
                db_session.add(Linea(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,asiento_borrador_id=asiento.id,
                    renglon=renglon,cuenta_contable_id=mapa[item["cuenta"]].id,concepto=item["concepto"],debe_centavos=item["debe_centavos"],
                    haber_centavos=item["haber_centavos"],afecta_saldos=False))
            creados.append(asiento)
        db_session.commit();return creados
    except Exception:
        db_session.rollback();raise
