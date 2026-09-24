"""Ruta acotada para corregir datos de etiqueta sin exponer el pedido completo."""

from flask import Blueprint, abort, redirect, render_template, request, session, url_for

from services.edicion_datos_cliente import (
    aplicar_edicion_datos_cliente_para_etiqueta,
    puede_editar_datos_cliente_para_etiqueta,
)
from services.acceso_tenant_pedidos import obtener_pedido_tenant
from services.tenant_context import TenantError, resolver_tenant_usuario
from services.unidad_negocio_contexto import (
    UnidadNegocioError,
    resolver_unidad_activa,
)


def crear_blueprint_edicion_cliente(*, dependencias):
    blueprint = Blueprint("pedidos_edicion_cliente", __name__)
    db = dependencias["db"]
    Pedido = dependencias["Pedido"]
    login_required = dependencias["login_required"]
    usuario_actual = dependencias["usuario_actual"]
    registrar_auditoria = dependencias["registrar_auditoria"]
    normalizar_telefono = dependencias["normalizar_telefono"]
    UsuarioOrganizacion = dependencias["UsuarioOrganizacion"]
    UnidadNegocio = dependencias["UnidadNegocio"]

    @blueprint.route(
        "/pedido/<int:id>/corregir-datos-etiqueta",
        methods=["GET", "POST"],
    )
    @login_required
    def editar(id):
        usuario = usuario_actual()
        try:
            membresia = resolver_tenant_usuario(
                usuario,
                UsuarioOrganizacion=UsuarioOrganizacion,
                organizacion_id=session.get("organizacion_id"),
            )
        except TenantError:
            return redirect(url_for("inicio"))
        try:
            unidad, _unidades = resolver_unidad_activa(
                membresia.organizacion_id,
                session.get("unidad_negocio_id"),
                UnidadNegocio=UnidadNegocio,
            )
        except UnidadNegocioError:
            abort(403)
        session["unidad_negocio_id"] = unidad.id
        pedido = obtener_pedido_tenant(
            id,
            membresia.organizacion_id,
            Pedido=Pedido,
            unidad_negocio_id=unidad.id,
        )
        if pedido is None:
            abort(404)
        rol = str(getattr(membresia, "rol", "") or "").lower()

        if not puede_editar_datos_cliente_para_etiqueta(pedido, rol=rol):
            return redirect(url_for(
                "detalle_pedido",
                id=pedido.id,
                error="Los datos para etiqueta ya no pueden modificarse en esta etapa.",
            ))

        if request.method == "POST":
            resultado = aplicar_edicion_datos_cliente_para_etiqueta(
                pedido,
                request.form,
                rol=rol,
                organizacion_id=membresia.organizacion_id,
                unidad_negocio_id=unidad.id,
                normalizar_telefono_fn=normalizar_telefono,
            )

            if not resultado.permitida:
                return redirect(url_for("detalle_pedido", id=pedido.id))

            try:
                db.session.commit()
                registrar_auditoria(
                    "Corrigió datos para etiqueta",
                    entidad="pedido",
                    entidad_id=pedido.id,
                    detalle=(
                        "Campos modificados: " + ", ".join(resultado.cambios)
                        if resultado.cambios
                        else "Sin cambios reales."
                    ),
                )
            except Exception as error:
                db.session.rollback()
                return render_template(
                    "editar_datos_cliente_etiqueta.html",
                    pedido=pedido,
                    error=f"No se pudieron guardar los datos: {error}",
                )

            return redirect(url_for(
                "detalle_pedido",
                id=pedido.id,
                ok="Datos para etiqueta actualizados.",
            ))

        return render_template(
            "editar_datos_cliente_etiqueta.html",
            pedido=pedido,
            error="",
        )

    return blueprint
