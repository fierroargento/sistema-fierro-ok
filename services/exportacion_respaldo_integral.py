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
    if "organizacion_id" not in nombres:
        return [], "modelo_sin_identidad_tenant"
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
        conjuntos[conjunto] = registros
    documento = {
        "version": 1,
        "organizacion_id": int(organizacion_id),
        "unidad_negocio_id": int(unidad_negocio_id),
        "origen": "exportacion_controlada_sistema_fierro",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "modo": "respaldo_integral_solo_lectura_sin_secretos",
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
