"""Importacion tenant del maestro existente de proveedores de compras."""

import re

from services.importacion_productos_costeo import normalizar


CAMPOS_PROVEEDORES = {
    "codigo": {"nombre": "Codigo", "obligatorio": True, "alias": {"codigo", "cod proveedor", "codigo proveedor"}},
    "razon_social": {"nombre": "Razon social", "obligatorio": True, "alias": {"razon social", "proveedor", "nombre"}},
    "cuit": {"nombre": "CUIT", "obligatorio": False, "alias": {"cuit", "cuil"}},
    "email": {"nombre": "Email", "obligatorio": False, "alias": {"email", "correo"}},
    "telefono": {"nombre": "Telefono", "obligatorio": False, "alias": {"telefono", "tel"}},
    "estado": {"nombre": "Estado", "obligatorio": False, "alias": {"estado"}},
    "observacion": {"nombre": "Observacion", "obligatorio": False, "alias": {"observacion", "notas"}},
}


def sugerir_mapeo_proveedores(encabezados):
    resultado, usados = {}, set()
    for indice, encabezado in enumerate(encabezados):
        limpio, destino = normalizar(encabezado), ""
        for campo, definicion in CAMPOS_PROVEEDORES.items():
            if campo not in usados and limpio in definicion["alias"]:
                destino = campo
                usados.add(campo)
                break
        resultado[str(indice)] = destino
    return resultado


def _extraer(fila, mapeo):
    return {
        campo: (
            fila["valores"][int(indice)]
            if int(indice) < len(fila["valores"]) else ""
        )
        for indice, campo in mapeo.items() if campo
    }


def _cuit(valor):
    return re.sub(r"\D", "", str(valor or ""))


def _datos_normalizados(datos):
    estado = normalizar(datos.get("estado") or "activo")
    return {
        "codigo": str(datos.get("codigo") or "").strip().upper(),
        "razon_social": str(datos.get("razon_social") or "").strip(),
        "cuit": _cuit(datos.get("cuit")) or None,
        "email": str(datos.get("email") or "").strip().lower() or None,
        "telefono": str(datos.get("telefono") or "").strip() or None,
        "estado": estado,
        "observacion": str(datos.get("observacion") or "").strip() or None,
    }


def _datos_existentes(proveedor):
    return _datos_normalizados({
        campo: getattr(proveedor, campo, None) for campo in CAMPOS_PROVEEDORES
    })


def previsualizar_proveedores(filas, mapeo, *, proveedores):
    destinos = [campo for campo in mapeo.values() if campo]
    if len(destinos) != len(set(destinos)):
        raise ValueError("Un campo del sistema no puede recibir dos columnas.")
    faltantes = [
        definicion["nombre"]
        for campo, definicion in CAMPOS_PROVEEDORES.items()
        if definicion["obligatorio"] and campo not in destinos
    ]
    if faltantes:
        raise ValueError("Faltan campos obligatorios: " + ", ".join(faltantes) + ".")

    por_codigo = {str(item.codigo or "").strip().upper(): item for item in proveedores}
    por_cuit = {_cuit(item.cuit): item for item in proveedores if _cuit(item.cuit)}
    codigos_archivo, cuits_archivo, resultado = set(), set(), []
    for fila in filas:
        datos = _datos_normalizados(_extraer(fila, mapeo))
        errores = []
        if not datos["codigo"]:
            errores.append("Falta codigo")
        if not datos["razon_social"]:
            errores.append("Falta razon social")
        if datos["estado"] not in {"activo", "inactivo"}:
            errores.append("Estado invalido")
        if datos["cuit"] and len(datos["cuit"]) != 11:
            errores.append("CUIT invalido")
        if datos["email"] and (
            "@" not in datos["email"] or len(datos["email"]) > 200
        ):
            errores.append("Email invalido")
        if len(datos["codigo"]) > 80 or len(datos["razon_social"]) > 200:
            errores.append("Codigo o razon social demasiado largo")
        if datos["codigo"] in codigos_archivo:
            errores.append("Codigo duplicado en el archivo")
        codigos_archivo.add(datos["codigo"])
        if datos["cuit"]:
            if datos["cuit"] in cuits_archivo:
                errores.append("CUIT duplicado en el archivo")
            cuits_archivo.add(datos["cuit"])

        existente_codigo = por_codigo.get(datos["codigo"])
        existente_cuit = por_cuit.get(datos["cuit"]) if datos["cuit"] else None
        if existente_codigo and existente_cuit and existente_codigo.id != existente_cuit.id:
            errores.append("El codigo y el CUIT pertenecen a proveedores distintos")
        existente = existente_codigo or existente_cuit
        accion = "rechazado" if errores else "actualizar" if existente else "crear"
        if existente and not errores and _datos_existentes(existente) == datos:
            accion = "sin_cambios"
        resultado.append({
            "numero": fila["numero"], "datos": datos,
            "proveedor_id": getattr(existente, "id", None),
            "accion": accion, "errores": errores,
        })
    return resultado


def resumir_proveedores(vista):
    return {
        clave: sum(fila["accion"] == clave for fila in vista)
        for clave in ("crear", "actualizar", "sin_cambios", "rechazado")
    }


def aplicar_proveedores(
    vista, *, organizacion_id, ProveedorCompra, db_session, commit=True,
):
    conteos = resumir_proveedores(vista)
    for fila in vista:
        if fila["accion"] not in {"crear", "actualizar"}:
            continue
        if fila["accion"] == "actualizar":
            proveedor = ProveedorCompra.query.filter_by(
                id=fila["proveedor_id"], organizacion_id=organizacion_id,
            ).first()
            if proveedor is None:
                raise ValueError("El proveedor cambio o ya no pertenece a la organizacion.")
        else:
            proveedor = ProveedorCompra(organizacion_id=organizacion_id)
            db_session.add(proveedor)
        for campo, valor in fila["datos"].items():
            setattr(proveedor, campo, valor)
    try:
        db_session.flush()
        if commit:
            db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return {
        "creados": conteos["crear"],
        "actualizados": conteos["actualizar"],
        "sin_cambios": conteos["sin_cambios"],
        "rechazados": conteos["rechazado"],
    }
