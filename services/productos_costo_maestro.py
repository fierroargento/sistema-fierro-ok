"""Entrada del costo manual desde el maestro; reutiliza versiones de Costos."""
from decimal import Decimal, InvalidOperation
import re


def _decimal(valor, nombre, maximo, decimales):
    texto = str('' if valor is None else valor).strip().replace(',', '.')
    if not texto:
        return None
    if len(texto)>30:
        raise ValueError(f'{nombre}: el número es demasiado largo.')
    if not re.fullmatch(r'(?:\d+(?:\.\d+)?|\.\d+)', texto):
        raise ValueError(f'{nombre}: usá un número sin separadores de miles.')
    try:
        numero = Decimal(texto)
        if (not numero.is_finite() or numero < 0 or numero > maximo
                or numero != numero.quantize(Decimal(1).scaleb(-decimales))):
            raise ValueError(f'{nombre}: valor fuera de rango o con más de {decimales} decimales.')
    except InvalidOperation as error:
        raise ValueError(f'{nombre}: el número no es válido.') from error
    return numero


def leer_costo_manual(formulario):
    # Clientes anteriores conservan el costo; un campo ausente no significa borrar.
    if formulario.get('costo_maestro_presentado') != '1':
        return {'costo_presentado': False}
    from services.costos_productos import normalizar_moneda
    moneda = normalizar_moneda(formulario.get('moneda_costo', 'ARS'))
    if moneda not in {'ARS', 'USD'}:
        raise ValueError('Elegí Pesos (ARS) o Dólares (USD) para el costo.')
    precio = _decimal(formulario.get('precio_costo'), 'Precio de costo', Decimal('999999999999.99'), 2)
    iva = _decimal(formulario.get('iva_pct'), 'IVA', Decimal('100'), 6)
    return {'costo_presentado':True, 'precio_costo_centavos':None if precio is None else int(precio * 100),
            'moneda_costo':moneda, 'iva_pct':iva}


def _modelos():
    from models.costo_producto_version import CostoProductoVersion
    from models.costo_producto_detalle import CostoProductoDetalle
    from models.usuario_sistema import UsuarioSistema
    return CostoProductoVersion, CostoProductoDetalle


def cargar_costos_manuales(salida, db_session, organizacion_id):
    Modelo, _ = _modelos()
    ids = [d['costo_carga_id'] for d in salida.values() if d.get('costo_carga_id')]
    versiones = db_session.query(Modelo).filter(Modelo.id.in_(ids),Modelo.organizacion_id==organizacion_id,
        Modelo.producto_id.in_(salida),Modelo.unidad_negocio_id.is_(None),Modelo.tipo=='manual').populate_existing().all() if ids else []
    por_id = {v.id:v for v in versiones}
    for producto_id, datos in salida.items():
        datos['precio_costo'] = ''
        version = por_id.get(datos.get('costo_carga_id'))
        if version is not None and version.producto_id == producto_id:
            datos.update(precio_costo=format(Decimal(version.costo_total_centavos)/100, '.2f'),
                moneda_costo=version.moneda, costo_estado=version.estado,
                costo_version_numero=version.numero_version)


def guardar_costo_manual(producto, general, datos, db_session, *, usuario=None):
    if not datos.get('costo_presentado'):
        return
    Modelo, Detalle = _modelos()
    anterior = None
    if general.costo_carga_id:
        anterior = db_session.query(Modelo).filter_by(id=general.costo_carga_id,
            organizacion_id=producto.organizacion_id,producto_id=producto.id,unidad_negocio_id=None,tipo='manual').first()
        if anterior is None:
            raise ValueError('El costo vinculado no corresponde al producto. Revisá su historial de costos.')
    importe = datos['precio_costo_centavos']
    general.moneda_costo = datos['moneda_costo']
    general.iva_pct = datos['iva_pct']
    if importe is None:
        # Quita la referencia de la ficha, nunca borra una versión histórica.
        general.costo_carga_id = None
        return
    if anterior is not None and (anterior.costo_total_centavos,anterior.moneda)==(importe,datos['moneda_costo']):
        return
    from services.costos_productos import crear_version_costo
    from models.organizacion import Organizacion
    from models.unidad_negocio import UnidadNegocio
    from models.producto import Producto
    from models.producto_ficha_maestra import ProductoFichaMaestra
    ficha = db_session.query(ProductoFichaMaestra).filter_by(producto_id=producto.id,
        organizacion_id=producto.organizacion_id).one()
    # El mismo perfil general permite encontrar la carga desde Costos.
    # No se cambia ni reactiva un perfil existente ni una ficha de producción.
    from models.perfil_costeo_producto import PerfilCosteoProducto
    perfil = db_session.query(PerfilCosteoProducto).filter_by(organizacion_id=producto.organizacion_id,
        producto_id=producto.id,unidad_negocio_id=None).first()
    if perfil is None and ficha.tipo == 'simple':
        from services.perfiles_costeo import crear_o_actualizar_perfil
        crear_o_actualizar_perfil(organizacion_id=producto.organizacion_id,unidad_negocio_id=None,
            producto_id=producto.id,tipo=ficha.tipo,PerfilCosteoProducto=PerfilCosteoProducto,
            UnidadNegocio=UnidadNegocio,Producto=Producto,db_session=db_session,commit=False)
    version = crear_version_costo(organizacion_id=producto.organizacion_id,
        unidad_negocio_id=None, producto_id=producto.id, moneda=datos['moneda_costo'],tipo='manual',
        detalles=[{'tipo':'insumo','codigo':producto.sku,'concepto':'Costo unitario cargado en maestro (sin IVA)',
            'cantidad':1,'unidad_medida':ficha.unidad_medida,'costo_unitario_centavos':importe,'porcentaje_merma':0,'orden':0}],
        creado_por_username=getattr(usuario,'username',None),
        observacion='Carga manual desde Base de Datos / Productos. Importe sin IVA; no sustituye una composición calculada.',
        Organizacion=Organizacion,UnidadNegocio=UnidadNegocio,Producto=Producto,
        CostoProductoVersion=Modelo,CostoProductoDetalle=Detalle,db_session=db_session,commit=False)
    general.costo_carga_id=version.id
