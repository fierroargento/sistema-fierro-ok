"""Certificacion de conciliacion Mercado Pago con datos locales y sin transporte."""

import io
import json

from services.conciliacion_liquidaciones_canal import construir_conciliaciones, incorporar_gestiones


def certificar_conciliacion_mp(ventas, movimientos, gestiones, *, organizacion_id, unidad_negocio_id):
    ventas=list(ventas or []); movimientos=list(movimientos or []); gestiones=list(gestiones or [])
    bloqueos=[]; advertencias=[]
    for nombre, registros in (("venta",ventas),("movimiento",movimientos),("gestion",gestiones)):
        ids=[getattr(x,"id",None) for x in registros if getattr(x,"id",None) is not None]
        if len(ids)!=len(set(ids)): bloqueos.append(f"Hay {nombre}s repetidos en el conjunto evaluado.")
        for registro in registros:
            if registro.organizacion_id!=organizacion_id or registro.unidad_negocio_id!=unidad_negocio_id:
                bloqueos.append(f"El {nombre} #{getattr(registro,'id','?')} pertenece a otro tenant.")
    claves_venta={(v.cuenta_codigo,v.referencia_venta) for v in ventas}
    for movimiento in movimientos:
        clave=(movimiento.cuenta_codigo,movimiento.referencia_venta)
        if clave not in claves_venta: advertencias.append(f"Movimiento {movimiento.referencia_movimiento} sin venta local asociada.")
    pagos_por_venta={}
    for venta in ventas:
        if venta.referencia_pago: pagos_por_venta.setdefault((venta.cuenta_codigo,venta.referencia_venta),set()).add(venta.referencia_pago)
    for movimiento in movimientos:
        esperados=pagos_por_venta.get((movimiento.cuenta_codigo,movimiento.referencia_venta),set())
        if esperados and movimiento.referencia_pago and movimiento.referencia_pago not in esperados:
            bloqueos.append(f"Movimiento {movimiento.referencia_movimiento} referencia un pago distinto al de la venta.")
    filas,resumen=construir_conciliaciones(ventas,movimientos)
    incorporar_gestiones(filas,gestiones)
    sin_gestion=sum(1 for f in filas if f["requiere_revision"] and f["estado_gestion"]=="abierta")
    bajo_piso=sum(1 for f in filas if f["estado_economico"]=="bajo_piso")
    if sin_gestion: advertencias.append(f"Hay {sin_gestion} conciliaciones que requieren gestion interna.")
    if bajo_piso: bloqueos.append(f"Hay {bajo_piso} ventas cuya liquidacion esperada queda debajo del piso economico.")
    controles={
        "tenant_aislado": not any("otro tenant" in x for x in bloqueos),
        "identidad_consistente": not any("repetidos" in x or "pago distinto" in x for x in bloqueos),
        "piso_economico_protegido": bajo_piso==0,
        "movimientos_asociados": not any("sin venta local" in x for x in advertencias),
        "transporte_bloqueado": True,
    }
    return {"aprobada":not bloqueos,"controles":controles,"resumen":{**resumen,"ventas_observadas":len(ventas),"movimientos_observados":len(movimientos),"gestiones":len(gestiones),"sin_gestion":sin_gestion,"bloqueos":len(bloqueos),"advertencias":len(advertencias)},"bloqueos":bloqueos,"advertencias":advertencias,"acciones_externas":0,"escrituras":0}


def exportar_certificacion_mp(resultado):
    return io.BytesIO(json.dumps(resultado,ensure_ascii=False,sort_keys=True,indent=2,default=str).encode("utf-8"))
