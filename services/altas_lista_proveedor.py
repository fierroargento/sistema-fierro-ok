"""Altas explícitas revisadas desde la lista; no escribe durante la revisión."""
from hashlib import sha256

METADATOS = ('descripcion', 'unidad_medida', 'tipo')
TIPOS = {'materia_prima', 'consumible', 'servicio_productivo', 'embalaje_productivo'}


def unidad(valor):
    texto = str(valor or '').strip().lower()
    return {'kilogramo':'kg','kilogramos':'kg','kgs':'kg','m':'metro','metros':'metro',
            'unidades':'unidad','u':'unidad','m²':'m2','litros':'litro','l':'litro'}.get(texto, texto)


def datos(valores, proveedor_id):
    codigo = str(valores.get('codigo_proveedor') or '').strip()
    nombre = str(valores.get('descripcion') or '').strip()
    medida = unidad(valores.get('unidad_medida'))
    tipo = str(valores.get('tipo') or '').strip().lower().replace(' ', '_')
    sku = str(valores.get('sku') or '').strip()
    errores = []
    if not codigo or len(codigo) > 120:
        errores.append('Alta: completá el código del artículo del proveedor (hasta 120 caracteres).')
    if not nombre or len(nombre) > 200:
        errores.append('Alta: completá Descripción (hasta 200 caracteres).')
    if not medida or len(medida) > 30:
        errores.append('Alta: completá Unidad de medida de consumo, por ejemplo kg, metro o unidad.')
    if tipo not in TIPOS:
        errores.append('Alta: Tipo debe ser materia_prima, consumible, servicio_productivo o embalaje_productivo.')
    if len(sku) > 80:
        errores.append('El SKU/código interno admite hasta 80 caracteres.')
    if errores:
        raise ValueError('\n'.join(errores))
    interno = sku or 'LP-' + str(proveedor_id) + '-' + sha256(codigo.upper().encode()).hexdigest()[:16].upper()
    return dict(codigo=interno.lower(),nombre=nombre,unidad_medida=medida,tipo=tipo)


def preparar(valores, proveedor_id, org, session):
    from sqlalchemy import func
    from models.fuentes_costo_productivo import InsumoProductivo as I
    alta = datos(valores, proveedor_id)
    if session.query(I.id).filter(I.organizacion_id==org,func.upper(I.codigo)==alta['codigo'].upper()).first():
        raise ValueError('Ese código interno ya existe. Vinculá el material existente en esta unidad antes de importar.')
    if session.query(I.id).filter(I.organizacion_id==org,func.lower(I.nombre)==alta['nombre'].lower()).first():
        raise ValueError('Ya existe un material con esa descripción. Vinculalo al código del proveedor para evitar duplicados.')
    return alta


def guardar(alta, org, unidad_id, session):
    from models.organizacion import Organizacion
    from models.unidad_negocio import UnidadNegocio
    from models.fuentes_costo_productivo import InsumoProductivo
    from services.fuentes_costo_productivo import crear_insumo
    return crear_insumo(organizacion_id=org,unidad_negocio_id=unidad_id,
        **alta,Organizacion=Organizacion,UnidadNegocio=UnidadNegocio,
        InsumoProductivo=InsumoProductivo,db_session=session,commit=False)


def errores_entrada(valores, proveedor_id):
    """Informa juntos los campos pendientes antes de consultar identidades."""
    errores=[]
    try:datos(valores,proveedor_id)
    except ValueError as exc:errores.extend(str(exc).splitlines())
    for campo,etiqueta in [('precio_proveedor','Precio proveedor sin IVA'),('base_precio','Cotización proveedor (unitario o bulto)'),('moneda_proveedor','Moneda proveedor (ARS o USD)')]:
        if not str(valores.get(campo) or '').strip():errores.append('Completá '+etiqueta+'.')
    base=str(valores.get('base_precio') or '').strip().lower()
    if base and base not in {'unitario','bulto'}:errores.append('Cotización proveedor debe ser unitario o bulto.')
    moneda=str(valores.get('moneda_proveedor') or '').strip().upper()
    if moneda and moneda not in {'ARS','USD'}:errores.append('Moneda proveedor debe ser ARS o USD.')
    if base=='bulto' and not str(valores.get('cantidad_bulto') or '').strip():errores.append('Completá Cantidad por bulto en unidades de consumo.')
    return errores
