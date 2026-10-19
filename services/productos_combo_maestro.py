"""Composición del maestro sobre los perfiles y componentes de Costos existentes."""
from decimal import Decimal, InvalidOperation
from sqlalchemy import inspect, func


def normalizar_componentes(valor):
    if isinstance(valor, str):
        if len(valor) > 20000:
            raise ValueError('La composición supera el tamaño permitido.')
        filas = []
        for parte in valor.split('|'):
            if not parte.strip():
                continue
            if '=' not in parte:
                raise ValueError('Componentes combo: usá SKU=2|OTRO-SKU=1.')
            sku, cantidad = parte.rsplit('=', 1)
            filas.append({'sku': sku, 'cantidad': cantidad})
    elif isinstance(valor, list):
        filas = valor
    else:
        raise ValueError('La composición del combo no es válida.')
    if len(filas) > 100:
        raise ValueError('El combo admite hasta 100 componentes distintos.')
    salida, vistos = [], set()
    for fila in filas:
        if not isinstance(fila, dict):
            raise ValueError('La composición del combo no es válida.')
        sku = str(fila.get('sku') or '').strip().upper()
        if not sku or len(sku) > 80:
            raise ValueError('Seleccioná el producto de cada componente.')
        if sku in vistos:
            raise ValueError(f'{sku}: el componente está repetido. Ajustá su cantidad en una sola fila.')
        try:
            cantidad = Decimal(str(fila.get('cantidad', '')).strip().replace(',', '.'))
        except InvalidOperation as error:
            raise ValueError(f'{sku}: ingresá una cantidad válida mayor que cero.') from error
        if not cantidad.is_finite() or cantidad <= 0 or cantidad > Decimal('999999999999.999999') or cantidad != cantidad.quantize(Decimal('0.000001')):
            raise ValueError(f'{sku}: ingresá una cantidad mayor que cero, con hasta seis decimales.')
        vistos.add(sku)
        salida.append({'sku': sku, 'cantidad': format(cantidad.quantize(Decimal('0.000001')), 'f')})
    return salida


def esquema_combo_disponible(db_session):
    inspector = inspect(db_session.connection())
    return all(inspector.has_table(t) for t in ('perfil_costeo_producto', 'combo_producto_componente'))


def leer_composiciones(productos, db_session, organizacion_id):
    """Carga agrupada: mismos perfiles por ámbito, sin copiar recetas."""
    if not productos or not esquema_combo_disponible(db_session):
        return {}
    from models.perfil_costeo_producto import PerfilCosteoProducto as Perfil, ComboProductoComponente as Linea
    from models.producto import Producto
    perfiles = db_session.query(Perfil).filter(Perfil.organizacion_id == organizacion_id,
        Perfil.producto_id.in_([p.id for p in productos]), Perfil.tipo == 'combo').order_by(Perfil.id).populate_existing().all()
    lineas = db_session.query(Linea, Perfil, Producto).join(Perfil, Perfil.id == Linea.componente_perfil_id).join(
        Producto, Producto.id == Perfil.producto_id).filter(
        Linea.combo_perfil_id.in_([p.id for p in perfiles]),
        Perfil.organizacion_id == organizacion_id, Producto.organizacion_id == organizacion_id,
    ).order_by(Linea.id).populate_existing().all() if perfiles else []
    por_perfil = {}
    for linea, perfil, producto in lineas:
        por_perfil.setdefault(linea.combo_perfil_id, []).append({'sku': producto.sku,
            'cantidad': format(linea.cantidad, 'f'), 'linea_id': linea.id,
            'perfil_id': perfil.id, 'observacion': linea.observacion or ''})
    salida = {}
    for perfil in perfiles:
        salida.setdefault(perfil.producto_id, []).append({'perfil_id': perfil.id,
            'unidad_combo_id': perfil.unidad_negocio_id, 'activo': perfil.activo,
            'componentes_combo': por_perfil.get(perfil.id, [])})
    return salida


def preparar_composicion(producto, datos, db_session, organizacion_id):
    """Valida todo antes del alta. None conserva composiciones ya existentes."""
    if datos['tipo'] != 'combo':
        if datos.get('componentes_combo'):
            raise ValueError('Solo un producto de tipo Combo admite componentes de combo.')
        return None
    if not esquema_combo_disponible(db_session):
        raise ValueError('Falta preparar las tablas de composición de Costos. No se creó el combo.')
    existentes = leer_composiciones([producto], db_session, organizacion_id).get(producto.id, []) if producto else []
    if 'componentes_combo' not in datos:
        if existentes and all(c['componentes_combo'] for c in existentes):
            return None
        raise ValueError('Elegí al menos un producto y su cantidad para crear o completar el combo.')
    filas = datos['componentes_combo']
    if not filas:
        raise ValueError('Elegí al menos un producto y su cantidad. Un combo no puede quedar vacío.')
    from models.producto import Producto
    from models.producto_ficha_maestra import ProductoFichaMaestra as Ficha
    from models.perfil_costeo_producto import PerfilCosteoProducto as Perfil
    from models.unidad_negocio import UnidadNegocio
    unidad_id = datos.get('unidad_combo_id')
    if unidad_id is not None:
        unidad = db_session.query(UnidadNegocio).filter_by(id=unidad_id, organizacion_id=organizacion_id).first()
        if unidad is None:
            raise ValueError('La unidad del combo no pertenece a la organización activa.')
    componentes = []
    for fila in sorted(filas, key=lambda f: f["sku"]):
        if fila['sku'] == datos['sku']:
            raise ValueError('Un combo no puede contenerse a sí mismo. Elegí otro producto.')
        candidatos = db_session.query(Producto).filter(Producto.organizacion_id == organizacion_id,
            func.upper(Producto.sku) == fila['sku']).with_for_update().all()
        if len(candidatos) != 1:
            raise ValueError(f"{fila['sku']}: elegí un producto existente y único de esta organización.")
        componente = candidatos[0]
        ficha = db_session.query(Ficha).filter_by(producto_id=componente.id, organizacion_id=organizacion_id).first()
        if ficha is None or not ficha.activo or not ficha.habilita_componente:
            raise ValueError(f"{fila['sku']}: configurá su ficha y habilitá Componente de combo en Productos.")
        if ficha.tipo not in {'simple', 'produccion'}:
            raise ValueError('Un combo solo puede contener productos simples o de producción; no otros combos.')
        perfiles = db_session.query(Perfil).filter_by(producto_id=componente.id, organizacion_id=organizacion_id).all()
        if any(p.tipo != ficha.tipo for p in perfiles):
            raise ValueError(f"{fila['sku']}: revisá la coherencia entre la ficha y sus perfiles de costeo.")
        perfil = next((p for p in perfiles if p.unidad_negocio_id == unidad_id), None)
        if perfil is not None and not perfil.activo:
            raise ValueError(f"{fila['sku']}: el perfil de costeo está inactivo en la unidad elegida.")
        componentes.append((componente, ficha.tipo, perfil, fila['cantidad']))
    perfil_combo = next((c for c in existentes if c['unidad_combo_id'] == unidad_id), None)
    if perfil_combo is not None and not perfil_combo['activo']:
        raise ValueError('El perfil del combo está inactivo. Revisalo en Costos antes de editar su composición.')
    return {'unidad_id': unidad_id, 'componentes': componentes}


def guardar_composicion(producto, plan, db_session):
    if plan is None:
        return
    from models.producto import Producto
    from models.unidad_negocio import UnidadNegocio
    from models.perfil_costeo_producto import PerfilCosteoProducto as Perfil, ComboProductoComponente as Linea
    from services.perfiles_costeo import crear_o_actualizar_perfil, crear_o_actualizar_componente_combo
    def perfil_para(p, tipo):
        perfil = db_session.query(Perfil).filter_by(organizacion_id=p.organizacion_id,
            producto_id=p.id, unidad_negocio_id=plan['unidad_id']).first()
        return perfil if perfil is not None else crear_o_actualizar_perfil(
            organizacion_id=p.organizacion_id, producto_id=p.id, unidad_negocio_id=plan['unidad_id'],
            tipo=tipo, PerfilCosteoProducto=Perfil, UnidadNegocio=UnidadNegocio, Producto=Producto,
            db_session=db_session, commit=False)
    combo = perfil_para(producto, 'combo')
    conservar = set()
    for componente, tipo, perfil, cantidad in plan['componentes']:
        perfil = perfil or perfil_para(componente, tipo)
        anterior = db_session.query(Linea).filter_by(combo_perfil_id=combo.id, componente_perfil_id=perfil.id).first()
        linea, _ = crear_o_actualizar_componente_combo(combo, perfil, cantidad=cantidad,
            observacion=anterior.observacion if anterior else None,
            ComboProductoComponente=Linea, db_session=db_session, commit=False)
        conservar.add(linea.id)
    for linea in db_session.query(Linea).filter_by(combo_perfil_id=combo.id).all():
        if linea.id not in conservar:
            db_session.delete(linea)
    db_session.flush()
