"""Actualización acotada del catálogo desde un CSV de Tiendanube, sin API."""
import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from io import StringIO
from itsdangerous import URLSafeTimedSerializer, BadSignature

COLUMNAS = {'peso_gr': 'Peso (kg)', 'alto_cm': 'Alto (cm)',
            'ancho_cm': 'Ancho (cm)', 'largo_cm': 'Profundidad (cm)'}
ETIQUETAS = {'peso_gr': 'Peso (g)', 'alto_cm': 'Alto (cm)',
             'ancho_cm': 'Ancho (cm)', 'largo_cm': 'Largo / profundidad (cm)'}
SALT = 'productos-logistica-tn-v1'


def leer(archivo):
    if not str(archivo.filename or '').lower().endswith('.csv'):
        raise ValueError('Elegí el archivo CSV exportado de Tiendanube, sin convertirlo.')
    contenido = archivo.read(4 * 1024 * 1024 + 1)
    if len(contenido) > 4 * 1024 * 1024:
        raise ValueError('El CSV supera 4 MB. Usá un archivo de hasta 500 filas.')
    try:
        texto = contenido.decode('utf-8-sig')
    except UnicodeDecodeError:
        try:
            texto = contenido.decode('cp1252')
        except UnicodeDecodeError:
            raise ValueError('No se pudo leer el texto del CSV. Exportalo de nuevo desde Tiendanube.') from None
    try:
        dialecto = csv.Sniffer().sniff(texto[:4096], delimiters=';\t,')
    except csv.Error:
        dialecto = None
    fuente = csv.reader(StringIO(texto, newline=''), dialecto) if dialecto else csv.reader(StringIO(texto, newline=''), delimiter=';')
    encabezados = next(fuente, [])
    requeridas = ['SKU', *COLUMNAS.values()]
    if any(encabezados.count(c) != 1 for c in requeridas):
        raise ValueError('El CSV debe tener una sola columna SKU, Peso (kg), Alto (cm), Ancho (cm) y Profundidad (cm). Usá la exportación de productos de Tiendanube.')
    indices = {c: encabezados.index(c) for c in requeridas}
    filas = []
    try:
        for valores in fuente:
            if not any(v.strip() for v in valores):
                continue
            if len(filas) >= 500:
                raise ValueError('El archivo supera 500 filas. Dividilo en archivos más pequeños.')
            filas.append({'numero': fuente.line_num, 'sku': (valores[indices['SKU']] if len(valores) > indices['SKU'] else '').strip().upper(),
                          'valores': {c: valores[i].strip() if len(valores) > i else '' for c, i in indices.items() if c != 'SKU'}})
    except csv.Error:
        raise ValueError('El CSV tiene una fila que no se puede leer. Exportalo de nuevo desde Tiendanube.') from None
    if not filas:
        raise ValueError('El archivo no contiene productos.')
    return filas


def _valores(entrada):
    datos, avisos = {}, []
    for campo, columna in COLUMNAS.items():
        texto = entrada['valores'][columna]
        if texto == '':
            avisos.append(columna + ': sin dato; se conserva Fierro')
            continue
        try:
            n = Decimal(texto.replace(',', '.'))
            if not n.is_finite() or n < 0:
                raise InvalidOperation()
            if n == 0:
                avisos.append(columna + ': cero en Tiendanube; se conserva Fierro')
                continue
            if campo == 'peso_gr':
                n *= 1000
            if n > Decimal('1000000000'):
                raise InvalidOperation()
        except InvalidOperation:
            raise ValueError(f'Columna «{columna}»: «{texto}» no es una medida válida. Corregí ese dato; no se importa este SKU.') from None
        datos[campo] = float(n)
    return datos, avisos


def _productos(Producto, session, org):
    # Usa el mismo catálogo; no carga recetas/costos para actualizar medidas.
    from services.producto_habilitaciones import esquema_ficha_disponible
    from models.producto_ficha_maestra import ProductoFichaMaestra
    productos = session.query(Producto).filter_by(organizacion_id=org).all()
    fichas = {}
    if esquema_ficha_disponible(session):
        fichas = {f.producto_id: f for f in session.query(ProductoFichaMaestra).filter_by(organizacion_id=org)}
    por_sku = defaultdict(list)
    for p in productos:
        por_sku[p.sku.strip().upper()].append(p)
    return por_sku, fichas


def previsualizar(filas, *, Producto, session, organizacion_id):
    por_sku, fichas = _productos(Producto, session, organizacion_id)
    grupos = defaultdict(list)
    for fila in filas:
        grupos[fila['sku']].append(fila)
    vista = []
    for sku, originales in grupos.items():
        f = {'sku': sku, 'filas': [r['numero'] for r in originales], 'accion': 'omitido',
             'motivo': '', 'avisos': [], 'cambios': [], 'producto_id': None, 'antes': {}, 'datos': {}}
        try:
            if not sku:
                raise ValueError('Falta SKU. Completalo en Tiendanube; no se adivina por nombre.')
            coincidencias = por_sku.get(sku, [])
            if not coincidencias:
                raise ValueError('SKU no encontrado en Fierro. Se omite; esta carga no crea productos.')
            if len(coincidencias) != 1:
                raise ValueError('Más de un producto en Fierro tiene este SKU. Revisá su identidad.')
            p = coincidencias[0]
            if fichas.get(p.id) and fichas[p.id].no_stockeable:
                raise ValueError('Producto No stockeable: no se cargan medidas de envío.')
            calculadas = [_valores(r) for r in originales]
            if any(c[0] != calculadas[0][0] for c in calculadas[1:]):
                raise ValueError('El SKU se repite con peso o dimensiones diferentes. No se eligió ninguna fila. Corregí el CSV.')
            datos, avisos = calculadas[0]
            if len(originales) > 1:
                avisos.append('SKU repetido con las mismas medidas: se toma una sola vez.')
            antes = {c: getattr(p, c) for c in COLUMNAS}
            cambios = [{'campo': ETIQUETAS[c], 'antes': antes[c], 'despues': v} for c, v in datos.items() if antes[c] != v]
            f.update(producto_id=p.id, antes=antes, datos=datos, avisos=avisos, cambios=cambios,
                     accion='actualizar' if cambios else 'sin_cambios')
            if not datos:
                f.update(accion='omitido', motivo='No hay peso ni dimensiones mayores que cero. Se conserva Fierro.')
        except ValueError as error:
            f['motivo'] = str(error)
        vista.append(f)
    return vista


def firmar(vista, org, usuario, secreto):
    return URLSafeTimedSerializer(secreto, salt=SALT).dumps({'org': org, 'usuario': usuario, 'filas': vista})


def aplicar(token, *, Producto, session, organizacion_id, usuario_id, secreto):
    if len(token) > 1000000:
        raise ValueError('La revisión supera el tamaño permitido.')
    try:
        lote = URLSafeTimedSerializer(secreto, salt=SALT).loads(token, max_age=900)
    except BadSignature:
        raise ValueError('La revisión venció o fue modificada. Volvé a subir el CSV.') from None
    if lote['org'] != organizacion_id or lote['usuario'] != usuario_id:
        raise ValueError('La revisión pertenece a otro usuario u organización.')
    filas = [f for f in lote['filas'] if f['accion'] in ('actualizar', 'sin_cambios')]
    if not any(f['accion'] == 'actualizar' for f in filas):
        raise ValueError('No hay medidas para actualizar.')
    try:
        ids = [f['producto_id'] for f in filas]
        productos = {p.id: p for p in session.query(Producto).filter(
            Producto.organizacion_id == organizacion_id, Producto.id.in_(ids)).order_by(Producto.id).with_for_update().populate_existing()}
        from services.producto_habilitaciones import esquema_ficha_disponible
        from models.producto_ficha_maestra import ProductoFichaMaestra
        fichas = {}
        if esquema_ficha_disponible(session):
            fichas = {f.producto_id: f for f in session.query(ProductoFichaMaestra).filter(
                ProductoFichaMaestra.organizacion_id == organizacion_id,
                ProductoFichaMaestra.producto_id.in_(ids)).order_by(ProductoFichaMaestra.producto_id).with_for_update().populate_existing()}
        # Valida todas las filas antes de escribir la primera.
        for f in filas:
            p = productos.get(f['producto_id'])
            if p is None or p.sku.strip().upper() != f['sku'] or any(getattr(p, c) != f['antes'][c] for c in COLUMNAS):
                raise ValueError(f'{f["sku"]}: cambiaron sus medidas desde la revisión. Volvé a subir el CSV. No se guardó nada.')
            if fichas.get(p.id) and fichas[p.id].no_stockeable:
                raise ValueError(f'{f["sku"]}: ahora es No stockeable. Volvé a revisar; no se guardó nada.')
        for f in filas:
            if f['accion'] == 'actualizar':
                for c, v in f['datos'].items():
                    if c not in COLUMNAS or not 0 < v <= 1000000000:
                        raise ValueError('Medidas inválidas; volvé a revisar el CSV.')
                    setattr(productos[f['producto_id']], c, v)
        session.commit()
        return sum(f['accion'] == 'actualizar' for f in filas)
    except Exception:
        session.rollback()
        raise
