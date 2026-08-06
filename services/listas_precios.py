"""Reglas y persistencia del dominio de listas de precios."""

from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP

from sqlalchemy import func

from services.fechas import ahora_utc_naive


TIPOS_LISTA = {"mostrador", "tiendanube", "mercadolibre", "mayorista"}


def _opcion(valor, opciones, nombre):
    normalizado = str(valor or "").strip().lower()
    if normalizado not in opciones:
        raise ValueError(f"{nombre} invalido: {normalizado or '(vacio)'}.")
    return normalizado


def _moneda(valor):
    moneda = str(valor or "").strip().upper()
    if len(moneda) != 3 or not moneda.isalpha():
        raise ValueError("La moneda debe tener tres letras.")
    return moneda


def _commit(db_session, commit):
    if not commit:
        return
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise


def validar_organizacion_unidad(
    *, organizacion_id, unidad_negocio_id,
    Organizacion, UnidadNegocio, db_session,
):
    organizacion = db_session.get(Organizacion, organizacion_id)
    if organizacion is None:
        raise ValueError("La organizacion indicada no existe.")
    unidad = None
    if unidad_negocio_id is not None:
        unidad = db_session.get(UnidadNegocio, unidad_negocio_id)
        if unidad is None:
            raise ValueError("La unidad indicada no existe.")
        if int(unidad.organizacion_id) != int(organizacion_id):
            raise ValueError("La unidad no pertenece a la organizacion.")
    return organizacion, unidad


def crear_lista_precio(
    *, organizacion_id, unidad_negocio_id, codigo, nombre, tipo,
    moneda="ARS", descripcion=None, creado_por_usuario_id=None,
    creado_por_username=None, Organizacion, UnidadNegocio,
    ListaPrecio, db_session, commit=True,
):
    validar_organizacion_unidad(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        Organizacion=Organizacion,
        UnidadNegocio=UnidadNegocio,
        db_session=db_session,
    )
    codigo_limpio = str(codigo or "").strip().lower()
    nombre_limpio = str(nombre or "").strip()
    if not codigo_limpio or not nombre_limpio:
        raise ValueError("La lista requiere codigo y nombre.")
    if ListaPrecio.query.filter_by(
        organizacion_id=organizacion_id, codigo=codigo_limpio
    ).first() is not None:
        raise ValueError("Ya existe una lista con ese codigo.")
    lista = ListaPrecio(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        codigo=codigo_limpio,
        nombre=nombre_limpio,
        descripcion=str(descripcion or "").strip() or None,
        tipo=_opcion(tipo, TIPOS_LISTA, "Tipo de lista"),
        moneda=_moneda(moneda),
        estado="preparatorio",
        creado_por_usuario_id=creado_por_usuario_id,
        creado_por_username=str(creado_por_username or "").strip() or None,
    )
    db_session.add(lista)
    _commit(db_session, commit)
    return lista


def crear_politica_lista(
    lista, *, comision_pct=0, cargo_fijo_centavos=0,
    flete_venta_centavos=0, margen_objetivo_pct=0,
    incremento_redondeo_centavos=1, creado_por_usuario_id=None,
    creado_por_username=None, PoliticaComercialLista,
    db_session, commit=True,
):
    if lista is None or lista.id is None:
        raise ValueError("La lista indicada no existe.")
    comision = decimal_porcentaje(comision_pct, "La comision")
    margen = decimal_porcentaje(margen_objetivo_pct, "El margen objetivo")
    if comision + margen >= Decimal("100"):
        raise ValueError("Comision y margen deben sumar menos de 100.")
    ultima = db_session.query(func.max(
        PoliticaComercialLista.numero_version
    )).filter_by(lista_precio_id=lista.id).scalar() or 0
    politica = PoliticaComercialLista(
        lista_precio_id=lista.id,
        numero_version=ultima + 1,
        comision_pct=comision,
        cargo_fijo_centavos=entero_no_negativo(
            cargo_fijo_centavos, "El cargo fijo"
        ),
        flete_venta_centavos=entero_no_negativo(
            flete_venta_centavos, "El flete de venta"
        ),
        margen_objetivo_pct=margen,
        incremento_redondeo_centavos=max(
            1, entero_no_negativo(
                incremento_redondeo_centavos, "El incremento"
            )
        ),
        estado="preparatorio",
        vigente=False,
        creado_por_usuario_id=creado_por_usuario_id,
        creado_por_username=str(creado_por_username or "").strip() or None,
    )
    db_session.add(politica)
    _commit(db_session, commit)
    return politica


def activar_politica_lista(
    politica, *, PoliticaComercialLista, db_session,
    ahora_fn=ahora_utc_naive, commit=True,
):
    if politica is None or politica.id is None:
        raise ValueError("La politica indicada no existe.")
    momento = ahora_fn()
    try:
        anteriores = PoliticaComercialLista.query.filter(
            PoliticaComercialLista.lista_precio_id == politica.lista_precio_id,
            PoliticaComercialLista.vigente.is_(True),
            PoliticaComercialLista.id != politica.id,
        ).all()
        for anterior in anteriores:
            anterior.vigente = False
            anterior.estado = "archivado"
            anterior.vigente_hasta = momento
        politica.vigente = True
        politica.estado = "vigente"
        politica.vigente_desde = momento
        politica.vigente_hasta = None
        _commit(db_session, commit)
    except Exception:
        db_session.rollback()
        raise
    return politica


def decimal_porcentaje(valor, nombre):
    try:
        numero = Decimal(str(valor).strip())
    except (InvalidOperation, AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"{nombre} no es valido.") from error
    if not numero.is_finite() or numero < 0 or numero >= 100:
        raise ValueError(f"{nombre} debe estar entre 0 y menos de 100.")
    return numero


def entero_no_negativo(valor, nombre):
    try:
        numero = int(valor)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{nombre} no es valido.") from error
    if numero < 0:
        raise ValueError(f"{nombre} no puede ser negativo.")
    return numero


def redondear_hacia_arriba(centavos, incremento):
    importe = entero_no_negativo(centavos, "El importe")
    paso = entero_no_negativo(incremento, "El incremento")
    if paso == 0:
        raise ValueError("El incremento debe ser mayor que cero.")
    return int(
        (Decimal(importe) / Decimal(paso)).to_integral_value(
            rounding=ROUND_CEILING
        ) * paso
    )


def calcular_precio_comercial(
    *, costo_base_centavos, flete_venta_centavos=0,
    cargo_fijo_centavos=0, comision_pct=0,
    margen_objetivo_pct=0, impuesto_pct=0,
    incremento_redondeo_centavos=1, precio_elegido_centavos=None,
):
    costo = entero_no_negativo(costo_base_centavos, "El costo base")
    flete = entero_no_negativo(flete_venta_centavos, "El flete de venta")
    cargo = entero_no_negativo(cargo_fijo_centavos, "El cargo fijo")
    comision = decimal_porcentaje(comision_pct, "La comision")
    margen_objetivo = decimal_porcentaje(
        margen_objetivo_pct, "El margen objetivo"
    )
    impuesto = decimal_porcentaje(impuesto_pct, "El impuesto")
    if comision + margen_objetivo >= Decimal("100"):
        raise ValueError("Comision y margen deben sumar menos de 100.")

    base_fija = costo + flete + cargo
    divisor = Decimal("1") - (
        comision + margen_objetivo
    ) / Decimal("100")
    sugerido_sin_redondear = int(
        (Decimal(base_fija) / divisor).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    sugerido = redondear_hacia_arriba(
        sugerido_sin_redondear, incremento_redondeo_centavos
    )
    elegido = sugerido if precio_elegido_centavos is None else (
        entero_no_negativo(precio_elegido_centavos, "El precio elegido")
    )
    comision_centavos = int(
        (Decimal(elegido) * comision / Decimal("100")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    margen_centavos = elegido - base_fija - comision_centavos
    margen_pct = (
        Decimal(margen_centavos) * Decimal("100") / Decimal(elegido)
        if elegido else Decimal("0")
    ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    impuestos_centavos = int(
        (Decimal(elegido) * impuesto / Decimal("100")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    return {
        "costo_base_centavos": costo,
        "flete_venta_centavos": flete,
        "cargo_fijo_centavos": cargo,
        "comision_centavos": comision_centavos,
        "margen_centavos": margen_centavos,
        "margen_pct": margen_pct,
        "impuestos_centavos": impuestos_centavos,
        "precio_neto_sugerido_centavos": sugerido,
        "precio_elegido_centavos": elegido,
        "precio_final_centavos": elegido + impuestos_centavos,
    }


def validar_alcance_lista(
    *, organizacion_id, unidad_negocio_id, catalogo_producto,
    costo_version, lista_precio=None,
):
    if catalogo_producto is None or catalogo_producto.catalogo is None:
        raise ValueError("La inclusion de catalogo no existe.")
    catalogo = catalogo_producto.catalogo
    if int(catalogo.organizacion_id) != int(organizacion_id):
        raise ValueError("El catalogo no pertenece a la organizacion.")
    if catalogo.unidad_negocio_id not in (None, unidad_negocio_id):
        raise ValueError("El catalogo no pertenece a la unidad.")
    if int(costo_version.organizacion_id) != int(organizacion_id):
        raise ValueError("El costo no pertenece a la organizacion.")
    if costo_version.unidad_negocio_id not in (None, unidad_negocio_id):
        raise ValueError("El costo no corresponde a la unidad.")
    if int(costo_version.producto_id) != int(catalogo_producto.producto_id):
        raise ValueError("El costo corresponde a otro producto.")
    if lista_precio is not None:
        if int(lista_precio.organizacion_id) != int(organizacion_id):
            raise ValueError("La lista no pertenece a la organizacion.")
        if lista_precio.unidad_negocio_id not in (None, unidad_negocio_id):
            raise ValueError("La lista no corresponde a la unidad.")
        if lista_precio.moneda != costo_version.moneda:
            raise ValueError("La moneda de la lista y el costo no coinciden.")
    return True


def crear_item_lista(
    *, lista, catalogo_producto, costo_version, politica,
    impuesto_pct=0, precio_elegido_centavos=None,
    creado_por_usuario_id=None, creado_por_username=None,
    ListaPrecioItem, db_session, commit=True,
):
    if lista is None or lista.id is None:
        raise ValueError("La lista indicada no existe.")
    if politica is None or politica.lista_precio_id != lista.id:
        raise ValueError("La politica no pertenece a la lista.")
    if not politica.vigente:
        raise ValueError("La politica debe estar vigente.")
    unidad_id = lista.unidad_negocio_id
    validar_alcance_lista(
        organizacion_id=lista.organizacion_id,
        unidad_negocio_id=unidad_id,
        catalogo_producto=catalogo_producto,
        costo_version=costo_version,
        lista_precio=lista,
    )
    if not costo_version.vigente:
        raise ValueError("El costo debe estar vigente.")
    resultado = calcular_precio_comercial(
        costo_base_centavos=costo_version.costo_total_centavos,
        flete_venta_centavos=politica.flete_venta_centavos,
        cargo_fijo_centavos=politica.cargo_fijo_centavos,
        comision_pct=politica.comision_pct,
        margen_objetivo_pct=politica.margen_objetivo_pct,
        impuesto_pct=impuesto_pct,
        incremento_redondeo_centavos=(
            politica.incremento_redondeo_centavos
        ),
        precio_elegido_centavos=precio_elegido_centavos,
    )
    ultima = db_session.query(func.max(
        ListaPrecioItem.numero_version
    )).filter_by(
        lista_precio_id=lista.id,
        catalogo_producto_id=catalogo_producto.id,
    ).scalar() or 0
    item = ListaPrecioItem(
        lista_precio_id=lista.id,
        catalogo_producto_id=catalogo_producto.id,
        costo_producto_version_id=costo_version.id,
        politica_comercial_lista_id=politica.id,
        numero_version=ultima + 1,
        costo_base_centavos=resultado["costo_base_centavos"],
        precio_neto_sugerido_centavos=(
            resultado["precio_neto_sugerido_centavos"]
        ),
        precio_elegido_centavos=resultado["precio_elegido_centavos"],
        impuestos_centavos=resultado["impuestos_centavos"],
        precio_final_centavos=resultado["precio_final_centavos"],
        margen_centavos=resultado["margen_centavos"],
        margen_pct=resultado["margen_pct"],
        impuesto_pct=decimal_porcentaje(impuesto_pct, "El impuesto"),
        estado="preparatorio",
        vigente=False,
        creado_por_usuario_id=creado_por_usuario_id,
        creado_por_username=str(creado_por_username or "").strip() or None,
    )
    db_session.add(item)
    _commit(db_session, commit)
    return item


def activar_item_lista(
    item, *, ListaPrecioItem, db_session,
    ahora_fn=ahora_utc_naive, commit=True,
):
    if item is None or item.id is None:
        raise ValueError("El precio indicado no existe.")
    momento = ahora_fn()
    try:
        anteriores = ListaPrecioItem.query.filter(
            ListaPrecioItem.lista_precio_id == item.lista_precio_id,
            ListaPrecioItem.catalogo_producto_id == item.catalogo_producto_id,
            ListaPrecioItem.vigente.is_(True),
            ListaPrecioItem.id != item.id,
        ).all()
        for anterior in anteriores:
            anterior.vigente = False
            anterior.estado = "archivado"
            anterior.vigente_hasta = momento
        item.vigente = True
        item.estado = "vigente"
        item.vigente_desde = momento
        item.vigente_hasta = None
        _commit(db_session, commit)
    except Exception:
        db_session.rollback()
        raise
    return item


def historial_politicas(lista_id, *, PoliticaComercialLista):
    return PoliticaComercialLista.query.filter_by(
        lista_precio_id=lista_id
    ).order_by(PoliticaComercialLista.numero_version.desc()).all()


def historial_items(
    lista_id, catalogo_producto_id, *, ListaPrecioItem,
):
    return ListaPrecioItem.query.filter_by(
        lista_precio_id=lista_id,
        catalogo_producto_id=catalogo_producto_id,
    ).order_by(ListaPrecioItem.numero_version.desc()).all()
