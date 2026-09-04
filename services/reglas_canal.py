"""Persistencia versionada de politicas genericas por lista/canal."""

from decimal import Decimal, InvalidOperation

from services.fechas import ahora_utc_naive


def _entero(valor, nombre, permitir_vacio=False):
    if permitir_vacio and str(valor or "").strip() == "": return None
    try: numero = int(valor)
    except (TypeError, ValueError) as error: raise ValueError(f"{nombre} no es válido.") from error
    if numero < 0: raise ValueError(f"{nombre} no puede ser negativo.")
    return numero


def crear_regla_canal(lista, *, nombre, comision_pct, umbral_envio_centavos, costo_envio_default_centavos, incremento_redondeo_centavos, observacion, usuario, ReglaCanalVersion, db_session):
    try: comision = Decimal(str(comision_pct or 0).replace(",", "."))
    except InvalidOperation as error: raise ValueError("La comisión no es válida.") from error
    if comision < 0 or comision >= 100: raise ValueError("La comisión debe ser menor a 100%.")
    anteriores = ReglaCanalVersion.query.filter_by(lista_precio_id=lista.id).all()
    regla = ReglaCanalVersion(
        lista_precio_id=lista.id, numero_version=max((r.numero_version for r in anteriores), default=0) + 1,
        nombre=str(nombre or "").strip(), comision_pct=comision,
        umbral_envio_centavos=_entero(umbral_envio_centavos, "El umbral de envío"),
        costo_envio_default_centavos=_entero(costo_envio_default_centavos, "El costo de envío"),
        incremento_redondeo_centavos=max(1, _entero(incremento_redondeo_centavos, "El redondeo")),
        observacion=str(observacion or "").strip() or None,
        creado_por_usuario_id=getattr(usuario, "id", None), creado_por_username=getattr(usuario, "username", None),
    )
    if not regla.nombre: raise ValueError("La política requiere un nombre.")
    db_session.add(regla); db_session.commit(); return regla


def agregar_tramo(regla, *, precio_desde_centavos, precio_hasta_centavos, cargo_fijo_centavos, ReglaCanalCargoTramo, db_session):
    if regla.estado != "preparatorio": raise ValueError("Solo se pueden editar tramos de una política preparatoria.")
    desde = _entero(precio_desde_centavos, "El precio desde")
    hasta = _entero(precio_hasta_centavos, "El precio hasta", permitir_vacio=True)
    if hasta is not None and hasta <= desde: raise ValueError("El precio hasta debe superar al precio desde.")
    for actual in regla.tramos:
        fin_actual = actual.precio_hasta_centavos
        if (hasta is None or actual.precio_desde_centavos < hasta) and (fin_actual is None or desde < fin_actual):
            raise ValueError("El tramo se superpone con otro existente.")
    tramo = ReglaCanalCargoTramo(regla_canal_version_id=regla.id, precio_desde_centavos=desde, precio_hasta_centavos=hasta, cargo_fijo_centavos=_entero(cargo_fijo_centavos, "El cargo fijo"))
    db_session.add(tramo); db_session.commit(); return tramo


def activar_regla_canal(regla, *, ReglaCanalVersion, db_session):
    if regla.estado != "preparatorio": raise ValueError("La política no está preparatoria.")
    momento = ahora_utc_naive()
    for anterior in ReglaCanalVersion.query.filter_by(lista_precio_id=regla.lista_precio_id, vigente=True).all():
        anterior.vigente = False; anterior.estado = "archivado"; anterior.vigente_hasta = momento
    regla.vigente = True; regla.estado = "vigente"; regla.vigente_desde = momento
    db_session.commit(); return regla
