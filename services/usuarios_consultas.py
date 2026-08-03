"""
Consultas del panel de usuarios aisladas por tenant.
"""


def obtener_membresias_usuario(
    *,
    organizacion_id,
    UsuarioSistema,
    UsuarioOrganizacion,
):
    return (
        UsuarioOrganizacion.query
        .join(UsuarioSistema)
        .filter(
            UsuarioOrganizacion.organizacion_id
            == organizacion_id
        )
        .order_by(
            UsuarioOrganizacion.activa.desc(),
            UsuarioOrganizacion.rol.asc(),
            UsuarioSistema.username.asc(),
        )
        .all()
    )
