"""Exportación tenant de respaldo técnico, de solo lectura y sin secretos."""

import hashlib
import io
import json
from datetime import date, datetime, timezone
from decimal import Decimal


MODELOS_POR_CONJUNTO = {
    "estructura": ("Organizacion", "UnidadNegocio", "SucursalOperativa", "EntidadFiscal", "ModuloOrganizacion"),
    "usuarios": ("UsuarioOrganizacion",),
    "catalogo": ("Producto", "Catalogo"),
    "costos": ("CostoProductoVersion", "InsumoProductivo", "MaquinaProductiva", "EmpleadoProductivo", "CostoFijoProductivo"),
    "inventario": ("ExistenciaSucursal", "MovimientoInventario"),
    "pedidos": ("Pedido",),
    "compras": ("ProveedorCompra", "OrdenCompra", "RecepcionCompra", "FacturaProveedorCompra", "MapeoInsumoInventario"),
    "produccion": ("OrdenProduccion", "ParteProduccion", "LoteProduccion", "ControlCalidadProduccion"),
    "tesoreria": ("CuentaTesoreria", "MovimientoTesoreriaProyectado"),
    "contabilidad": ("CuentaContable", "AsientoContableBorrador", "LineaAsientoContableBorrador"),
    "postventa": ("CasoPostventa", "PropuestaResolucionPostventa", "ItemCasoPostventa", "EvidenciaCasoPostventa"),
    "auditoria": ("Auditoria",),
}

MODELOS_HIJO_POR_CONJUNTO = {
    "catalogo": (("CatalogoProducto", "Catalogo", "catalogo_id"),),
    "costos": (("CostoProductoDetalle", "CostoProductoVersion", "costo_producto_version_id"),),
    "pedidos": (("PedidoItem", "Pedido", "pedido_id"),),
    "compras": (
        ("OrdenCompraItem", "OrdenCompra", "orden_compra_id"),
        ("RecepcionCompraItem", "RecepcionCompra", "recepcion_compra_id"),
    ),
    "produccion": (
        ("OrdenProduccionInsumo", "OrdenProduccion", "orden_produccion_id"),
        ("OrdenProduccionOperacion", "OrdenProduccion", "orden_produccion_id"),
        ("OrdenProduccionMaquina", "OrdenProduccion", "orden_produccion_id"),
    ),
}

CAMPOS_PROHIBIDOS = (
    "password", "contrasena", "contraseña", "token", "secret", "credential",
    "access_key", "refresh_key", "api_key", "authorization", "cookie", "session",
)


def _valor(valor):
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, bytes):
        return hashlib.sha256(valor).hexdigest()
    return valor


def _prohibido(nombre):
    normalizado = str(nombre).lower()
    return any(fragmento in normalizado for fragmento in CAMPOS_PROHIBIDOS)


def _columnas(Modelo):
    tabla = getattr(Modelo, "__table__", None)
    return list(tabla.columns) if tabla is not None else []


def _registros_modelo(Modelo, *, organizacion_id, unidad_negocio_id):
    columnas = _columnas(Modelo)
    nombres = {columna.name for columna in columnas}
    if Modelo.__name__ == "Organizacion" and "id" in nombres:
        consulta = Modelo.query.filter_by(id=organizacion_id)
    elif "organizacion_id" not in nombres:
        return [], "modelo_sin_identidad_tenant"
    else:
        consulta = Modelo.query.filter_by(organizacion_id=organizacion_id)
        if "unidad_negocio_id" in nombres:
            consulta = consulta.filter_by(unidad_negocio_id=unidad_negocio_id)
    filas = consulta.order_by(Modelo.id.asc()).all() if "id" in nombres else consulta.all()
    resultado = []
    for fila in filas:
        datos = {columna.name: _valor(getattr(fila, columna.name)) for columna in columnas if not _prohibido(columna.name)}
        datos["_modelo"] = Modelo.__name__
        resultado.append(datos)
    return resultado, None


def _registros_hijo(Modelo, Padre, clave_padre, *, organizacion_id, unidad_negocio_id):
    columnas_padre = {columna.name for columna in _columnas(Padre)}
    if "organizacion_id" not in columnas_padre:
        return [], "padre_sin_identidad_tenant"
    consulta_padre = Padre.query.filter_by(organizacion_id=organizacion_id)
    if "unidad_negocio_id" in columnas_padre:
        consulta_padre = consulta_padre.filter_by(unidad_negocio_id=unidad_negocio_id)
    padres = consulta_padre.all()
    columnas = _columnas(Modelo)
    if clave_padre not in {columna.name for columna in columnas}:
        return [], "clave_padre_inexistente"
    resultado = []
    for padre in padres:
        for fila in Modelo.query.filter_by(**{clave_padre: padre.id}).all():
            datos = {columna.name: _valor(getattr(fila, columna.name)) for columna in columnas if not _prohibido(columna.name)}
            datos["_modelo"] = Modelo.__name__
            resultado.append(datos)
    resultado.sort(key=lambda item: (item.get("_modelo", ""), item.get("id", 0)))
    return resultado, None


def construir_respaldo(*, organizacion_id, unidad_negocio_id, modelos):
    conjuntos = {}
    modelos_omitidos = []
    campos_omitidos = sorted(CAMPOS_PROHIBIDOS)
    for conjunto, nombres in MODELOS_POR_CONJUNTO.items():
        registros = []
        for nombre in nombres:
            Modelo = modelos.get(nombre)
            if Modelo is None:
                modelos_omitidos.append({"conjunto": conjunto, "modelo": nombre, "motivo": "modelo_no_disponible"})
                continue
            filas, motivo = _registros_modelo(Modelo, organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id)
            if motivo:
                modelos_omitidos.append({"conjunto": conjunto, "modelo": nombre, "motivo": motivo})
                continue
            registros.extend(filas)
        for nombre_hijo, nombre_padre, clave_padre in MODELOS_HIJO_POR_CONJUNTO.get(conjunto, ()):
            Hijo = modelos.get(nombre_hijo)
            Padre = modelos.get(nombre_padre)
            if Hijo is None or Padre is None:
                modelos_omitidos.append({"conjunto": conjunto, "modelo": nombre_hijo, "motivo": "modelo_hijo_o_padre_no_disponible"})
                continue
            filas, motivo = _registros_hijo(Hijo, Padre, clave_padre, organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id)
            if motivo:
                modelos_omitidos.append({"conjunto": conjunto, "modelo": nombre_hijo, "motivo": motivo})
                continue
            registros.extend(filas)
        conjuntos[conjunto] = registros
    documento = {
        "version": 1,
        "organizacion_id": int(organizacion_id),
        "unidad_negocio_id": int(unidad_negocio_id),
        "origen": "exportacion_controlada_sistema_fierro",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "modo": "respaldo_integral_solo_lectura_sin_secretos",
        "respaldo_reconstruible": not modelos_omitidos,
        "restauracion_automatica_habilitada": False,
        "conjuntos": conjuntos,
        "manifiesto": {
            nombre: {
                "registros": len(registros),
                "huella": hashlib.sha256(json.dumps(registros, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest(),
            }
            for nombre, registros in conjuntos.items()
        },
        "seguridad": {
            "campos_prohibidos": campos_omitidos,
            "modelos_omitidos": modelos_omitidos,
            "credenciales_incluidas": False,
            "tokens_incluidos": False,
        },
        "controles": {
            "escrituras": 0,
            "actualizaciones": 0,
            "eliminaciones": 0,
            "conexiones_externas": 0,
        },
    }
    base = json.dumps(documento, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    documento["huella_respaldo"] = hashlib.sha256(base).hexdigest()
    return documento


def exportar(documento):
    return io.BytesIO(json.dumps(documento, ensure_ascii=False, sort_keys=True, indent=2, default=str).encode("utf-8"))
