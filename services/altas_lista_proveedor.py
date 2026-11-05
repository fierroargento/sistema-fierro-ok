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
    if not codigo or len(codigo) > 120:
        raise ValueError('Alta: completá el código del artículo del proveedor (hasta 120 caracteres).')
    if not nombre or len(nombre) > 200:
        raise ValueError('Alta: completá Descripción (hasta 200 caracteres).')
    if not medida or len(medida) > 30:
        raise ValueError('Alta: completá Unidad de medida de consumo, por ejemplo kg, metro o unidad.')
    if tipo not in TIPOS:
        raise ValueError('Alta: Tipo debe ser materia_prima, consumible, servicio_productivo o embalaje_productivo.')
    if len(sku) > 80:
        raise ValueError('El SKU/código interno admite hasta 80 caracteres.')
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
