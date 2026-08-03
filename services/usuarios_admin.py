"""
Administración de usuarios y membresías por tenant.

UsuarioSistema conserva la identidad global. Los permisos y el
acceso operativo pertenecen a UsuarioOrganizacion.
"""

from werkzeug.security import generate_password_hash


ROLES_TENANT = (
    "admin",
    "carga",
    "despacho",
)


def _texto(formulario, campo, maximo):
    return str(
        formulario.get(campo)
        or ""
    ).strip()[:maximo]


def _guardar(db_session):
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise


def _membresia_tenant(
    membresia_id,
    *,
    organizacion,
    UsuarioOrganizacion,
):
    try:
        membresia_id = int(membresia_id)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "La membresía no es válida."
        ) from error

    membresia = (
        UsuarioOrganizacion.query
        .filter_by(
            id=membresia_id,
            organizacion_id=organizacion.id,
        )
        .first()
    )

    if membresia is None:
        raise ValueError(
            "La membresía no existe en "
            "la organización activa."
        )

    return membresia


def _cantidad_membresias(
    usuario_id,
    *,
    UsuarioOrganizacion,
):
    return (
        UsuarioOrganizacion.query
        .filter_by(usuario_id=usuario_id)
        .count()
    )


def crear_usuario_tenant(
    formulario,
    *,
    organizacion,
    UsuarioSistema,
    UsuarioOrganizacion,
    db_session,
    creador,
):
    username = _texto(
        formulario,
        "username",
        80,
    )
    nombre = _texto(
        formulario,
        "nombre",
        120,
    )
    rol = _texto(
        formulario,
        "rol",
        30,
    ) or "carga"
    password = str(
        formulario.get("password")
        or ""
    )

    if not username or not nombre or not password:
        raise ValueError(
            "Completá usuario, nombre y contraseña."
        )

    if rol not in ROLES_TENANT:
        raise ValueError("El rol no es válido.")

    existente = (
        UsuarioSistema.query
        .filter_by(username=username)
        .first()
    )

    if existente is not None:
        raise ValueError(
            "Ese usuario ya existe. La incorporación "
            "de identidades existentes requiere una "
            "invitación segura."
        )

    usuario = UsuarioSistema(
        username=username,
        nombre=nombre,
        rol=rol,
        password_hash=generate_password_hash(
            password
        ),
        activo=True,
        creado_por=(
            getattr(creador, "username", None)
            or "admin"
        ),
    )
    db_session.add(usuario)
    db_session.flush()

    membresia = UsuarioOrganizacion(
        usuario_id=usuario.id,
        organizacion_id=organizacion.id,
        rol=rol,
        activa=True,
        predeterminada=True,
    )
    db_session.add(membresia)
    _guardar(db_session)

    return (
        membresia,
        "Usuario creado en la organización.",
    )


def editar_membresia_tenant(
    membresia_id,
    formulario,
    *,
    organizacion,
    UsuarioOrganizacion,
    db_session,
):
    membresia = _membresia_tenant(
        membresia_id,
        organizacion=organizacion,
        UsuarioOrganizacion=(
            UsuarioOrganizacion
        ),
    )
    usuario = membresia.usuario

    nombre = _texto(
        formulario,
        "nombre",
        120,
    )
    rol = _texto(
        formulario,
        "rol",
        30,
    )
    password = str(
        formulario.get("password")
        or ""
    )

    if not nombre:
        raise ValueError(
            "El nombre no puede quedar vacío."
        )

    if rol not in ROLES_TENANT:
        raise ValueError("El rol no es válido.")

    total = _cantidad_membresias(
        usuario.id,
        UsuarioOrganizacion=(
            UsuarioOrganizacion
        ),
    )

    if total > 1 and (
        nombre != usuario.nombre
        or password
    ):
        raise ValueError(
            "La identidad pertenece a varias "
            "organizaciones. Su nombre o contraseña "
            "deben administrarse fuera del tenant."
        )

    membresia.rol = rol

    if total == 1:
        usuario.nombre = nombre
        usuario.rol = rol

        if password:
            usuario.password_hash = (
                generate_password_hash(password)
            )

    _guardar(db_session)

    return (
        membresia,
        "Membresía actualizada correctamente.",
    )


def cambiar_estado_membresia_tenant(
    membresia_id,
    *,
    organizacion,
    usuario_actual,
    UsuarioOrganizacion,
    db_session,
):
    membresia = _membresia_tenant(
        membresia_id,
        organizacion=organizacion,
        UsuarioOrganizacion=(
            UsuarioOrganizacion
        ),
    )

    if (
        usuario_actual is not None
        and membresia.usuario_id
        == usuario_actual.id
        and bool(membresia.activa)
    ):
        raise ValueError(
            "No podés desactivar tu propia "
            "membresía activa."
        )

    membresia.activa = not bool(
        membresia.activa
    )

    total = _cantidad_membresias(
        membresia.usuario_id,
        UsuarioOrganizacion=(
            UsuarioOrganizacion
        ),
    )

    if total == 1:
        membresia.usuario.activo = (
            membresia.activa
        )

    _guardar(db_session)

    estado = (
        "activada"
        if membresia.activa
        else "desactivada"
    )

    return (
        membresia,
        f"Membresía {estado} correctamente.",
    )
