"""Importacion por archivos de ventas y movimientos financieros internos."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import Workbook

from services.conciliacion_liquidaciones_canal import registrar_movimiento, registrar_venta
from services.importacion_productos_costeo import normalizar
from services.reglas_economicas import calcular_pisos_regla, resolver_regla_vigente


COMUNES_VENTA = {
    "lista_codigo": ("Codigo de lista", {"lista", "codigo lista"}),
    "catalogo_codigo": ("Codigo de catalogo", {"catalogo", "codigo catalogo"}),
    "sku_comercial": ("SKU comercial", {"sku", "sku comercial"}),
    "cuenta_codigo": ("Cuenta del canal", {"cuenta", "cuenta canal"}),
    "referencia_venta": ("Referencia venta", {"venta", "id venta", "referencia venta"}),
    "referencia_item": ("Referencia item", {"item", "id item", "referencia item"}),
    "referencia_pago": ("Referencia pago", {"pago", "id pago", "referencia pago"}),
    "cantidad": ("Cantidad", {"cantidad", "unidades"}),
    "precio_unitario": ("Precio unitario", {"precio", "precio unitario"}),
    "estado_venta": ("Estado venta", {"estado", "estado venta"}),
    "fecha_venta": ("Fecha venta", {"fecha", "fecha venta"}),
}
COMUNES_MOVIMIENTO = {
    "cuenta_codigo": ("Cuenta del canal", {"cuenta", "cuenta canal"}),
    "referencia_venta": ("Referencia venta", {"venta", "id venta", "referencia venta"}),
    "referencia_pago": ("Referencia pago", {"pago", "id pago", "referencia pago"}),
    "referencia_movimiento": ("Referencia movimiento", {"movimiento", "id movimiento", "referencia movimiento"}),
    "tipo_movimiento": ("Tipo movimiento", {"tipo", "tipo movimiento"}),
    "direccion": ("Direccion", {"direccion", "credito debito"}),
    "importe": ("Importe", {"importe", "monto"}),
    "impacta_saldo": ("Impacta saldo", {"impacta", "impacta saldo"}),
    "estado_movimiento": ("Estado movimiento", {"estado", "estado movimiento"}),
    "fecha_movimiento": ("Fecha movimiento", {"fecha", "fecha movimiento"}),
    "detalle": ("Detalle", {"detalle", "concepto"}),
}


def campos_para(tipo):
    if tipo == "ventas": origen = COMUNES_VENTA
    elif tipo == "movimientos": origen = COMUNES_MOVIMIENTO
    else: raise ValueError("El tipo de conciliacion no es valido.")
    opcionales = {"referencia_pago", "detalle"}
    return {
        clave: {
            "nombre": nombre,
            "alias": set(alias) | {normalizar(nombre)},
            "obligatorio": clave not in opcionales,
        }
        for clave, (nombre, alias) in origen.items()
    }


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


def _centavos(valor, errores):
    texto = str(valor or "").strip().replace(" ", "")
    if "," in texto and "." in texto: texto = texto.replace(".", "").replace(",", ".")
    else: texto = texto.replace(",", ".")
    try: numero = Decimal(texto)
    except InvalidOperation: errores.append("El importe no es valido"); return None
    if numero < 0: errores.append("El importe no puede ser negativo"); return None
    return int((numero * 100).quantize(Decimal("1")))


def _fecha(valor, errores):
    texto = str(valor or "").strip()
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try: return datetime.strptime(texto, formato).isoformat()
        except ValueError: pass
    errores.append("La fecha no es valida"); return None


def _booleano(valor, errores):
    texto = normalizar(valor)
    if texto in {"si", "1", "true", "verdadero"}: return True
    if texto in {"no", "0", "false", "falso"}: return False
    errores.append("Impacta saldo debe ser SI o NO"); return None


def _datos_fila(fila, mapeo):
    return {campo: fila["valores"][int(i)] if int(i) < len(fila["valores"]) else "" for i, campo in mapeo.items() if campo}


def previsualizar_ventas(filas, mapeo, *, organizacion_id, unidad_negocio_id, modelos):
    validar_mapeo(mapeo, "ventas"); resultado = []; vistas = set()
    Lista, Catalogo, Inclusion = modelos["ListaPrecio"], modelos["Catalogo"], modelos["CatalogoProducto"]
    existentes = {(v.cuenta_codigo.lower(), v.referencia_venta.lower(), v.referencia_item.lower()) for v in modelos["VentaCanalItem"].query.filter_by(organizacion_id=organizacion_id).all()}
    reglas_economicas = modelos["ReglaEconomicaVersion"].query.filter(modelos["ReglaEconomicaVersion"].organizacion_id == organizacion_id).all()
    for fila in filas:
        datos = _datos_fila(fila, mapeo); errores = []
        lista_codigo = str(datos.get("lista_codigo") or "").strip().lower(); catalogo_codigo = str(datos.get("catalogo_codigo") or "").strip().lower(); sku = str(datos.get("sku_comercial") or "").strip().upper()
        cuenta = str(datos.get("cuenta_codigo") or "").strip(); venta = str(datos.get("referencia_venta") or "").strip(); item = str(datos.get("referencia_item") or "").strip()
        identidad = (cuenta.lower(), venta.lower(), item.lower())
        if identidad in vistas or identidad in existentes: errores.append("La venta/item ya existe o esta duplicada")
        vistas.add(identidad)
        lista = Lista.query.filter_by(organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id, codigo=lista_codigo).first()
        catalogo = Catalogo.query.filter_by(organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id, codigo=catalogo_codigo).first()
        inclusion = None
        if lista is None: errores.append("No existe la lista en la unidad activa")
        if catalogo is None: errores.append("No existe el catalogo en la unidad activa")
        if catalogo is not None:
            opciones = Inclusion.query.filter(Inclusion.catalogo_id == catalogo.id, Inclusion.sku_comercial.ilike(sku)).all()
            if len(opciones) != 1: errores.append("No se encontro una unica inclusion para el SKU")
            else: inclusion = opciones[0]
        regla_canal = modelos["ReglaCanalVersion"].query.filter_by(lista_precio_id=getattr(lista, "id", None), vigente=True).first() if lista else None
        if regla_canal is None: errores.append("La lista no tiene politica de canal vigente")
        try: cantidad = int(datos.get("cantidad"))
        except (TypeError, ValueError): cantidad = 0; errores.append("La cantidad no es valida")
        if cantidad <= 0 and "La cantidad no es valida" not in errores: errores.append("La cantidad debe ser positiva")
        estado = str(datos.get("estado_venta") or "").strip().lower()
        if estado not in {"confirmada", "cancelada", "devuelta", "devolucion_parcial"}: errores.append("El estado de venta no es valido")
        precio = _centavos(datos.get("precio_unitario"), errores); fecha = _fecha(datos.get("fecha_venta"), errores)
        costo = modelos["CostoProductoVersion"].query.filter_by(organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id, producto_id=getattr(inclusion, "producto_id", None), vigente=True).first() if inclusion else None
        regla_economica = resolver_regla_vigente(reglas_economicas, unidad_negocio_id=unidad_negocio_id, catalogo_id=getattr(inclusion, "catalogo_id", None), producto_id=getattr(inclusion, "producto_id", None)) if inclusion else None
        piso = calcular_pisos_regla(costo.costo_total_centavos, regla_economica)["minimo"]["piso_liquidacion_centavos"] if costo and regla_economica else None
        normalizados = {"cuenta_codigo": cuenta, "referencia_venta": venta, "referencia_item": item, "referencia_pago": str(datos.get("referencia_pago") or "").strip() or None, "cantidad": cantidad, "precio_unitario_centavos": precio, "estado": estado, "fecha_venta": fecha, "costo_unitario_centavos": getattr(costo, "costo_total_centavos", None), "piso_unitario_centavos": piso}
        resultado.append({"numero": fila["numero"], "lista_id": getattr(lista, "id", None), "inclusion_id": getattr(inclusion, "id", None), "regla_canal_id": getattr(regla_canal, "id", None), "lista_codigo": lista_codigo, "sku_comercial": sku, "datos": normalizados, "accion": "rechazado" if errores else "crear", "errores": errores})
    return resultado


def previsualizar_movimientos(filas, mapeo, *, organizacion_id, unidad_negocio_id, modelos):
    validar_mapeo(mapeo, "movimientos"); resultado = []; vistas = set()
    existentes = {(m.cuenta_codigo.lower(), m.referencia_movimiento.lower()) for m in modelos["MovimientoLiquidacionCanal"].query.filter_by(organizacion_id=organizacion_id).all()}
    ventas = modelos["VentaCanalItem"].query.filter_by(organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id).all()
    for fila in filas:
        datos = _datos_fila(fila, mapeo); errores = []
        cuenta = str(datos.get("cuenta_codigo") or "").strip(); venta = str(datos.get("referencia_venta") or "").strip(); movimiento = str(datos.get("referencia_movimiento") or "").strip(); pago = str(datos.get("referencia_pago") or "").strip() or None
        identidad = (cuenta.lower(), movimiento.lower())
        if identidad in vistas or identidad in existentes: errores.append("El movimiento ya existe o esta duplicado")
        vistas.add(identidad)
        ventas_propias = [v for v in ventas if v.cuenta_codigo == cuenta and v.referencia_venta == venta]
        if not ventas_propias: errores.append("No existe la venta para esa cuenta")
        elif pago and any(v.referencia_pago and v.referencia_pago != pago for v in ventas_propias): errores.append("La referencia de pago no coincide con la venta")
        tipo = str(datos.get("tipo_movimiento") or "").strip().lower(); direccion = str(datos.get("direccion") or "").strip().lower()
        if tipo not in {"pago_bruto", "liquidacion_neta", "comision", "cargo_fijo", "envio", "impuesto", "retencion", "devolucion", "ajuste"}: errores.append("El tipo de movimiento no es valido")
        if direccion not in {"credito", "debito"}: errores.append("La direccion no es valida")
        normalizados = {"cuenta_codigo": cuenta, "referencia_venta": venta, "referencia_pago": pago, "referencia_movimiento": movimiento, "tipo": tipo, "direccion": direccion, "importe_centavos": _centavos(datos.get("importe"), errores), "impacta_saldo": _booleano(datos.get("impacta_saldo"), errores), "estado": str(datos.get("estado_movimiento") or "confirmado").strip().lower(), "fecha_movimiento": _fecha(datos.get("fecha_movimiento"), errores), "detalle": str(datos.get("detalle") or "").strip() or None}
        resultado.append({"numero": fila["numero"], "lista_codigo": "", "sku_comercial": "", "datos": normalizados, "accion": "rechazado" if errores else "crear", "errores": errores})
    return resultado


def aplicar(vista, tipo, *, organizacion_id, unidad_negocio_id, usuario, modelos, db_session):
    conteos = {"creados": 0, "actualizados": 0, "sin_cambios": 0, "rechazados": 0}
    try:
        for fila in vista:
            if fila["accion"] == "rechazado": conteos["rechazados"] += 1; continue
            datos = dict(fila["datos"])
            if tipo == "ventas":
                regla = modelos["ReglaCanalVersion"].query.get(fila["regla_canal_id"])
                datos["fecha_venta"] = datetime.fromisoformat(datos["fecha_venta"])
                registrar_venta(organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id, lista_precio_id=fila["lista_id"], catalogo_producto_id=fila["inclusion_id"], regla_canal=regla, origen="importacion", usuario=usuario, VentaCanalItem=modelos["VentaCanalItem"], db_session=db_session, commit=False, **datos)
            else:
                datos["fecha_movimiento"] = datetime.fromisoformat(datos["fecha_movimiento"])
                registrar_movimiento(organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id, origen="importacion", usuario=usuario, MovimientoLiquidacionCanal=modelos["MovimientoLiquidacionCanal"], db_session=db_session, commit=False, **datos)
            conteos["creados"] += 1
        db_session.commit()
    except Exception: db_session.rollback(); raise
    return conteos


def plantilla(tipo):
    campos = campos_para(tipo); libro = Workbook(); hoja = libro.active; hoja.title = tipo.capitalize(); hoja.append([d["nombre"].upper() for d in campos.values()])
    ejemplos = {"lista_codigo": "canal-principal", "catalogo_codigo": "catalogo-general", "sku_comercial": "SKU-001", "cuenta_codigo": "cuenta-01", "referencia_venta": "VENTA-001", "referencia_item": "ITEM-001", "referencia_pago": "PAGO-001", "cantidad": 1, "precio_unitario": 1500, "estado_venta": "confirmada", "fecha_venta": "2026-09-04 10:00:00", "referencia_movimiento": "MOV-001", "tipo_movimiento": "liquidacion_neta", "direccion": "credito", "importe": 1200, "impacta_saldo": "SI", "estado_movimiento": "confirmado", "fecha_movimiento": "2026-09-05 10:00:00", "detalle": "Liquidacion observada"}
    hoja.append([ejemplos[clave] for clave in campos]); salida = BytesIO(); libro.save(salida); salida.seek(0); return salida
