"""Diagnostica preparacion integral del canal sin consultar ni ejecutar APIs."""

from datetime import timedelta

from services.fechas import ahora_utc_naive


TIPOS = ("precio", "cargo", "envio")


def crear_regla_validacion(lista, *, nombre, vigencias, exigencias, usuario,
                           ReglaValidacionCanalVersion, db_session):
    anteriores = ReglaValidacionCanalVersion.query.filter_by(lista_precio_id=lista.id).all()
    valores = {}
    for tipo in ("precio", "cargos", "envio", "promocion"):
        try: horas = int(vigencias.get(tipo, 168))
        except (TypeError, ValueError) as error: raise ValueError(f"La vigencia de {tipo} no es valida.") from error
        if horas <= 0: raise ValueError(f"La vigencia de {tipo} debe ser positiva.")
        valores[f"vigencia_{tipo}_horas"] = horas
    regla = ReglaValidacionCanalVersion(
        lista_precio_id=lista.id,
        numero_version=max((item.numero_version for item in anteriores), default=0) + 1,
        nombre=str(nombre or "").strip(),
        exigir_precio_observado=bool(exigencias.get("precio")),
        exigir_cargos_observados=bool(exigencias.get("cargos")),
        exigir_envio_observado=bool(exigencias.get("envio")),
        exigir_promocion_observada=bool(exigencias.get("promocion")),
        exigir_identidad_unica=bool(exigencias.get("identidad")),
        creado_por_usuario_id=getattr(usuario, "id", None),
        creado_por_username=getattr(usuario, "username", None), **valores,
    )
    if not regla.nombre: raise ValueError("La regla requiere un nombre.")
    db_session.add(regla); db_session.commit(); return regla


def activar_regla_validacion(regla, *, ReglaValidacionCanalVersion, db_session):
    if regla is None or regla.estado != "preparatorio": raise ValueError("La regla no esta preparatoria.")
    momento = ahora_utc_naive()
    for anterior in ReglaValidacionCanalVersion.query.filter_by(lista_precio_id=regla.lista_precio_id, vigente=True).all():
        anterior.vigente = False; anterior.estado = "archivado"; anterior.vigente_hasta = momento
    regla.vigente = True; regla.estado = "vigente"; regla.vigente_desde = momento
    db_session.commit(); return regla


def _ultima(observaciones, lista_id, inclusion_id, tipo):
    candidatas = [item for item in observaciones if item.lista_precio_id == lista_id and item.catalogo_producto_id == inclusion_id and item.tipo == tipo]
    return max(candidatas, key=lambda item: item.fecha_observacion) if candidatas else None


def _promocion(promociones, lista_id, inclusion_id):
    candidatas = [item for item in promociones if item.lista_precio_id == lista_id and item.catalogo_producto_id == inclusion_id]
    return max(candidatas, key=lambda item: item.fecha_observacion) if candidatas else None


def evaluar_fila(fila, regla, observaciones, promociones, *, ahora=None):
    ahora = ahora or ahora_utc_naive(); bloqueos = []; advertencias = []
    inclusion = fila.get("inclusion")
    if inclusion is None: return {"estado_preparacion": "bloqueada", "bloqueos": ["producto_sin_inclusion_catalogo"], "advertencias": [], "identidades": []}
    if regla is None: return {"estado_preparacion": "bloqueada", "bloqueos": ["sin_regla_validacion_vigente"], "advertencias": [], "identidades": []}
    lista_id = fila["regla_canal"].lista_precio_id; inclusion_id = inclusion.id
    encontrados = {tipo: _ultima(observaciones, lista_id, inclusion_id, tipo) for tipo in TIPOS}
    promo = _promocion(promociones, lista_id, inclusion_id)
    contratos = (
        ("precio", regla.exigir_precio_observado, regla.vigencia_precio_horas),
        ("cargo", regla.exigir_cargos_observados, regla.vigencia_cargos_horas),
        ("envio", regla.exigir_envio_observado, regla.vigencia_envio_horas),
    )
    for tipo, obligatorio, horas in contratos:
        item = encontrados[tipo]
        if item is None:
            (bloqueos if obligatorio else advertencias).append(f"{tipo}_no_observado")
        elif item.fecha_observacion < ahora - timedelta(hours=int(horas)):
            (bloqueos if obligatorio else advertencias).append(f"{tipo}_vencido")
    if promo is None:
        (bloqueos if regla.exigir_promocion_observada else advertencias).append("promocion_no_observada")
    elif promo.fecha_observacion < ahora - timedelta(hours=int(regla.vigencia_promocion_horas)):
        (bloqueos if regla.exigir_promocion_observada else advertencias).append("promocion_vencida")
    identidades = {
        (item.cuenta_codigo, item.referencia_publicacion)
        for item in encontrados.values() if item is not None
    }
    if promo is not None and promo.cuenta_codigo and promo.referencia_externa:
        identidades.add((promo.cuenta_codigo, promo.referencia_externa))
    if regla.exigir_identidad_unica and len(identidades) > 1: bloqueos.append("cuenta_o_publicacion_inconsistente")
    if fila.get("desvios_observados"): bloqueos.extend(fila["desvios_observados"])
    return {"estado_preparacion": "bloqueada" if bloqueos else "advertencia" if advertencias else "lista", "bloqueos": bloqueos, "advertencias": advertencias, "identidades": sorted(identidades)}


def construir_tablero(filas, reglas, observaciones, promociones, propuestas, *, ahora=None):
    reglas_vigentes = {regla.lista_precio_id: regla for regla in reglas if regla.vigente}
    diagnosticos = []
    por_clave = {(fila["regla_canal"].lista_precio_id, fila["inclusion"].id if fila.get("inclusion") else None): fila for fila in filas}
    for fila in filas:
        regla = reglas_vigentes.get(fila["regla_canal"].lista_precio_id)
        diagnosticos.append({"fila": fila, "regla_validacion": regla, **evaluar_fila(fila, regla, observaciones, promociones, ahora=ahora)})
    propuestas_obsoletas = []
    from services.cola_acciones_comerciales import propuesta_esta_vigente
    for propuesta in propuestas:
        fila = por_clave.get((propuesta.lista_precio_id, propuesta.catalogo_producto_id))
        if propuesta.estado in {"preparada", "aprobada"} and not propuesta_esta_vigente(propuesta, fila): propuestas_obsoletas.append(propuesta.id)
    resumen = {"lista": 0, "advertencia": 0, "bloqueada": 0, "propuestas_obsoletas": len(propuestas_obsoletas)}
    for item in diagnosticos: resumen[item["estado_preparacion"]] += 1
    return diagnosticos, resumen, propuestas_obsoletas
