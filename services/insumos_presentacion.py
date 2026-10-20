"""Bulto de compra separado de la tarifa neta por unidad del insumo."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from sqlalchemy import inspect, or_


def disponible(session):
    from models.insumo_presentacion_compra import InsumoPresentacionCompra as Modelo, InsumoPrecioBultoVersion
    i = inspect(session.connection())
    return all(i.has_table(m.__tablename__) and set(m.__table__.c.keys()) <= {c['name'] for c in i.get_columns(m.__tablename__)} for m in (Modelo, InsumoPrecioBultoVersion))


def validar(datos):
    cantidad = str(datos.get('cantidad_bulto') if datos.get('cantidad_bulto') is not None else '').strip().replace(',', '.')
    medidas = str(datos.get('medidas_origen') or '').strip()
    if cantidad:
        try:
            n = Decimal(cantidad)
        except InvalidOperation as error:
            raise ValueError('La cantidad por bulto no es válida.') from error
        if not n.is_finite() or n <= 0 or n > Decimal('999999999999.999999') or n != n.quantize(Decimal('0.000001')):
            raise ValueError('La cantidad por bulto debe ser positiva, con hasta seis decimales.')
        cantidad = str(n)
    if len(medidas) > 120:
        raise ValueError('Las medidas de origen admiten hasta 120 caracteres.')
    return {'cantidad_bulto': cantidad, 'medidas_origen': medidas}


def preparar_precio(datos):
    """Normaliza una vez. Nunca vuelve a dividir un precio cotizado por unidad."""
    valores = validar(datos)
    cantidad = Decimal(valores['cantidad_bulto']) if valores['cantidad_bulto'] else None
    def importe(campo):
        valor = datos.get(campo)
        if valor is None or not str(valor).strip(): return None
        try: n = Decimal(str(valor).strip().replace(',', '.'))
        except InvalidOperation as error: raise ValueError('El precio no es válido.') from error
        if not n.is_finite() or n < 0 or n > Decimal('999999999999.99'):
            raise ValueError('El precio está fuera de rango.')
        return n
    unitario = importe('precio_unitario'); bulto = importe('precio_bulto')
    base = str(datos.get('base_precio') or ('bulto' if unitario is None and bulto is not None else 'unitario')).strip().lower()
    if base not in {'unitario', 'bulto'}: raise ValueError('Elegí precio por unidad o por bulto.')
    if bulto is not None and cantidad is None:
        raise ValueError('El precio por bulto requiere su cantidad de metros o unidades.')
    if base == 'bulto':
        if bulto is None or cantidad is None: raise ValueError('Completá precio y cantidad por bulto.')
        normalizado = (bulto / cantidad).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        if unitario is not None and unitario.quantize(Decimal('.01'), rounding=ROUND_HALF_UP) != normalizado:
            raise ValueError('El precio unitario no coincide con precio por bulto dividido por cantidad.')
        unitario = normalizado
    elif unitario is None:
        raise ValueError('Precio unitario es obligatorio cuando la cotización es por unidad.')
    elif bulto is not None and bulto.quantize(Decimal('.01'), rounding=ROUND_HALF_UP) != (unitario.quantize(Decimal('.01'), rounding=ROUND_HALF_UP) * cantidad).quantize(Decimal('.01'), rounding=ROUND_HALF_UP):
        raise ValueError('Los precios por unidad y por bulto no coinciden.')
    if unitario > Decimal('999999999999.99'): raise ValueError('El precio unitario calculado está fuera de rango.')
    centavos = int((unitario * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    total = bulto if bulto is not None else Decimal(centavos) / 100 * cantidad if cantidad is not None else None
    if total is not None and total > Decimal('999999999999.99'):
        raise ValueError('El precio por bulto calculado está fuera de rango.')
    return {**valores, 'base_precio': base, 'unitario_centavos': centavos,
            'bulto_centavos': int((total * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) if total is not None else None}


def guardar_precio(version, insumo, datos, session, organizacion_id):
    plan = preparar_precio(datos)
    if version.insumo_id != insumo.id or insumo.organizacion_id != organizacion_id:
        raise ValueError('La versión de precio no pertenece al insumo de la organización.')
    if version.precio_unitario_centavos != plan['unitario_centavos']:
        raise ValueError('El precio normalizado no coincide con la versión de precio.')
    if not disponible(session):
        if plan['cantidad_bulto'] or plan['bulto_centavos'] is not None:
            raise ValueError('Falta preparar los bultos de insumos en staging.')
        return
    from models.insumo_presentacion_compra import InsumoPresentacionCompra, InsumoPrecioBultoVersion
    cantidad = Decimal(plan['cantidad_bulto']) if plan['cantidad_bulto'] else None
    if cantidad is None:
        r = session.query(InsumoPresentacionCompra).filter_by(insumo_id=insumo.id, organizacion_id=organizacion_id).first()
        cantidad = r.cantidad_bulto if r is not None else None
    if cantidad is None: return
    total = plan['bulto_centavos']
    if total is None:
        total = int((Decimal(version.precio_unitario_centavos) * cantidad).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    if total > 99999999999999:
        raise ValueError('El precio por bulto calculado está fuera de rango.')
    session.add(InsumoPrecioBultoVersion(precio_version_id=version.id, organizacion_id=organizacion_id,
        cantidad_bulto=cantidad, precio_bulto_centavos=total, base_precio=plan['base_precio']))
    session.flush()


def guardar(insumo, datos, session, organizacion_id):
    valores = validar(datos)
    # Vacío/no mapeado conserva lo guardado. No presupone un bulto de una unidad.
    if not any(valores.values()):
        return
    if insumo.organizacion_id != organizacion_id:
        raise ValueError('El insumo no pertenece a la organización.')
    if not disponible(session):
        raise ValueError('Falta preparar los bultos en staging: python -m scripts.preparar_bultos_insumos --staging')
    from models.insumo_presentacion_compra import InsumoPresentacionCompra as Modelo
    r = session.query(Modelo).filter_by(insumo_id=insumo.id).first()
    if r is not None and r.organizacion_id != organizacion_id:
        raise ValueError('La presentación no pertenece a la organización.')
    if r is None:
        r = Modelo(insumo_id=insumo.id, organizacion_id=organizacion_id)
        session.add(r)
    if valores['cantidad_bulto']:
        r.cantidad_bulto = Decimal(valores['cantidad_bulto'])
    if valores['medidas_origen']:
        r.medidas_origen = valores['medidas_origen']
    session.flush()  # La misma transacción que el insumo y su precio; no hace commit.


def leer(session, organizacion_id, unidad_id):
    if not disponible(session):
        return {}
    from models.insumo_presentacion_compra import InsumoPresentacionCompra as Modelo
    from models.fuentes_costo_productivo import InsumoProductivo as Insumo
    filas = session.query(Modelo).join(Insumo, Insumo.id == Modelo.insumo_id).filter(
        Modelo.organizacion_id == organizacion_id,
        Insumo.organizacion_id == organizacion_id,
        or_(Insumo.unidad_negocio_id.is_(None), Insumo.unidad_negocio_id == unidad_id),
    ).all()
    salida = {r.insumo_id: {'cantidad_bulto': r.cantidad_bulto, 'medidas_origen': r.medidas_origen or '',
        'precio_bulto_centavos': None, 'base_precio': 'unitario', 'historial': {}} for r in filas}
    if not salida: return salida
    from models.fuentes_costo_productivo import InsumoPrecioVersion
    from models.insumo_presentacion_compra import InsumoPrecioBultoVersion
    versiones = session.query(InsumoPrecioVersion).filter(InsumoPrecioVersion.insumo_id.in_(salida), InsumoPrecioVersion.moneda == 'ARS').all()
    ids = [v.id for v in versiones]
    historicos = {v.precio_version_id: v for v in session.query(InsumoPrecioBultoVersion).filter(
        InsumoPrecioBultoVersion.precio_version_id.in_(ids), InsumoPrecioBultoVersion.organizacion_id == organizacion_id).all()} if ids else {}
    for v in versiones:
        d = salida[v.insumo_id]; h = historicos.get(v.id)
        if h is not None:
            d['historial'][v.id] = {'cantidad_bulto': h.cantidad_bulto, 'precio_bulto_centavos': h.precio_bulto_centavos, 'base_precio': h.base_precio}
        if not v.vigente: continue
        if h is not None:
            d['precio_bulto_centavos'] = h.precio_bulto_centavos; d['base_precio'] = h.base_precio
        elif d['cantidad_bulto'] is not None:
            d['precio_bulto_centavos'] = int((Decimal(v.precio_unitario_centavos) * d['cantidad_bulto']).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    return salida
