"""
Adaptador web para resolver la membresia tenant activa.

La membresia se cachea solamente durante el request actual.
No confia en roles almacenados por el cliente.
"""

from flask import g, session

from services.tenant_context import (
    TenantError,
    resolver_tenant_usuario,
)


def membresia_actual_web(
    usuario,
    *,
    UsuarioOrganizacion,
):
    if usuario is None:
        return None

    organizacion_solicitada = session.get(
        "organizacion_id"
    )
    clave = (
        usuario.id,
        organizacion_solicitada,
    )

    if getattr(
        g,
        "_clave_membresia_tenant",
        None,
    ) == clave:
        return getattr(
            g,
            "_membresia_tenant_actual",
            None,
        )

    try:
        membresia = resolver_tenant_usuario(
            usuario,
            UsuarioOrganizacion=(
                UsuarioOrganizacion
            ),
            organizacion_id=(
                organizacion_solicitada
            ),
        )
    except TenantError:
        membresia = None

    if membresia is not None:
        session["organizacion_id"] = (
            membresia.organizacion_id
        )
        clave = (
            usuario.id,
            membresia.organizacion_id,
        )

    g._clave_membresia_tenant = clave
    g._membresia_tenant_actual = membresia

    return membresia
