"""Consulta IPC oficial, propone ajustes y los aplica solo tras aprobación."""

import json
import os
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from services.fechas import ahora_utc_naive
from services.fuentes_costo_productivo import registrar_importe_costo_fijo


SERIE_IPC_NACIONAL = os.getenv("IPC_SERIE_ID", "148.3_INIVELNAL_DICI_M_26")
API_SERIES_URL = os.getenv("IPC_API_URL", "https://apis.datos.gob.ar/series/api/series/")


def primer_dia_mes(valor):
    return date(valor.year, valor.month, 1)


def desplazar_meses(valor, cantidad):
    indice = valor.year * 12 + valor.month - 1 + cantidad
    return date(indice // 12, indice % 12 + 1, 1)


def _fecha_mes(valor):
    texto = str(valor or "").strip()
    if len(texto) == 7:
        texto += "-01"
    return date.fromisoformat(texto)


def ventana_para_ajuste(vigente_desde, *, periodo_inicio=None, periodo_final=None, frecuencia_meses=6):
    """Devuelve la ventana explícita o la infiere hasta el mes previo a la vigencia."""
    if periodo_inicio and periodo_final:
        inicio = primer_dia_mes(periodo_inicio)
        final = primer_dia_mes(periodo_final)
        if inicio > final:
            raise ValueError("El inicio del período IPC no puede superar el final.")
        return {"inicio": inicio, "final": final, "base": desplazar_meses(inicio, -1)}
    ajuste = primer_dia_mes(vigente_desde)
    final = desplazar_meses(ajuste, -1)
    inicio = desplazar_meses(final, -(int(frecuencia_meses) - 1))
    return {
        "inicio": inicio,
        "final": final,
        "base": desplazar_meses(inicio, -1),
    }


def calcular_ajuste(importe_centavos, indice_base, indice_final):
    base = Decimal(str(indice_base))
    final = Decimal(str(indice_final))
    if base <= 0 or final <= 0:
        raise ValueError("Los índices IPC deben ser positivos.")
    factor = final / base
    propuesto = (Decimal(importe_centavos) * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    variacion = ((factor - Decimal("1")) * Decimal("100")).quantize(Decimal("0.000001"))
    return int(propuesto), variacion


def _leer_api(urlopen_fn, desde, hasta, serie):
    parametros = urlencode({
        "ids": serie, "format": "json",
        "start_date": desde.isoformat(), "end_date": hasta.isoformat(),
    })
    request = Request(f"{API_SERIES_URL}?{parametros}", headers={"User-Agent": "FierroSystem/1.0"})
    with urlopen_fn(request, timeout=20) as respuesta:
        return json.loads(respuesta.read().decode("utf-8")), request.full_url


def actualizar_indices_oficiales(*, desde, hasta, IndiceIPCOficial, db_session, urlopen_fn=urlopen, serie=SERIE_IPC_NACIONAL):
    contenido, fuente_url = _leer_api(urlopen_fn, desde, hasta, serie)
    filas = contenido.get("data") or []
    guardados = 0
    for fila in filas:
        if not isinstance(fila, (list, tuple)) or len(fila) < 2 or fila[1] is None:
            continue
        periodo = primer_dia_mes(date.fromisoformat(str(fila[0])[:10]))
        registro = IndiceIPCOficial.query.filter_by(serie=serie, periodo=periodo).first()
        if registro is None:
            registro = IndiceIPCOficial(serie=serie, periodo=periodo)
            db_session.add(registro)
        registro.valor = Decimal(str(fila[1]))
        registro.fuente_url = fuente_url
        registro.fecha_consulta = ahora_utc_naive()
        guardados += 1
    db_session.commit()
    return guardados


def configurar_regla(costo, *, proximo_ajuste, organizacion_id, usuario_id, observacion,
                     ReglaAjusteIPCProductivo, db_session, serie=SERIE_IPC_NACIONAL,
                     tipo_ajuste="ipc", frecuencia_meses=6, periodo_ipc_inicio=None,
                     periodo_ipc_final=None, modalidad_pago="adelantado",
                     requiere_aprobacion=True, ReglaAjusteCostoHistorial=None):
    fecha = date.fromisoformat(str(proximo_ajuste))
    if fecha.day != 1:
        raise ValueError("La vigencia del ajuste debe comenzar el primer día del mes.")
    regla = ReglaAjusteIPCProductivo.query.filter_by(costo_fijo_id=costo.id).first()
    if regla is None:
        regla = ReglaAjusteIPCProductivo(costo_fijo_id=costo.id, organizacion_id=organizacion_id)
        db_session.add(regla)
    frecuencia = int(frecuencia_meses)
    if frecuencia < 1 or frecuencia > 120:
        raise ValueError("La frecuencia debe estar entre 1 y 120 meses.")
    inicio = _fecha_mes(periodo_ipc_inicio) if periodo_ipc_inicio else None
    final = _fecha_mes(periodo_ipc_final) if periodo_ipc_final else None
    if tipo_ajuste == "ipc":
        if not inicio or not final:
            raise ValueError("Indicá el período inicial y final del IPC.")
        ventana_para_ajuste(fecha, periodo_inicio=inicio, periodo_final=final, frecuencia_meses=frecuencia)
    regla.serie = serie
    regla.tipo_ajuste = tipo_ajuste
    regla.frecuencia_meses = frecuencia
    regla.periodo_ipc_inicio = inicio
    regla.periodo_ipc_final = final
    regla.modalidad_pago = modalidad_pago
    regla.requiere_aprobacion = bool(requiere_aprobacion)
    regla.proximo_ajuste = fecha
    regla.activa = True
    regla.observacion = str(observacion or "").strip() or None
    regla.creado_por_usuario_id = usuario_id
    if ReglaAjusteCostoHistorial is not None:
        db_session.flush()
        ultima = ReglaAjusteCostoHistorial.query.filter_by(regla_id=regla.id).order_by(
            ReglaAjusteCostoHistorial.numero_revision.desc()
        ).first()
        db_session.add(ReglaAjusteCostoHistorial(
            regla=regla, numero_revision=(ultima.numero_revision if ultima else 0) + 1,
            tipo_ajuste=tipo_ajuste, serie=serie, frecuencia_meses=frecuencia,
            periodo_ipc_inicio=inicio, periodo_ipc_final=final, proximo_ajuste=fecha,
            modalidad_pago=modalidad_pago, requiere_aprobacion=bool(requiere_aprobacion),
            observacion=regla.observacion, creado_por_usuario_id=usuario_id,
        ))
    db_session.commit()
    return regla


def generar_propuestas(*, ReglaAjusteIPCProductivo, PropuestaAjusteIPCProductivo,
                       IndiceIPCOficial, CostoFijoVersion, db_session, hoy=None):
    hoy = hoy or date.today()
    creadas = []
    reglas = ReglaAjusteIPCProductivo.query.filter_by(activa=True).all()
    for regla in reglas:
        ventana = ventana_para_ajuste(
            regla.proximo_ajuste, periodo_inicio=regla.periodo_ipc_inicio,
            periodo_final=regla.periodo_ipc_final, frecuencia_meses=regla.frecuencia_meses,
        )
        base = IndiceIPCOficial.query.filter_by(serie=regla.serie, periodo=ventana["base"]).first()
        final = IndiceIPCOficial.query.filter_by(serie=regla.serie, periodo=ventana["final"]).first()
        if base is None or final is None:
            continue
        existente = PropuestaAjusteIPCProductivo.query.filter_by(
            regla_id=regla.id, vigente_desde=regla.proximo_ajuste,
        ).first()
        if existente is not None:
            continue
        version = CostoFijoVersion.query.filter_by(costo_fijo_id=regla.costo_fijo_id, vigente=True).first()
        if version is None:
            continue
        propuesto, variacion = calcular_ajuste(
            version.importe_mensual_centavos, base.valor, final.valor,
        )
        propuesta = PropuestaAjusteIPCProductivo(
            regla_id=regla.id, version_origen_id=version.id,
            periodo_base=ventana["base"], periodo_final=ventana["final"],
            indice_base=base.valor, indice_final=final.valor,
            variacion_porcentual=variacion,
            importe_actual_centavos=version.importe_mensual_centavos,
            importe_propuesto_centavos=propuesto,
            vigente_desde=regla.proximo_ajuste,
            estado="pendiente" if regla.requiere_aprobacion else "aprobada",
        )
        db_session.add(propuesta)
        creadas.append(propuesta)
    db_session.commit()
    return creadas


def aplicar_propuesta(propuesta, *, CostoFijoVersion, db_session, usuario_id=None, hoy=None):
    hoy = hoy or date.today()
    if propuesta.estado != "aprobada" or propuesta.vigente_desde > hoy:
        return False
    costo = propuesta.regla.costo_fijo
    registrar_importe_costo_fijo(
        costo, moneda="ARS",
        importe_periodo_centavos=propuesta.importe_propuesto_centavos,
        naturaleza="fijo", periodicidad="mensual", meses_cobertura=1,
        vigente_desde=datetime.combine(propuesta.vigente_desde, datetime.min.time()),
        observacion=(
            f"Ajuste IPC oficial {propuesta.periodo_base:%m/%Y}–"
            f"{propuesta.periodo_final:%m/%Y}: {propuesta.variacion_porcentual}%"
        ),
        creado_por_usuario_id=usuario_id or propuesta.aprobado_por_usuario_id,
        CostoFijoVersion=CostoFijoVersion, db_session=db_session,
    )
    propuesta.estado = "aplicada"
    propuesta.fecha_aplicacion = ahora_utc_naive()
    frecuencia = propuesta.regla.frecuencia_meses
    propuesta.regla.proximo_ajuste = desplazar_meses(propuesta.vigente_desde, frecuencia)
    if propuesta.regla.periodo_ipc_inicio:
        propuesta.regla.periodo_ipc_inicio = desplazar_meses(propuesta.regla.periodo_ipc_inicio, frecuencia)
    if propuesta.regla.periodo_ipc_final:
        propuesta.regla.periodo_ipc_final = desplazar_meses(propuesta.regla.periodo_ipc_final, frecuencia)
    db_session.commit()
    return True


def aprobar_propuesta(propuesta, *, usuario_id, CostoFijoVersion, db_session, hoy=None):
    if propuesta.estado != "pendiente":
        raise ValueError("La propuesta ya fue procesada.")
    propuesta.estado = "aprobada"
    propuesta.aprobado_por_usuario_id = usuario_id
    propuesta.fecha_aprobacion = ahora_utc_naive()
    db_session.commit()
    aplicar_propuesta(
        propuesta, CostoFijoVersion=CostoFijoVersion,
        db_session=db_session, usuario_id=usuario_id, hoy=hoy,
    )
    return propuesta


def ejecutar_ciclo_ipc(*, modelos, db_session, urlopen_fn=urlopen, hoy=None):
    hoy = hoy or date.today()
    reglas = modelos["ReglaAjusteIPCProductivo"].query.filter_by(activa=True).all()
    if reglas:
        ventanas = [ventana_para_ajuste(
            r.proximo_ajuste, periodo_inicio=r.periodo_ipc_inicio,
            periodo_final=r.periodo_ipc_final, frecuencia_meses=r.frecuencia_meses,
        ) for r in reglas]
        bases = [v["base"] for v in ventanas]
        finales = [v["final"] for v in ventanas]
        actualizar_indices_oficiales(
            desde=min(bases), hasta=max(finales),
            IndiceIPCOficial=modelos["IndiceIPCOficial"],
            db_session=db_session, urlopen_fn=urlopen_fn,
        )
    generar_propuestas(
        ReglaAjusteIPCProductivo=modelos["ReglaAjusteIPCProductivo"],
        PropuestaAjusteIPCProductivo=modelos["PropuestaAjusteIPCProductivo"],
        IndiceIPCOficial=modelos["IndiceIPCOficial"],
        CostoFijoVersion=modelos["CostoFijoVersion"], db_session=db_session,
        hoy=hoy,
    )
    aprobadas = modelos["PropuestaAjusteIPCProductivo"].query.filter_by(estado="aprobada").all()
    return sum(
        aplicar_propuesta(p, CostoFijoVersion=modelos["CostoFijoVersion"], db_session=db_session, hoy=hoy)
        for p in aprobadas
    )
