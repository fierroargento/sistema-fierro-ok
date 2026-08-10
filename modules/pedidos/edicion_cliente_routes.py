"""Ruta acotada para corregir datos de etiqueta sin exponer el pedido completo."""

from flask import Blueprint, redirect, render_template, request, url_for

from services.edicion_datos_cliente import (
    aplicar_edicion_datos_cliente_para_etiqueta,
    puede_editar_datos_cliente_para_etiqueta,
)


def crear_blueprint_edicion_cliente(*, dependencias):
    blueprint = Blueprint("pedidos_edicion_cliente", __name__)
    db = dependencias["db"]
    Pedido = dependencias["Pedido"]
    login_required = dependencias["login_required"]
    usuario_actual = dependencias["usuario_actual"]
    registrar_auditoria = dependencias["registrar_auditoria"]
    normalizar_telefono = dependencias["normalizar_telefono"]

    @blueprint.route(
        "/pedido/<int:id>/corregir-datos-etiqueta",
        methods=["GET", "POST"],
    )
    @login_required
    def editar(id):
        pedido = Pedido.query.get_or_404(id)
        usuario = usuario_actual()
        rol = str(getattr(usuario, "rol", "") or "").lower()

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
