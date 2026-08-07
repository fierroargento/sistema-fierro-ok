"""Mapeo y validacion masiva de componentes de combos."""

from decimal import Decimal, InvalidOperation

from services.importacion_productos_costeo import normalizar
from services.perfiles_costeo import crear_o_actualizar_componente_combo


CAMPOS_COMBOS = {
    "sku_combo": {"nombre": "SKU combo", "obligatorio": True, "alias": {"sku combo", "combo", "codigo combo"}},
    "sku_componente": {"nombre": "SKU componente", "obligatorio": True, "alias": {"sku componente", "componente", "codigo componente"}},
    "cantidad": {"nombre": "Cantidad", "obligatorio": True, "alias": {"cantidad", "unidades"}},
    "unidad": {"nombre": "Unidad de negocio", "obligatorio": False, "alias": {"unidad", "unidad negocio", "marca"}},
    "observacion": {"nombre": "Observacion", "obligatorio": False, "alias": {"observacion", "notas"}},
}


def sugerir_mapeo_combo(encabezados):
    resultado, usados = {}, set()
    for indice, encabezado in enumerate(encabezados):
        limpio = normalizar(str(encabezado or "").replace("_", " ").replace("-", " "))
        destino = ""
        for campo, definicion in CAMPOS_COMBOS.items():
            if campo not in usados and limpio in definicion["alias"]:
                destino, usados = campo, usados | {campo}
                break
        resultado[str(indice)] = destino
    return resultado


def validar_mapeo_combo(mapeo):
    destinos = [x for x in mapeo.values() if x]
    if len(destinos) != len(set(destinos)):
        raise ValueError("Un campo no puede recibir dos columnas.")
    faltantes = [d["nombre"] for c, d in CAMPOS_COMBOS.items() if d["obligatorio"] and c not in destinos]
    if faltantes:
        raise ValueError("Faltan campos obligatorios: " + ", ".join(faltantes) + ".")


def _datos(fila, mapeo):
    salida = {}
    for indice, campo in mapeo.items():
        if campo:
            pos = int(indice)
            salida[campo] = fila["valores"][pos] if pos < len(fila["valores"]) else ""
    return salida


def _cantidad(valor):
    try:
        numero = Decimal(str(valor).replace(",", ".").strip())
    except (InvalidOperation, ValueError) as error:
        raise ValueError("Cantidad invalida") from error
    if not numero.is_finite() or numero <= 0:
        raise ValueError("Cantidad invalida")
    return str(numero)


def previsualizar_combos(
    filas, mapeo, *, organizacion_id, modelos, modo="crear_actualizar",
    unidad_negocio_id=None,
):
    validar_mapeo_combo(mapeo)
    perfiles = modelos["PerfilCosteoProducto"].query.filter_by(organizacion_id=organizacion_id).all()
    if unidad_negocio_id is not None:
        perfiles = [p for p in perfiles if p.unidad_negocio_id == unidad_negocio_id]
    resultado = []
    for fila in filas:
        datos, errores = _datos(fila, mapeo), []
        sku_combo = str(datos.get("sku_combo") or "").strip().upper()
        sku_componente = str(datos.get("sku_componente") or "").strip().upper()
        unidad = normalizar(datos.get("unidad"))
        candidatos_combo = [p for p in perfiles if (p.producto.sku or "").upper() == sku_combo and p.tipo == "combo"]
        candidatos_componente = [p for p in perfiles if (p.producto.sku or "").upper() == sku_componente and p.tipo in {"simple", "produccion"}]
        if unidad:
            candidatos_combo = [p for p in candidatos_combo if p.unidad_negocio and normalizar(p.unidad_negocio.nombre) == unidad]
            candidatos_componente = [p for p in candidatos_componente if p.unidad_negocio and normalizar(p.unidad_negocio.nombre) == unidad]
        if len(candidatos_combo) != 1:
            errores.append("No se encontro un unico perfil Combo")
        if len(candidatos_componente) != 1:
            errores.append("No se encontro un unico componente Simple o Produccion")
        try:
            cantidad = _cantidad(datos.get("cantidad"))
        except ValueError as error:
            cantidad, errores = "", errores + [str(error)]
        combo = candidatos_combo[0] if len(candidatos_combo) == 1 else None
        componente = candidatos_componente[0] if len(candidatos_componente) == 1 else None
        if combo and componente and combo.unidad_negocio_id != componente.unidad_negocio_id:
            errores.append("El combo y el componente pertenecen a unidades diferentes")
        existente = None
        if combo and componente:
            existente = modelos["ComboProductoComponente"].query.filter_by(
                combo_perfil_id=combo.id, componente_perfil_id=componente.id,
            ).first()
        accion = "rechazado" if errores else "actualizar" if existente else "crear"
        if existente and str(existente.cantidad.normalize()) == str(Decimal(cantidad).normalize()) and (existente.observacion or "") == str(datos.get("observacion") or "").strip():
            accion = "sin_cambios"
        if not errores and modo == "solo_crear" and accion == "actualizar":
            accion, errores = "rechazado", ["El componente ya existe en el combo"]
        if not errores and modo == "solo_actualizar" and accion == "crear":
            accion, errores = "rechazado", ["El componente todavía no existe en el combo"]
        resultado.append({
            "numero": fila["numero"], "sku_combo": sku_combo,
            "sku_componente": sku_componente, "cantidad": cantidad,
            "unidad": datos.get("unidad", ""), "observacion": datos.get("observacion", ""),
            "combo_id": combo.id if combo else None,
            "componente_id": componente.id if componente else None,
            "accion": accion, "errores": errores,
        })
    return resultado


def aplicar_combos(vista, *, modelos, db_session):
    conteos = {"creados": 0, "actualizados": 0, "sin_cambios": 0, "rechazados": 0}
    for fila in vista:
        if fila["accion"] in {"rechazado", "sin_cambios"}:
            conteos["rechazados" if fila["accion"] == "rechazado" else "sin_cambios"] += 1
            continue
        crear_o_actualizar_componente_combo(
            db_session.get(modelos["PerfilCosteoProducto"], fila["combo_id"]),
            db_session.get(modelos["PerfilCosteoProducto"], fila["componente_id"]),
            cantidad=fila["cantidad"], observacion=fila["observacion"],
            ComboProductoComponente=modelos["ComboProductoComponente"],
            db_session=db_session, commit=False,
        )
        conteos["creados" if fila["accion"] == "crear" else "actualizados"] += 1
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return conteos
