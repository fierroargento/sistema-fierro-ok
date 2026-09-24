"""Paquete reproducible de datos sintéticos para UAT desconectada."""

import csv
import hashlib
import io
import json
import zipfile

from PIL import Image, ImageDraw


ARCHIVOS_CSV = {
    "01_inclusiones_catalogo.csv": (
        ["CATALOGO", "SKU", "DESCRIPCION", "SKU COMERCIAL", "NOMBRE COMERCIAL", "MARCA", "CATEGORIA"],
        [["catalogo-uat", "UAT-PROD-001", "Producto sintético UAT", "UAT-PROD-001", "Producto sintético UAT", "Marca UAT", "Ensayo"]],
    ),
    "02_clasificacion_productos.csv": (
        ["SKU", "TIPO", "OBSERVACION"],
        [["UAT-PROD-001", "produccion", "Clasificación sintética para ensayo aislado"]],
    ),
    "03_insumos.csv": (
        ["CODIGO", "NOMBRE", "TIPO", "UNIDAD DE MEDIDA", "PRECIO UNITARIO", "PROVEEDOR"],
        [["UAT-INS-001", "Chapa sintética UAT", "materia_prima", "kg", "1500", "Proveedor sintético UAT"]],
    ),
    "04_empleados.csv": (
        ["CODIGO O LEGAJO", "NOMBRE", "SECTOR", "PUESTO", "UBICACION DE TRABAJO", "TIPO DE FUNCION", "PARTICIPACION PRODUCTIVA %", "SUELDO BASE", "EXCEPCION CARGAS %", "ADICIONALES", "OTROS COSTOS", "HORAS MENSUALES", "HORAS PRODUCTIVAS"],
        [["UAT-EMP-001", "Operario sintético UAT", "Producción", "Operario", "Taller UAT", "directa", "100", "1000000", "", "0", "0", "176", "160"]],
    ),
    "05_maquinas.csv": (
        ["CODIGO", "NOMBRE", "CATEGORIA", "VALOR DE ADQUISICION", "VALOR RESIDUAL", "VIDA UTIL EN HORAS", "POTENCIA KW", "FACTOR DE CARGA %", "COSTO POR KWH", "MANTENIMIENTO MENSUAL", "OTROS COSTOS MENSUALES", "HORAS PRODUCTIVAS MENSUALES"],
        [["UAT-MAQ-001", "Máquina sintética UAT", "Corte", "1000000", "100000", "10000", "2.5", "80", "150", "20000", "5000", "120"]],
    ),
    "06_costos_fijos.csv": (
        ["CODIGO", "NOMBRE", "CATEGORIA", "INTEGRA PRODUCCION", "CRITERIO DE DISTRIBUCION", "NATURALEZA", "PERIODICIDAD", "IMPORTE DEL PERIODO", "MESES QUE CUBRE", "COMPROBANTE"],
        [["UAT-CF-001", "Costo fijo sintético UAT", "Ensayo", "si", "porcentaje", "fijo", "mensual", "120000", "", "UAT-SIN-EFECTO"]],
    ),
    "07_fichas_tecnicas.csv": (
        ["SKU PRODUCTO", "TIPO DE LINEA", "CODIGO DEL RECURSO", "CANTIDAD", "MERMA %", "OPERACION", "MINUTOS", "ASIGNACION %", "UNIDADES MENSUALES"],
        [
            ["UAT-PROD-001", "insumo", "UAT-INS-001", "2", "5", "", "", "", ""],
            ["UAT-PROD-001", "operacion", "UAT-EMP-001", "", "", "Soldadura UAT", "15", "", ""],
            ["UAT-PROD-001", "maquina", "UAT-MAQ-001", "", "", "Corte UAT", "10", "", ""],
            ["UAT-PROD-001", "costo fijo", "UAT-CF-001", "", "", "", "", "10", "100"],
        ],
    ),
    "08_proveedores.csv": (
        ["CODIGO", "RAZON SOCIAL", "CUIT", "EMAIL", "TELEFONO", "ESTADO", "OBSERVACION"],
        [["UAT-PROV-001", "Proveedor sintético UAT SA", "30-70000000-1", "uat-proveedor@example.invalid", "+54 9 11 0000 0000", "activo", "Dato ficticio; no contactar"]],
    ),
}


def _csv_bytes(encabezados, filas):
    salida = io.StringIO(newline="")
    escritor = csv.writer(salida, lineterminator="\n")
    escritor.writerow(encabezados)
    escritor.writerows(filas)
    return salida.getvalue().encode("utf-8-sig")


def _imagen_png():
    salida = io.BytesIO()
    imagen = Image.new("RGB", (1200, 1200), "#176b89")
    dibujo = ImageDraw.Draw(imagen)
    dibujo.rectangle((90, 90, 1110, 1110), outline="white", width=18)
    dibujo.text((420, 550), "UAT 001", fill="white")
    imagen.save(salida, format="PNG", optimize=True)
    return salida.getvalue()


def _readme():
    return """PAQUETE DE DATOS SINTETICOS UAT - SISTEMA FIERRO

Este paquete contiene únicamente datos ficticios. No autoriza despliegues,
integraciones, publicaciones, movimientos de stock, cobros, pagos ni contactos.

Precondiciones obligatorias:
1. Staging separado y certificado con el preflight aprobado.
2. MODO_LABORATORIO_DESCONECTADO=true.
3. Conexiones, efectos, webhooks y scheduler en false.
4. Organización y unidad exclusivas de ensayo.
5. Crear manualmente un catálogo desactivado con código: catalogo-uat.

Orden de prueba desde la interfaz:
1. Importar 01_inclusiones_catalogo.csv en Inclusiones de catálogo.
2. Importar 02_clasificacion_productos.csv en Productos y clasificación.
3. Importar 03_insumos.csv, 04_empleados.csv, 05_maquinas.csv y
   06_costos_fijos.csv desde Fuentes de costo.
4. Importar 07_fichas_tecnicas.csv desde Fichas técnicas.
5. Importar 08_proveedores.csv desde Compras > Importar proveedores.
6. Abrir la ficha UAT-PROD-001, seleccionar 09_imagen_producto_uat.png y
   verificar la vista previa antes de guardar.
7. Mantener catálogo, producto, costos e integraciones sin activar.

Resultado esperado:
- Todos los lotes quedan limitados al tenant/unidad UAT.
- La segunda carga idéntica resulta sin cambios o idempotente.
- La imagen queda en almacenamiento local aislado.
- No se consulta ni modifica ningún sistema externo.
"""


def construir_paquete_uat():
    archivos = {
        nombre: _csv_bytes(encabezados, filas)
        for nombre, (encabezados, filas) in ARCHIVOS_CSV.items()
    }
    archivos["09_imagen_producto_uat.png"] = _imagen_png()
    archivos["LEEME_PRIMERO.txt"] = _readme().encode("utf-8")
    manifiesto = {
        "version": 1,
        "modo": "paquete_datos_sinteticos_uat_desconectada",
        "datos_reales": False,
        "autoriza_activacion": False,
        "autoriza_conexiones": False,
        "archivos": [
            {
                "nombre": nombre,
                "bytes": len(contenido),
                "sha256": hashlib.sha256(contenido).hexdigest(),
            }
            for nombre, contenido in sorted(archivos.items())
        ],
    }
    archivos["MANIFIESTO.json"] = json.dumps(
        manifiesto, ensure_ascii=False, sort_keys=True, indent=2,
    ).encode("utf-8")
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", compression=zipfile.ZIP_DEFLATED) as paquete:
        for nombre, contenido in sorted(archivos.items()):
            entrada = zipfile.ZipInfo(nombre, date_time=(2026, 1, 1, 0, 0, 0))
            entrada.compress_type = zipfile.ZIP_DEFLATED
            entrada.create_system = 3
            entrada.external_attr = 0o100644 << 16
            paquete.writestr(entrada, contenido)
    salida.seek(0)
    return salida
