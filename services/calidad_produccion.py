"""Registro preparatorio de lotes y calidad sin liberacion de inventario."""

import hashlib
import io
import json
from decimal import Decimal, InvalidOperation


def _positivo(valor, nombre):
    try: numero = Decimal(str(valor).replace(",", "."))
    except (InvalidOperation, ValueError): raise ValueError(f"{nombre} no es válido.")
    if not numero.is_finite() or numero <= 0:
        raise ValueError(f"{nombre} debe ser mayor que cero.")
    return numero


def crear_lote(datos, *, orden, parte, organizacion_id, unidad_negocio_id, LoteProduccion,
               db_session, usuario_id=None):
    if int(orden.organizacion_id) != int(organizacion_id) or int(orden.unidad_negocio_id) != int(unidad_negocio_id):
        raise ValueError("La orden no pertenece al contexto activo.")
    if int(parte.organizacion_id) != int(organizacion_id) or int(parte.unidad_negocio_id) != int(unidad_negocio_id):
        raise ValueError("El parte no pertenece al contexto activo.")
    if int(parte.orden_produccion_id) != int(orden.id) or parte.estado == "anulado":
        raise ValueError("El parte no es válido para la orden.")
    cantidad = _positivo(datos.get("cantidad"), "La cantidad del lote")
    asignada = sum(Decimal(str(item.cantidad)) for item in getattr(parte, "lotes_preparatorios", ()))
    if asignada + cantidad > Decimal(str(parte.cantidad_buena)):
        raise ValueError("La cantidad acumulada de lotes supera la producción buena del parte.")
    codigo = str(datos.get("codigo") or "").strip()
    if not codigo: raise ValueError("El código del lote es obligatorio.")
    lote = LoteProduccion(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        orden_produccion_id=orden.id, parte_produccion_id=parte.id, codigo=codigo,
        cantidad=cantidad, estado="cuarentena", liberado_inventario=False,
        movimiento_creado=False, observacion=str(datos.get("observacion") or "").strip() or None,
        creado_por_usuario_id=usuario_id,
    )
    db_session.add(lote); db_session.commit()
    return lote


def registrar_control(datos, *, lote, organizacion_id, unidad_negocio_id, ControlCalidadProduccion,
                      db_session, usuario_id=None):
    if int(lote.organizacion_id) != int(organizacion_id) or int(lote.unidad_negocio_id) != int(unidad_negocio_id):
        raise ValueError("El lote no pertenece al contexto activo.")
    muestra = _positivo(datos.get("muestra"), "La muestra")
    try:
        aprobadas = Decimal(str(datos.get("aprobadas") or "0").replace(",", "."))
        rechazadas = Decimal(str(datos.get("rechazadas") or "0").replace(",", "."))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("Aprobadas y rechazadas no son válidas.") from error
    if (
        not aprobadas.is_finite() or not rechazadas.is_finite()
        or aprobadas < 0 or rechazadas < 0 or aprobadas + rechazadas != muestra
    ):
        raise ValueError("Aprobadas y rechazadas deben ser no negativas y sumar la muestra.")
    if muestra > Decimal(str(lote.cantidad)):
        raise ValueError("La muestra no puede superar la cantidad del lote.")
    numero = str(datos.get("numero") or "").strip()
    if not numero: raise ValueError("El número de control es obligatorio.")
    resultado = "aprobado_interno" if rechazadas == 0 else "rechazado_interno"
    control = ControlCalidadProduccion(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        lote_produccion_id=lote.id, numero=numero, muestra=muestra,
        aprobadas=aprobadas, rechazadas=rechazadas, resultado=resultado,
        libera_stock=False, observacion=str(datos.get("observacion") or "").strip() or None,
        creado_por_usuario_id=usuario_id,
    )
    lote.estado = resultado
    db_session.add(control); db_session.commit()
    return control


def evidencia_calidad(*, organizacion_id, unidad_negocio_id, lotes):
    registros=[]; hallazgos=[]
    for lote in sorted(lotes, key=lambda item: int(item.id)):
        if int(lote.organizacion_id) != int(organizacion_id) or int(lote.unidad_negocio_id) != int(unidad_negocio_id):
            hallazgos.append({"codigo":"lote_fuera_contexto","lote_id":lote.id}); continue
        if lote.liberado_inventario or lote.movimiento_creado:
            hallazgos.append({"codigo":"lote_con_impacto","lote_id":lote.id})
        registros.append({
            "lote_id":lote.id,"codigo":lote.codigo,"orden_id":lote.orden_produccion_id,
            "parte_id":lote.parte_produccion_id,"cantidad":format(Decimal(str(lote.cantidad)).normalize(),"f"),
            "estado":lote.estado,"controles":[{
                "numero":c.numero,"muestra":format(Decimal(str(c.muestra)).normalize(),"f"),
                "aprobadas":format(Decimal(str(c.aprobadas)).normalize(),"f"),
                "rechazadas":format(Decimal(str(c.rechazadas)).normalize(),"f"),"resultado":c.resultado,
            } for c in sorted(lote.controles_calidad,key=lambda x:int(x.id))],
        })
    resultado={"organizacion_id":organizacion_id,"unidad_negocio_id":unidad_negocio_id,
               "modo":"calidad_sin_liberacion","aprobado":not hallazgos,"lotes":registros,
               "hallazgos":hallazgos,"controles":{"persistencia_evidencia":False,"movimientos_stock":0,
               "liberaciones":0,"conexiones_externas":0}}
    resultado["huella_calidad"]=hashlib.sha256(json.dumps(resultado,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
    return resultado


def exportar_evidencia(resultado):
    return io.BytesIO(json.dumps(resultado,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8"))
