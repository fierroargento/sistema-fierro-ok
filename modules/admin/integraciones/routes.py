"""
Panel administrativo de integraciones.

Las acciones, OAuth y webhooks permanecen
temporalmente en app.py.
"""

from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services.integraciones_tenant import (
    cuentas_tienda_nube_tenant,
    obtener_vinculos_canal_tenant,
)
from services.vinculos_canales import (
    CANAL_MERCADO_LIBRE,
)
from services.tenant_context import (
    TenantError,
    resolver_tenant_usuario,
)


SLUG_ORGANIZACION_PLATAFORMA = (
    "grupo-fierro"
)


def crear_blueprint_integraciones(
    *,
    dependencias,
):
    blueprint = Blueprint(
        "admin_integraciones",
        __name__,
    )

    login_required = dependencias[
        "login_required"
    ]
    usuario_actual = dependencias[
        "usuario_actual"
    ]
    UsuarioOrganizacion = dependencias[
        "UsuarioOrganizacion"
    ]
    UnidadNegocio = dependencias.get(
        "UnidadNegocio"
    )
    VinculoCanalComercial = dependencias[
        "VinculoCanalComercial"
    ]
    TiendaNubeWebhookLog = dependencias[
        "TiendaNubeWebhookLog"
    ]
    ml_config_faltante = dependencias[
        "ml_config_faltante"
    ]
    tn_config_faltante = dependencias[
        "tn_config_faltante"
    ]

    def resolver_acceso():
        try:
            membresia = resolver_tenant_usuario(
                usuario_actual(),
                UsuarioOrganizacion=(
                    UsuarioOrganizacion
                ),
                organizacion_id=session.get(
                    "organizacion_id"
                ),
            )
        except TenantError as error:
            return None, redirect(
                url_for(
                    "inicio",
                    error=str(error),
                )
            )

        organizacion = getattr(
            membresia,
            "organizacion",
            None,
        )

        if (
            getattr(
                membresia,
                "rol",
                None,
            )
            != "admin"
            or getattr(
                organizacion,
                "slug",
                None,
            )
            != (
                SLUG_ORGANIZACION_PLATAFORMA
            )
        ):
            return None, redirect(
                url_for("inicio")
            )

        session["organizacion_id"] = (
            membresia.organizacion_id
        )

        return organizacion, None

    @blueprint.route(
        "/admin/integraciones",
        methods=["GET"],
    )
    @login_required
    def panel():
        organizacion, respuesta = (
            resolver_acceso()
        )

        if respuesta is not None:
            return respuesta

        unidades_negocio = (
            UnidadNegocio.query
            .filter_by(
                organizacion_id=(
                    organizacion.id
                ),
                activa=True,
            )
            .order_by(
                UnidadNegocio.nombre.asc()
            )
            .all()
        )

        vinculos_ml = (
            obtener_vinculos_canal_tenant(
                organizacion,
                VinculoCanalComercial=(
                    VinculoCanalComercial
                ),
                canal=CANAL_MERCADO_LIBRE,
                solo_activos=False,
            )
        )

        cuentas_ml = [
            vinculo.mercado_libre_cuenta
            for vinculo in vinculos_ml
            if getattr(
                vinculo,
                "mercado_libre_cuenta",
                None,
            )
            is not None
        ]

        cuentas_tn = (
            cuentas_tienda_nube_tenant(
                organizacion,
                VinculoCanalComercial=(
                    VinculoCanalComercial
                ),
                solo_activas=False,
            )
        )

        cuenta_tn = (
            cuentas_tn[0]
            if cuentas_tn
            else None
        )

        hay_cuentas_ml_activas = any(
            str(
                getattr(
                    vinculo,
                    "estado",
                    "",
                )
                or ""
            ).strip().lower()
            == "activo"
            and getattr(
                vinculo,
                "mercado_libre_cuenta",
                None,
            )
            is not None
            and str(
                getattr(
                    vinculo.mercado_libre_cuenta,
                    "estado_conexion",
                    "",
                )
                or ""
            ).strip().lower()
            == "conectada"
            and bool(
                getattr(
                    vinculo.mercado_libre_cuenta,
                    "access_token",
                    None,
                )
            )
            for vinculo in vinculos_ml
        )

        ultimos_logs_tn = (
            TiendaNubeWebhookLog.query
            .order_by(
                TiendaNubeWebhookLog
                .fecha.desc()
            )
            .limit(10)
            .all()
        )

        return render_template(
            "admin_integraciones.html",
            unidades_negocio=(
                unidades_negocio
            ),
            vinculos_ml=vinculos_ml,
            cuentas_ml=cuentas_ml,
            hay_cuentas_ml_activas=(
                hay_cuentas_ml_activas
            ),
            faltantes=(
                ml_config_faltante()
            ),
            cuenta_tn=cuenta_tn,
            faltantes_tn=(
                tn_config_faltante()
            ),
            ultimos_logs_tn=(
                ultimos_logs_tn
            ),
            ok_feedback=(
                request.args.get("ok")
                or ""
            ).strip(),
            error=(
                request.args.get("error")
                or ""
            ).strip(),
        )

    return blueprint
