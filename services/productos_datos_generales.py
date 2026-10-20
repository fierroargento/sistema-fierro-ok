"""Carga manual completa y atómica del maestro, sin conexiones externas."""
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO
import json
import re
import warnings
from sqlalchemy import inspect, select

MAX_IMAGENES = 5
MAX_IMAGEN_BYTES = 2 * 1024 * 1024


def esquema_datos_disponible(db_session):
    from models.producto_datos_generales import TABLAS_DATOS_PRODUCTO
    inspector = inspect(db_session.connection())
    return all(inspector.has_table(t.name) and set(t.c.keys()) <= {c['name'] for c in inspector.get_columns(t.name)} for t in TABLAS_DATOS_PRODUCTO)


def _json(formulario, nombre, defecto):
    try:
        valor = json.loads(formulario.get(nombre, json.dumps(defecto)))
    except (TypeError, ValueError) as error:
        raise ValueError(f'Revisá {nombre.replace("_", " ")}.') from error
    if not isinstance(valor, type(defecto)):
        raise ValueError(f'Revisá {nombre.replace("_", " ")}.')
    return valor


def _texto(valor, nombre, limite):
    valor = ' '.join(str(valor or '').strip().split())
    if len(valor) > limite:
        raise ValueError(f'{nombre} admite hasta {limite} caracteres.')
    return valor


def _ids(valores, nombre):
    if len(valores) > 300:
        raise ValueError(f'Demasiadas selecciones en {nombre}.')
    salida = []
    for valor in valores:
        if isinstance(valor, bool) or not str(valor).isdigit() or int(valor) <= 0:
            raise ValueError(f'La selección de {nombre} no es válida.')
        salida.append(int(valor))
    if len(set(salida)) != len(salida):
        raise ValueError(f'Hay elementos repetidos en {nombre}.')
    return salida


def leer_formulario_completo(formulario, archivos):
    if formulario.get('datos_generales_presentados') != '1':
        return None
    datos = {c: _texto(formulario.get(c), c, 120) for c in ('rubro', 'subrubro', 'marca')}
    if datos['subrubro'] and not datos['rubro']:
        raise ValueError('Elegí un rubro antes de completar el subrubro.')
    base = formulario.get('utilidad_base', 'costo')
    if base not in {'costo', 'precio_venta'}:
        raise ValueError('Elegí utilidad sobre costo o sobre precio de venta.')
    datos['utilidad_base'] = base
    porcentaje = str(formulario.get('utilidad_pct', '')).strip().replace(',', '.')
    datos['utilidad_pct'] = None
    if porcentaje:
        try:
            numero = Decimal(porcentaje)
        except InvalidOperation as error:
            raise ValueError('El porcentaje de utilidad no es válido.') from error
        if not numero.is_finite() or numero < 0 or numero > Decimal('999999.999999') or (base == 'precio_venta' and numero >= 100) or numero != numero.quantize(Decimal('0.000001')):
            raise ValueError('Usá una utilidad positiva o cero, con hasta seis decimales; sobre precio de venta debe ser menor al 100%.')
        datos['utilidad_pct'] = numero
    from services.productos_costo_maestro import leer_costo_manual
    datos.update(leer_costo_manual(formulario))
    proveedores = _json(formulario, 'proveedores_json', [])
    if len(proveedores) > 20:
        raise ValueError('El producto admite hasta 20 proveedores.')
    datos['proveedores'] = []
    for fila in proveedores:
        if not isinstance(fila, dict):
            raise ValueError('Revisá los proveedores del producto.')
        proveedor = _ids([fila.get('proveedor_id')], 'proveedores')[0]
        codigo = _texto(fila.get('codigo'), 'Código del proveedor', 120)
        if len(codigo.upper()) > 120:
            raise ValueError('El código normalizado del proveedor supera 120 caracteres.')
        datos['proveedores'].append({'proveedor_id':proveedor, 'codigo':codigo})
    if len({p['proveedor_id'] for p in datos['proveedores']}) != len(proveedores):
        raise ValueError('El proveedor está repetido. Conservá una sola fila por proveedor.')
    for tipo in ('sucursales', 'depositos'):
        campo_definido = tipo + ('_definidos' if tipo == 'depositos' else '_definidas')
        datos[campo_definido] = formulario.get(campo_definido) == '1'
        datos[tipo] = _ids(_json(formulario, tipo + '_json', []), tipo)
        if not datos[campo_definido]:
            datos[tipo] = []
    barras = _json(formulario, 'codigos_barras_json', [])
    if len(barras) > 20:
        raise ValueError('El producto admite hasta 20 códigos de barras.')
    datos['codigos_barras'] = []
    for codigo in barras:
        if not isinstance(codigo, str) or not codigo.strip() or len(codigo.strip()) > 80 or re.search(r'\s|[\x00-\x1f\x7f]', codigo.strip()):
            raise ValueError('Cada código de barras debe tener entre 1 y 80 caracteres, sin espacios.')
        datos['codigos_barras'].append(codigo.strip())
    if len(set(datos['codigos_barras'])) != len(datos['codigos_barras']):
        raise ValueError('Hay códigos de barras repetidos.')
    datos['imagenes_conservar'] = _ids(_json(formulario, 'imagenes_conservar_json', []), 'imágenes')
    datos['imagen_principal'] = str(formulario.get('imagen_principal', '')).strip()
    validos = [f for f in archivos if getattr(f, 'filename', '')]
    if len(validos) + len(datos['imagenes_conservar']) > MAX_IMAGENES:
        raise ValueError('El producto admite hasta 5 imágenes en total.')
    # Misma validación de imágenes que la ficha comercial existente.
    from services.catalogo_ficha_integral import prevalidar_imagenes
    prevalidar_imagenes(validos, max_imagenes=MAX_IMAGENES)
    from PIL import Image
    datos['imagenes_nuevas'] = []
    for archivo in validos:
        contenido = archivo.read(MAX_IMAGEN_BYTES + 1); archivo.stream.seek(0)
        if not contenido or len(contenido) > MAX_IMAGEN_BYTES:
            raise ValueError('Cada imagen debe pesar como máximo 2 MB.')
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(contenido)) as imagen:
                formato, (ancho, alto) = imagen.format, imagen.size
        if formato not in {'JPEG', 'PNG', 'WEBP'} or ancho * alto > 25000000 or max(ancho, alto) > 10000:
            raise ValueError('Usá imágenes JPG, PNG o WEBP de hasta 25 megapíxeles y 10.000 píxeles por lado.')
        datos['imagenes_nuevas'].append({'nombre':str(archivo.filename).replace('\\', '/').rsplit('/', 1)[-1][:180],
            'mime': {'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp'}[formato],
            'contenido':contenido,'sha256':sha256(contenido).hexdigest(),'ancho':ancho,'alto':alto})
    return datos


def cargar_datos_productos(productos, db_session, organizacion_id):
    if not productos or not esquema_datos_disponible(db_session):
        return {}
    from models.producto_datos_generales import ProductoDatosGenerales as General, ProductoProveedor as Proveedor, ProductoUbicacion as Ubicacion, ProductoCodigoBarras as Barras, ProductoImagenMaestra as Imagen
    ids = [p.id for p in productos]
    salida = {}
    for general in db_session.query(General).filter(General.organizacion_id==organizacion_id, General.producto_id.in_(ids)).populate_existing():
        salida[general.producto_id] = {c:getattr(general,c) for c in ('rubro','subrubro','marca','costo_carga_id','moneda_costo','utilidad_base','sucursales_definidas','depositos_definidos','revision')}
        salida[general.producto_id].update(iva_pct=str(general.iva_pct) if general.iva_pct is not None else '', utilidad_pct=str(general.utilidad_pct) if general.utilidad_pct is not None else '', proveedores=[],sucursales=[],depositos=[],codigos_barras=[],imagenes=[])
    from services.productos_costo_maestro import cargar_costos_manuales
    cargar_costos_manuales(salida, db_session, organizacion_id)
    for modelo, clave in ((Proveedor,'proveedores'),(Ubicacion,'ubicaciones'),(Barras,'codigos_barras'),(Imagen,'imagenes')):
        for registro in db_session.query(modelo).filter(modelo.organizacion_id==organizacion_id,modelo.producto_id.in_(ids)).order_by(modelo.id).populate_existing():
            d = salida.get(registro.producto_id)
            if d is None: continue
            if clave=='proveedores': d[clave].append({'proveedor_id':registro.proveedor_id,'codigo':registro.codigo})
            elif clave=='ubicaciones': d['sucursales' if registro.tipo=='sucursal' else 'depositos'].append(registro.sucursal_operativa_id)
            elif clave=='codigos_barras': d[clave].append(registro.codigo)
            else: d[clave].append({'id':registro.id,'nombre':registro.nombre,'principal':registro.principal,'sha256':registro.sha256,
                'url':f'/admin/productos/{registro.producto_id}/imagenes/{registro.id}'})
    return salida


def guardar_datos_generales(producto, datos, db_session, *, usuario=None):
    if datos is None: return
    if not esquema_datos_disponible(db_session):
        raise ValueError('Falta preparar la ficha completa de productos en staging. No se guardó ningún cambio.')
    from models.producto_datos_generales import ProductoDatosGenerales as General, ProductoProveedor as Proveedor, ProductoUbicacion as Ubicacion, ProductoCodigoBarras as Barras, ProductoImagenMaestra as Imagen
    from models.compras import ProveedorCompra
    from models.sucursal_operativa import SucursalOperativa
    org = producto.organizacion_id
    for fila in datos['proveedores']:
        anterior = db_session.query(Proveedor).filter_by(organizacion_id=org,producto_id=producto.id,proveedor_id=fila['proveedor_id']).first()
        proveedor = db_session.query(ProveedorCompra).filter_by(id=fila['proveedor_id'],organizacion_id=org).first()
        if proveedor is None or (proveedor.estado!='activo' and anterior is None):
            raise ValueError('Seleccioná proveedores activos de la organización actual.')
        clave = fila['codigo'].upper() or None
        if clave and db_session.query(Proveedor).filter(Proveedor.organizacion_id==org,Proveedor.proveedor_id==proveedor.id,
                Proveedor.codigo_clave==clave,Proveedor.producto_id!=producto.id).first():
            raise ValueError(f'El código {fila["codigo"]} ya identifica otro producto de {proveedor.razon_social}.')
    for nombre,tipo in (('sucursales','sucursal'),('depositos','deposito')):
        previas = set(db_session.scalars(select(Ubicacion.sucursal_operativa_id).where(Ubicacion.organizacion_id==org,Ubicacion.producto_id==producto.id,Ubicacion.tipo==tipo)))
        for ident in datos[nombre]:
            ubicacion = db_session.query(SucursalOperativa).filter_by(id=ident,organizacion_id=org).first()
            if ubicacion is None or (not ubicacion.activa and ident not in previas):
                raise ValueError('Seleccioná ubicaciones operativas activas de la organización actual.')
        if nombre=='depositos' and datos['depositos_definidos']:
            tabla=producto.metadata.tables.get('existencia_sucursal')
            if tabla is not None and inspect(db_session.connection()).has_table(tabla.name):
                pendientes=select(tabla.c.id).where(tabla.c.organizacion_id==org,tabla.c.producto_id==producto.id,
                    tabla.c.sucursal_operativa_id.not_in(datos[nombre]),
                    (tabla.c.stock_actual!=0)|(tabla.c.stock_reservado!=0)|(tabla.c.stock_bloqueado!=0)|(tabla.c.stock_transito!=0))
                if db_session.execute(pendientes.limit(1)).first():
                    raise ValueError('No podés quitar un depósito con saldo o compromisos pendientes. Regularizalo primero.')
    for codigo in datos['codigos_barras']:
        if db_session.query(Barras).filter(Barras.organizacion_id==org,Barras.codigo==codigo,Barras.producto_id!=producto.id).first():
            raise ValueError(f'El código de barras {codigo} ya pertenece a otro producto.')
    imagenes = db_session.query(Imagen).filter_by(organizacion_id=org,producto_id=producto.id).order_by(Imagen.id).all()
    por_id = {i.id:i for i in imagenes}
    if not set(datos['imagenes_conservar']) <= set(por_id):
        raise ValueError('La selección de imágenes no pertenece al producto. Volvé a abrir su ficha.')
    firmas = [por_id[i].sha256 for i in datos['imagenes_conservar']] + [i['sha256'] for i in datos['imagenes_nuevas']]
    if len(firmas)!=len(set(firmas)):
        raise ValueError('Hay imágenes repetidas. Conservá una sola copia de cada foto.')
    candidatos = [str(i) for i in datos['imagenes_conservar']] + [f'nueva:{i}' for i in range(len(datos['imagenes_nuevas']))]
    principal = datos['imagen_principal'] or (candidatos[0] if candidatos else '')
    if principal and principal not in candidatos:
        raise ValueError('Elegí una imagen principal entre las fotos conservadas o nuevas.')
    general = db_session.query(General).filter_by(producto_id=producto.id,organizacion_id=org).first()
    if general is None:
        general=General(producto_id=producto.id,organizacion_id=org,revision=1);db_session.add(general)
    else: general.revision+=1
    from services.productos_costo_maestro import guardar_costo_manual
    guardar_costo_manual(producto, general, datos, db_session, usuario=usuario)
    for campo in ('rubro','subrubro','marca','utilidad_pct','utilidad_base','sucursales_definidas','depositos_definidos'):
        setattr(general,campo,datos[campo])
    for modelo in (Proveedor,Ubicacion,Barras):
        db_session.query(modelo).filter_by(organizacion_id=org,producto_id=producto.id).delete(synchronize_session=False)
    db_session.flush()
    for n,fila in enumerate(datos['proveedores']):
        db_session.add(Proveedor(organizacion_id=org,producto_id=producto.id,**fila,codigo_clave=fila['codigo'].upper() or None,principal=n==0))
    for nombre,tipo in (('sucursales','sucursal'),('depositos','deposito')):
        for ident in datos[nombre]: db_session.add(Ubicacion(organizacion_id=org,producto_id=producto.id,sucursal_operativa_id=ident,tipo=tipo))
    for codigo in datos['codigos_barras']: db_session.add(Barras(organizacion_id=org,producto_id=producto.id,codigo=codigo))
    for imagen in imagenes:
        if imagen.id not in datos['imagenes_conservar']: db_session.delete(imagen)
        else: imagen.principal=str(imagen.id)==principal
    db_session.flush()
    for n,imagen in enumerate(datos['imagenes_nuevas']):
        db_session.add(Imagen(organizacion_id=org,producto_id=producto.id,**imagen,principal=principal==f'nueva:{n}'))
    db_session.flush()


def exigir_ubicacion_producto(producto, ubicacion_id, tipo, db_session):
    if not esquema_datos_disponible(db_session): return
    from models.producto_datos_generales import ProductoDatosGenerales as General, ProductoUbicacion as Ubicacion
    general=db_session.query(General).filter_by(producto_id=producto.id,organizacion_id=producto.organizacion_id).first()
    if general is None or not getattr(general,'depositos_definidos' if tipo=='deposito' else 'sucursales_definidas'): return
    if not db_session.query(Ubicacion.id).filter_by(producto_id=producto.id,organizacion_id=producto.organizacion_id,sucursal_operativa_id=ubicacion_id,tipo=tipo).first():
        raise ValueError(f'{producto.sku}: la ubicación no está habilitada como {tipo} en Base de Datos → Productos.')
