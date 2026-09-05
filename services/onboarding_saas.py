"""Alta y administración interna de tenants, sin efectos externos."""

import re
import unicodedata


def normalizar_codigo(valor, *, campo="código"):
    texto = unicodedata.normalize("NFKD", str(valor or "").strip().lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")[:80]
    if not texto:
        raise ValueError(f"Completá un {campo} válido.")
    return texto


def _texto(valor, nombre, limite=150):
    resultado = str(valor or "").strip()[:limite]
    if not resultado:
        raise ValueError(f"Completá {nombre}.")
    return resultado


def _commit(db_session):
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise


def membresia_del_usuario(UsuarioOrganizacion, *, usuario_id, organizacion_id):
    membresia = UsuarioOrganizacion.query.filter_by(
        usuario_id=int(usuario_id), organizacion_id=int(organizacion_id),
    ).first()
    if membresia is None:
        raise ValueError("La organización no pertenece al usuario actual.")
    return membresia


def crear_organizacion(
    *, nombre, slug, unidad_nombre, unidad_codigo, usuario,
    Organizacion, UnidadNegocio, UsuarioOrganizacion, ModuloOrganizacion,
    db_session, asegurar_modulos_fn,
):
    """Crea tenant, primera unidad y módulos, todos inactivos/desactivados."""
    nombre = _texto(nombre, "el nombre de la organización")
    slug = normalizar_codigo(slug or nombre, campo="identificador")
    unidad_nombre = _texto(unidad_nombre, "el nombre de la primera unidad")
    unidad_codigo = normalizar_codigo(unidad_codigo or unidad_nombre)
    if Organizacion.query.filter_by(slug=slug).first() is not None:
        raise ValueError("Ya existe una organización con ese identificador.")
    organizacion = Organizacion(nombre=nombre, slug=slug, activa=False)
    db_session.add(organizacion)
    db_session.flush()
    db_session.add(UnidadNegocio(
        organizacion_id=organizacion.id, nombre=unidad_nombre,
        codigo=unidad_codigo, activa=False,
    ))
    db_session.add(UsuarioOrganizacion(
        usuario_id=usuario.id, organizacion_id=organizacion.id,
        rol="admin", activa=True, predeterminada=False,
    ))
    asegurar_modulos_fn(
        ModuloOrganizacion=ModuloOrganizacion,
        organizacion_id=organizacion.id,
        db_session=db_session,
        logger_fn=None,
    )
    return organizacion


def cambiar_estado_organizacion(
    organizacion_id, *, usuario_id, Organizacion, UsuarioOrganizacion, db_session,
):
    membresia_del_usuario(
        UsuarioOrganizacion, usuario_id=usuario_id,
        organizacion_id=organizacion_id,
    )
    organizacion = Organizacion.query.get(int(organizacion_id))
    if organizacion is None:
        raise ValueError("No se encontró la organización.")
    organizacion.activa = not bool(organizacion.activa)
    _commit(db_session)
    return organizacion


def actualizar_organizacion(organizacion, *, nombre, slug, Organizacion, db_session):
    nombre = _texto(nombre, "el nombre de la organización")
    slug = normalizar_codigo(slug or nombre, campo="identificador")
    repetida = Organizacion.query.filter_by(slug=slug).first()
    if repetida is not None and repetida.id != organizacion.id:
        raise ValueError("Ya existe una organización con ese identificador.")
    organizacion.nombre = nombre
    organizacion.slug = slug
    _commit(db_session)
    return organizacion


def crear_unidad(organizacion, *, nombre, codigo, UnidadNegocio, db_session):
    nombre = _texto(nombre, "el nombre de la unidad")
    codigo = normalizar_codigo(codigo or nombre)
    existente = UnidadNegocio.query.filter_by(
        organizacion_id=organizacion.id, codigo=codigo,
    ).first()
    if existente is not None:
        raise ValueError("Ya existe una unidad con ese código en la organización.")
    unidad = UnidadNegocio(
        organizacion_id=organizacion.id, nombre=nombre,
        codigo=codigo, activa=False,
    )
    db_session.add(unidad)
    _commit(db_session)
    return unidad


def actualizar_unidad(
    organizacion, unidad_id, *, nombre, codigo, UnidadNegocio, db_session,
):
    unidad = UnidadNegocio.query.get(int(unidad_id))
    if unidad is None or unidad.organizacion_id != organizacion.id:
        raise ValueError("La unidad no pertenece al tenant activo.")
    nombre = _texto(nombre, "el nombre de la unidad")
    codigo = normalizar_codigo(codigo or nombre)
    repetida = UnidadNegocio.query.filter_by(
        organizacion_id=organizacion.id, codigo=codigo,
    ).first()
    if repetida is not None and repetida.id != unidad.id:
        raise ValueError("Ya existe una unidad con ese código en la organización.")
    unidad.nombre = nombre
    unidad.codigo = codigo
    _commit(db_session)
    return unidad


def cambiar_estado_unidad(organizacion, unidad_id, *, UnidadNegocio, db_session):
    unidad = UnidadNegocio.query.get(int(unidad_id))
    if unidad is None or unidad.organizacion_id != organizacion.id:
        raise ValueError("La unidad no pertenece al tenant activo.")
    unidad.activa = not bool(unidad.activa)
    _commit(db_session)
    return unidad
