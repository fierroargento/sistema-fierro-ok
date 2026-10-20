"""Alta y gestión del producto único, con concurrencia y contrato común."""
from hashlib import sha256
import json
import math

from sqlalchemy import inspect, select

from services.producto_habilitaciones import CAMPOS_FICHA, TIPOS, USOS, esquema_ficha_disponible
from services.productos_combo_maestro import normalizar_componentes, preparar_composicion, guardar_composicion, leer_composiciones

CAMPOS_LOGISTICA = ("peso_gr", "alto_cm", "ancho_cm", "largo_cm", "permite_correo",
    "permite_via_cargo", "requiere_revision_logistica", "observacion_logistica")
CAMPOS_BASE = ("sku", "descripcion") + CAMPOS_LOGISTICA


def texto(valor, nombre, limite, obligatorio=False):
    salida = str(valor if valor is not None else "").strip()
    if obligatorio and not salida:
        raise ValueError(f"Completá {nombre}.")
    if len(salida) > limite:
        raise ValueError(f"{nombre} admite hasta {limite} caracteres.")
    return salida


def booleano(valor, nombre):
    if isinstance(valor, bool):
        return valor
    limpio = str(valor).strip().lower()
    if limpio in {"1", "si", "sí", "true", "on", "x"}:
        return True
    if limpio in {"0", "no", "false", "off"}:
        return False
    raise ValueError(f"{nombre}: indicá Sí o No.")


def normalizar_ficha(datos):
    """El formulario y los lotes pasan por las mismas validaciones."""
    salida = {
        "sku": texto(datos.get("sku"), "SKU", 80, True).upper(),
        "nombre": texto(datos.get("nombre"), "nombre", 200, True),
        "linea": texto(datos.get("linea"), "línea", 120),
        "descripcion": texto(datos.get("descripcion"), "descripción", 255),
        "unidad_medida": texto(datos.get("unidad_medida"), "unidad de medida", 30, True).lower(),
        "tipo": texto(datos.get("tipo"), "tipo de producto", 20, True).lower().replace("ó", "o"),
    }
    if salida["tipo"] == "de produccion":
        salida["tipo"] = "produccion"
    if salida["tipo"] not in TIPOS:
        raise ValueError("Elegí Simple, De producción o Combo.")
    salida["no_stockeable"] = booleano(datos.get("no_stockeable", False), "No stockeable")
    salida["permitir_stock_negativo"] = booleano(datos.get("permitir_stock_negativo", False), "Permitir stock negativo")
    if salida["no_stockeable"] and salida["permitir_stock_negativo"]:
        raise ValueError("No stockeable y Permitir stock negativo son opciones incompatibles. Elegí una sola.")
    for campo in ("activo",) + tuple("habilita_" + uso for uso in USOS):
        salida[campo] = booleano(datos.get(campo), campo.replace("_", " "))
    for campo in CAMPOS_LOGISTICA:
        valor = datos.get(campo)
        if campo in {"peso_gr", "alto_cm", "ancho_cm", "largo_cm"}:
            if valor in (None, ""):
                salida[campo] = None
            else:
                try:
                    numero = float(str(valor).strip().replace(",", "."))
                except (ValueError, TypeError) as error:
                    raise ValueError(f"{campo}: ingresá un número mayor que cero.") from error
                if not math.isfinite(numero) or numero <= 0 or numero > 10**9:
                    raise ValueError(f"{campo}: ingresá un número válido mayor que cero.")
                salida[campo] = numero
        elif campo == "observacion_logistica":
            salida[campo] = texto(valor, "observación logística", 300)
        else:
            salida[campo] = booleano(valor, campo.replace("_", " "))
    if salida["no_stockeable"] and (salida["permite_correo"] or salida["permite_via_cargo"]):
        raise ValueError("Un producto No stockeable no admite envío físico. Destildá Permite Correo y Permite Vía Cargo.")
    ident = datos.get("insumo_id")
    if ident in (None, ""):
        salida["insumo_id"] = None
    elif isinstance(ident, bool) or not str(ident).isdigit() or int(ident) <= 0:
        raise ValueError("La referencia de insumo no es válida.")
    else:
        salida["insumo_id"] = int(ident)
    if "componentes_combo" in datos:
        salida["componentes_combo"] = normalizar_componentes(datos["componentes_combo"])
    unidad_combo = datos.get("unidad_combo_id")
    if unidad_combo in (None, ""):
        salida["unidad_combo_id"] = None
    elif isinstance(unidad_combo, bool) or not str(unidad_combo).isdigit() or int(unidad_combo) <= 0:
        raise ValueError("La unidad del combo no es válida.")
    else:
        salida["unidad_combo_id"] = int(unidad_combo)
    return salida


def datos_de_formulario(formulario):
    datos = dict(formulario)
    if datos.get("tipo") == "combo":
        try:
            datos["componentes_combo"] = json.loads(formulario.get("componentes_combo_json", "[]"))
        except (ValueError, TypeError) as error:
            raise ValueError("La composición del combo no es válida.") from error
    for campo in ("activo", "no_stockeable", "permitir_stock_negativo", "permite_correo", "permite_via_cargo", "requiere_revision_logistica") + tuple("habilita_" + uso for uso in USOS):
        datos[campo] = "1" if formulario.get(campo) == "1" else "0"
    return normalizar_ficha(datos)


def huella(producto, ficha, composiciones=None, adicionales=None, producciones=None):
    if producto is None:
        return "nuevo"
    datos = {c: getattr(producto, c) for c in CAMPOS_BASE}
    datos["producto_id"] = producto.id
    datos["ficha"] = ({c: getattr(ficha, c) for c in CAMPOS_FICHA} | {"revision": ficha.revision}) if ficha else None
    if (ficha and ficha.tipo == "combo") or ficha is None:
        if composiciones is None:
            composiciones = leer_composiciones([producto], inspect(producto).session, producto.organizacion_id).get(producto.id, [])
        datos["composiciones_combo"] = composiciones
    if ficha is None or ficha.tipo == "produccion":
        if producciones is None:
            from services.productos_produccion_maestro import leer_producciones
            producciones = leer_producciones([producto], inspect(producto).session, producto.organizacion_id).get(producto.id, [])
        datos["fabricacion"] = producciones
    from services.productos_datos_generales import cargar_datos_productos
    if adicionales is None:
        adicionales = cargar_datos_productos([producto], inspect(producto).session, producto.organizacion_id).get(producto.id, {})
    if adicionales:
        datos["datos_generales"] = adicionales
    return sha256(json.dumps(datos, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def perfiles_del_producto(producto, db_session):
    tabla = producto.metadata.tables.get("perfil_costeo_producto")
    if tabla is None or not inspect(db_session.connection()).has_table(tabla.name):
        return []
    return list(db_session.execute(select(tabla.c.tipo, tabla.c.unidad_negocio_id).where(
        tabla.c.organizacion_id == producto.organizacion_id,
        tabla.c.producto_id == producto.id,
    )).mappings())


def validar_vinculos(producto, datos, db_session, organizacion_id):
    if producto is not None:
        from models.producto_ficha_maestra import ProductoFichaMaestra
        anterior = db_session.query(ProductoFichaMaestra).filter_by(
            producto_id=producto.id, organizacion_id=organizacion_id,
        ).first()
        if anterior and anterior.tipo != datos["tipo"] and "combo" in {anterior.tipo, datos["tipo"]}:
            raise ValueError("El combo necesita un producto y SKU propios. No se puede convertir un producto simple o de producción en combo, ni el combo en otro tipo, conservando su SKU. Creá otro producto.")
        if not datos["permitir_stock_negativo"]:
            tabla = producto.metadata.tables.get("existencia_sucursal")
            if tabla is not None and inspect(db_session.connection()).has_table(tabla.name):
                pendiente = select(tabla.c.id).where(
                    tabla.c.organizacion_id == organizacion_id, tabla.c.producto_id == producto.id,
                    (tabla.c.stock_actual < 0) |
                    (tabla.c.stock_actual < tabla.c.stock_reservado + tabla.c.stock_bloqueado),
                )
                if db_session.execute(pendiente.limit(1)).first() is not None:
                    raise ValueError("No se puede desactivar Permitir stock negativo mientras haya saldos negativos o compromisos sin cobertura. Regularizá las existencias primero.")
        if datos["no_stockeable"]:
            inspector = inspect(db_session.connection())
            for nombre in ("existencia_sucursal", "item_inventario"):
                tabla = producto.metadata.tables.get(nombre)
                if tabla is None or not inspector.has_table(nombre):
                    continue
                consulta = select(tabla.c.id).where(
                    tabla.c.organizacion_id == organizacion_id,
                    tabla.c.producto_id == producto.id,
                )
                if nombre == "item_inventario":
                    consulta = consulta.where(tabla.c.activo.is_(True))
                if db_session.execute(consulta.limit(1)).first() is not None:
                    raise ValueError("El producto ya tiene existencias o un SKU de inventario activo. No se puede convertir a No stockeable sin revisar su historial y compromisos.")
        tipos = {p["tipo"] for p in perfiles_del_producto(producto, db_session)}
        if tipos and tipos != {datos["tipo"]}:
            raise ValueError("El producto tiene perfiles de costeo de otro tipo. Revisalos antes de cambiar el tipo maestro; no se transforma su composición automáticamente.")
    if datos["insumo_id"] is not None:
        from models.fuentes_costo_productivo import InsumoProductivo
        insumo = db_session.query(InsumoProductivo).filter_by(id=datos["insumo_id"], organizacion_id=organizacion_id).first()
        if insumo is None or insumo.tipo == "servicio_productivo":
            raise ValueError("Elegí una referencia de insumo físico de esta organización.")
        if insumo.unidad_medida.strip().lower() != datos["unidad_medida"]:
            raise ValueError("La unidad debe coincidir con la referencia de insumo; no se convierten saldos por suposición.")
        from models.producto_ficha_maestra import ProductoFichaMaestra
        otro = db_session.query(ProductoFichaMaestra).filter_by(insumo_id=insumo.id).first()
        if otro is not None and (producto is None or otro.producto_id != producto.id):
            raise ValueError("Ese insumo ya está vinculado a otro producto. Usá su ficha existente.")


def guardar_ficha(datos, *, Producto, db_session, organizacion_id, producto_id=None,
                  huella_esperada="nuevo", commit=True):
    from models.producto_ficha_maestra import ProductoFichaMaestra
    if not esquema_ficha_disponible(db_session):
        raise ValueError("La ficha ampliada todavía no está preparada. No se guardó ningún cambio.")
    datos = normalizar_ficha(datos)
    producto = None
    ficha = None
    if producto_id is not None:
        producto = db_session.query(Producto).filter_by(id=producto_id, organizacion_id=organizacion_id).with_for_update().populate_existing().first()
        if producto is None:
            raise ValueError("El producto no pertenece a la organización activa.")
        ficha = db_session.query(ProductoFichaMaestra).filter_by(producto_id=producto.id, organizacion_id=organizacion_id).populate_existing().first()
        if datos["sku"] != producto.sku.strip().upper():
            raise ValueError("El SKU identifica al producto y se conserva al editar su ficha.")
    if huella(producto, ficha) != huella_esperada:
        raise ValueError("El producto cambió desde que abriste la ficha. Cerrá y volvé a abrir para revisar sus datos actuales.")
    if ficha is not None and ficha.insumo_id is not None and ficha.insumo_id != datos["insumo_id"]:
        raise ValueError("La referencia de insumo ya guardada se conserva para mantener su identidad e historial.")
    existente = db_session.query(Producto).filter(Producto.organizacion_id == organizacion_id, Producto.sku.ilike(datos["sku"])).first()
    if existente is not None and (producto is None or existente.id != producto.id):
        if datos["tipo"] == "combo":
            raise ValueError("Ese SKU ya existe. El combo necesita otro SKU propio; sus componentes conservan los suyos.")
        raise ValueError("Ya existe un producto con ese SKU. Usá Gestionar.")
    validar_vinculos(producto, datos, db_session, organizacion_id)
    plan_combo = preparar_composicion(producto, datos, db_session, organizacion_id)
    if producto is None:
        producto = Producto(organizacion_id=organizacion_id, sku=datos["sku"], descripcion=datos["descripcion"])
        db_session.add(producto)
        db_session.flush()
    for campo in ("descripcion",) + CAMPOS_LOGISTICA:
        setattr(producto, campo, datos[campo])
    if ficha is None:
        ficha = ProductoFichaMaestra(producto_id=producto.id, organizacion_id=organizacion_id, revision=1)
        db_session.add(ficha)
    else:
        ficha.revision += 1
    for campo in CAMPOS_FICHA:
        setattr(ficha, campo, datos[campo])
    db_session.flush()
    guardar_composicion(producto, plan_combo, db_session)
    if commit:
        db_session.commit()
    return producto


def construir_filas(productos, db_session, organizacion_id):
    from models.producto_ficha_maestra import ProductoFichaMaestra
    preparado = esquema_ficha_disponible(db_session)
    fichas = {f.producto_id: f for f in db_session.query(ProductoFichaMaestra).filter(
        ProductoFichaMaestra.organizacion_id == organizacion_id,
        ProductoFichaMaestra.producto_id.in_([p.id for p in productos]),
    ).all()} if preparado and productos else {}
    perfiles_por_producto = {}
    tabla = productos[0].metadata.tables.get("perfil_costeo_producto") if productos else None
    if tabla is not None and inspect(db_session.connection()).has_table(tabla.name):
        for registro in db_session.execute(select(tabla.c.producto_id, tabla.c.tipo).where(
                tabla.c.organizacion_id == organizacion_id,
                tabla.c.producto_id.in_([p.id for p in productos]))).mappings():
            perfiles_por_producto.setdefault(registro["producto_id"], set()).add(registro["tipo"])
    composiciones = leer_composiciones(productos, db_session, organizacion_id)
    from services.productos_datos_generales import cargar_datos_productos
    adicionales = cargar_datos_productos(productos, db_session, organizacion_id)
    from services.productos_produccion_maestro import leer_producciones
    producciones = leer_producciones(productos, db_session, organizacion_id)
    filas = []
    for producto in productos:
        ficha = fichas.get(producto.id)
        tipos = sorted(perfiles_por_producto.get(producto.id, set()))
        datos = {c: getattr(producto, c) for c in CAMPOS_BASE}
        datos.update({c: getattr(ficha, c) for c in CAMPOS_FICHA} if ficha else {
            "nombre": producto.descripcion or "", "linea": "", "unidad_medida": "",
            "tipo": tipos[0] if len(tipos) == 1 else "", "activo": True, "no_stockeable": False, "permitir_stock_negativo": False,
            **{"habilita_" + uso: False for uso in USOS}, "insumo_id": None,
        })
        recetas = composiciones.get(producto.id, [])
        if datos["tipo"] == "combo":
            receta = next((r for r in recetas if r["unidad_combo_id"] is None), recetas[0] if recetas else None)
            datos["componentes_combo"] = [{"sku": c["sku"], "cantidad": c["cantidad"]} for c in receta["componentes_combo"]] if receta else []
            datos["unidad_combo_id"] = receta["unidad_combo_id"] if receta else None
        filas.append({"id": producto.id, "composiciones": recetas, "producciones": producciones.get(producto.id, []), "adicionales": adicionales.get(producto.id, {}), "configurado": ficha is not None,
            "datos": datos, "huella": huella(producto, ficha, recetas, adicionales.get(producto.id, {}), producciones.get(producto.id, [])), "tipos_previos": tipos,
            "usos": [etiqueta for uso, etiqueta in USOS.items() if ficha and getattr(ficha, "habilita_" + uso)]})
    return preparado, filas
