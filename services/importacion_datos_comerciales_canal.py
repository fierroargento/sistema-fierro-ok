"""Importa observaciones comerciales por seccion sin consultar canales externos."""

from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import Workbook

from services.importacion_productos_costeo import normalizar
from services.promociones_canal import registrar_observacion


COMUNES = {
    "lista_codigo": ("Codigo de lista", {"lista", "codigo lista", "codigo de lista"}),
    "catalogo_codigo": ("Codigo de catalogo", {"catalogo", "codigo catalogo", "codigo de catalogo"}),
    "sku_comercial": ("SKU comercial", {"sku", "sku comercial"}),
    "cuenta_codigo": ("Cuenta del canal", {"cuenta", "cuenta canal", "cuenta del canal"}),
    "referencia_publicacion": ("Referencia publicacion", {"publicacion", "id publicacion", "referencia publicacion"}),
}
ESPECIFICOS = {
    "precios": {"precio_publicado": ("Precio publicado", {"precio", "precio publicado"})},
    "promociones": {
        "nombre_promocion": ("Nombre promocion", {"promocion", "nombre promocion"}),
        "precio_base": ("Precio base", {"precio base", "precio original"}),
        "precio_promocional": ("Precio promocional", {"precio promocional", "precio oferta"}),
        "estado_promocion": ("Estado promocion", {"estado", "estado promocion"}),
    },
    "cargos": {
        "comision_pct": ("Comision porcentual", {"comision", "comision porcentual", "comision pct"}),
        "cargo_fijo": ("Cargo fijo", {"cargo", "cargo fijo"}),
    },
    "envios": {"costo_envio": ("Costo de envio", {"envio", "costo envio", "costo de envio"})},
}
TIPOS_MODELO = {"precios": "precio", "cargos": "cargo", "envios": "envio"}


def campos_para(tipo):
    if tipo not in ESPECIFICOS: raise ValueError("La seccion comercial no es valida.")
    campos = {}
    for clave, (nombre, alias) in {**COMUNES, **ESPECIFICOS[tipo]}.items():
        campos[clave] = {"nombre": nombre, "alias": alias, "obligatorio": clave != "nombre_promocion"}
    return campos


def sugerir_mapeo(encabezados, tipo):
    campos = campos_para(tipo); resultado = {}; usados = set()
    for indice, encabezado in enumerate(encabezados):
        limpio = normalizar(encabezado); destino = ""
        for clave, definicion in campos.items():
            if clave not in usados and limpio in definicion["alias"]:
                destino = clave; usados.add(clave); break
        resultado[str(indice)] = destino
    return resultado


def validar_mapeo(mapeo, tipo):
    campos = campos_para(tipo); destinos = [valor for valor in mapeo.values() if valor]
    if len(destinos) != len(set(destinos)): raise ValueError("Un campo no puede recibir dos columnas.")
    faltantes = [d["nombre"] for clave, d in campos.items() if d["obligatorio"] and clave not in destinos]
    if faltantes: raise ValueError("Faltan campos obligatorios: " + ", ".join(faltantes) + ".")


def _centavos(valor, nombre, errores):
    texto = str(valor or "").strip().replace(" ", "")
    if "," in texto and "." in texto: texto = texto.replace(".", "").replace(",", ".")
    else: texto = texto.replace(",", ".")
    try: numero = Decimal(texto)
    except InvalidOperation: errores.append(f"{nombre} no es valido"); return None
    if numero < 0: errores.append(f"{nombre} no puede ser negativo"); return None
    return int((numero * 100).quantize(Decimal("1")))


def _porcentaje(valor, errores):
    try: numero = Decimal(str(valor or "").replace(",", "."))
    except InvalidOperation: errores.append("La comision no es valida"); return None
    if numero < 0 or numero >= 100: errores.append("La comision debe estar entre 0 y menos de 100"); return None
    return str(numero)


def previsualizar(filas, mapeo, tipo, *, organizacion_id, unidad_negocio_id, modelos):
    validar_mapeo(mapeo, tipo); resultado = []; identidades = set()
    Lista, Catalogo, Inclusion = modelos["ListaPrecio"], modelos["Catalogo"], modelos["CatalogoProducto"]
    for fila in filas:
        datos = {campo: fila["valores"][int(i)] if int(i) < len(fila["valores"]) else "" for i, campo in mapeo.items() if campo}
        lista_codigo = str(datos.get("lista_codigo") or "").strip().lower()
        catalogo_codigo = str(datos.get("catalogo_codigo") or "").strip().lower()
        sku = str(datos.get("sku_comercial") or "").strip().upper()
        cuenta = str(datos.get("cuenta_codigo") or "").strip()
        referencia = str(datos.get("referencia_publicacion") or "").strip()
        errores = []; identidad = (cuenta.lower(), referencia.lower(), tipo)
        if identidad in identidades: errores.append("El archivo contiene una observacion duplicada")
        identidades.add(identidad)
        lista = Lista.query.filter_by(organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id, codigo=lista_codigo).first()
        catalogo = Catalogo.query.filter_by(organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id, codigo=catalogo_codigo).first()
        inclusion = None
        if lista is None: errores.append("No existe la lista en la unidad activa")
        if catalogo is None: errores.append("No existe el catalogo en la unidad activa")
        if catalogo is not None:
            opciones = Inclusion.query.filter(Inclusion.catalogo_id == catalogo.id, Inclusion.sku_comercial.ilike(sku)).all()
            if len(opciones) != 1: errores.append("No se encontro una unica inclusion para el SKU")
            else: inclusion = opciones[0]
        normalizados = {"cuenta_codigo": cuenta, "referencia_publicacion": referencia}
        if not cuenta: errores.append("Falta la cuenta del canal")
        if not referencia: errores.append("Falta la referencia de publicacion")
        if tipo == "precios": normalizados["precio_publicado_centavos"] = _centavos(datos.get("precio_publicado"), "El precio publicado", errores)
        elif tipo == "promociones":
            normalizados.update({
                "nombre_promocion": str(datos.get("nombre_promocion") or "").strip() or None,
                "precio_base_centavos": _centavos(datos.get("precio_base"), "El precio base", errores),
                "precio_promocional_centavos": _centavos(datos.get("precio_promocional"), "El precio promocional", errores),
                "estado_observado": str(datos.get("estado_promocion") or "").strip().lower(),
            })
            if normalizados["estado_observado"] not in {"activa", "inactiva"}: errores.append("El estado debe ser activa o inactiva")
            if not errores and normalizados["precio_promocional_centavos"] > normalizados["precio_base_centavos"]: errores.append("El precio promocional supera al precio base")
        elif tipo == "cargos":
            normalizados["comision_pct"] = _porcentaje(datos.get("comision_pct"), errores)
            normalizados["cargo_fijo_centavos"] = _centavos(datos.get("cargo_fijo"), "El cargo fijo", errores)
        else: normalizados["costo_envio_centavos"] = _centavos(datos.get("costo_envio"), "El costo de envio", errores)
        resultado.append({"numero": fila["numero"], "lista_id": getattr(lista, "id", None), "inclusion_id": getattr(inclusion, "id", None), "lista_codigo": lista_codigo, "sku_comercial": sku, "datos": normalizados, "accion": "rechazado" if errores else "crear_observacion", "errores": errores})
    return resultado


def aplicar(vista, tipo, *, organizacion_id, unidad_negocio_id, lote_id, usuario, modelos, db_session):
    conteos = {"creados": 0, "actualizados": 0, "sin_cambios": 0, "rechazados": 0}
    try:
        for fila in vista:
            if fila["accion"] == "rechazado": conteos["rechazados"] += 1; continue
            datos = fila["datos"]
            if tipo == "promociones":
                registrar_observacion(
                    organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
                    lista_precio_id=fila["lista_id"], catalogo_producto_id=fila["inclusion_id"],
                    referencia_externa=datos["referencia_publicacion"], nombre=datos["nombre_promocion"],
                    precio_base_centavos=datos["precio_base_centavos"], precio_promocional_centavos=datos["precio_promocional_centavos"],
                    estado_observado=datos["estado_observado"], origen="importacion", observacion=f"Lote {lote_id}", usuario=usuario,
                    PromocionCanalObservacion=modelos["PromocionCanalObservacion"], db_session=db_session,
                    commit=False, cuenta_codigo=datos["cuenta_codigo"],
                )
            else:
                registro = modelos["ObservacionComercialCanal"](
                    organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
                    lista_precio_id=fila["lista_id"], catalogo_producto_id=fila["inclusion_id"],
                    tipo=TIPOS_MODELO[tipo], origen="importacion", lote_importacion_id=lote_id,
                    creado_por_usuario_id=getattr(usuario, "id", None), creado_por_username=getattr(usuario, "username", None),
                    **datos,
                )
                db_session.add(registro)
            conteos["creados"] += 1
        db_session.commit()
    except Exception: db_session.rollback(); raise
    return conteos


def plantilla(tipo):
    campos = campos_para(tipo); libro = Workbook(); hoja = libro.active; hoja.title = tipo.capitalize()
    hoja.append([definicion["nombre"].upper() for definicion in campos.values()])
    ejemplos = {"lista_codigo": "canal-principal", "catalogo_codigo": "catalogo-general", "sku_comercial": "SKU-001", "cuenta_codigo": "cuenta-01", "referencia_publicacion": "PUB-001", "precio_publicado": 1500, "nombre_promocion": "Oferta", "precio_base": 1500, "precio_promocional": 1400, "estado_promocion": "activa", "comision_pct": 15, "cargo_fijo": 100, "costo_envio": 500}
    hoja.append([ejemplos[clave] for clave in campos])
    salida = BytesIO(); libro.save(salida); salida.seek(0); return salida
