"""Panel tenant de compras preparatorias sin impacto automático."""

from flask import Blueprint, redirect, render_template, request, session, url_for

from services.compras_consultas import obtener_panel_compras
from services.compras_nucleo import (
    cambiar_estado_orden,
    crear_orden,
    crear_proveedor,
    preparar_recepcion,
)
from services.tenant_context import TenantError, resolver_tenant_usuario


def crear_blueprint_compras(*, dependencias):
    blueprint = Blueprint("admin_compras", __name__)
    db = dependencias["db"]
    modelos = dependencias["modelos"]

    def acceso():
        usuario = dependencias["usuario_actual"]()
        try:
            membresia = resolver_tenant_usuario(
                usuario,
                UsuarioOrganizacion=dependencias["UsuarioOrganizacion"],
                organizacion_id=session.get("organizacion_id"),
            )
        except TenantError as error:
            return None, None, None, redirect(url_for("inicio", error=str(error)))
        if membresia.rol != "admin":
            return None, None, None, redirect(url_for("inicio"))
        unidades = modelos["UnidadNegocio"].query.filter_by(
            organizacion_id=membresia.organizacion_id, activa=True,
        ).order_by(modelos["UnidadNegocio"].nombre.asc()).all()
        unidad_id = session.get("unidad_negocio_id")
        unidad = next((item for item in unidades if item.id == unidad_id), None)
        if unidad is None and unidades:
            unidad = unidades[0]
            session["unidad_negocio_id"] = unidad.id
        if unidad is None:
            return usuario, membresia.organizacion, None, redirect(url_for("admin_estructura.panel"))
        session["organizacion_id"] = membresia.organizacion_id
        return usuario, membresia.organizacion, unidad, None

    @blueprint.route("/admin/compras")
    @dependencias["login_required"]
    def panel():
        _usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        datos = obtener_panel_compras(organizacion.id, unidad.id, modelos=modelos)
        return render_template(
            "admin_compras.html", organizacion=organizacion, unidad_activa=unidad,
            ok_feedback=(request.args.get("ok") or "").strip(),
            error=(request.args.get("error") or "").strip(), **datos,
        )

    @blueprint.route("/admin/compras/guardar", methods=["POST"])
    @dependencias["login_required"]
    def guardar():
        usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        accion = (request.form.get("accion") or "").strip()
        try:
            if accion == "crear_proveedor":
                creado = crear_proveedor(
                    request.form, organizacion_id=organizacion.id,
                    ProveedorCompra=modelos["ProveedorCompra"], db_session=db.session,
                )
                mensaje = f"Proveedor {creado.codigo} creado."
            elif accion == "crear_orden":
                proveedor = modelos["ProveedorCompra"].query.filter_by(
                    id=int(request.form.get("proveedor_id")), organizacion_id=organizacion.id,
                ).first()
                if proveedor is None:
                    raise ValueError("El proveedor no pertenece al tenant activo.")
                insumo_id = request.form.get("insumo_id")
                insumo = None
                if insumo_id:
                    insumo = modelos["InsumoProductivo"].query.filter_by(
                        id=int(insumo_id), organizacion_id=organizacion.id,
                    ).first()
                    if insumo is None:
                        raise ValueError("El insumo no pertenece al tenant activo.")
                creada = crear_orden(
                    request.form, organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id, proveedor=proveedor, insumo=insumo,
                    OrdenCompra=modelos["OrdenCompra"],
                    OrdenCompraItem=modelos["OrdenCompraItem"],
                    db_session=db.session, usuario_id=getattr(usuario, "id", None),
                )
                mensaje = f"Orden {creada.numero} creada como borrador."
            elif accion == "cambiar_estado":
                orden = modelos["OrdenCompra"].query.filter_by(
                    id=int(request.form.get("orden_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                ).first()
                if orden is None:
                    raise ValueError("La orden no pertenece al tenant y unidad activos.")
                cambiar_estado_orden(
                    orden, (request.form.get("estado") or "").strip(),
                    organizacion_id=organizacion.id, db_session=db.session,
                )
                mensaje = f"Orden {orden.numero} actualizada a {orden.estado}."
            elif accion == "preparar_recepcion":
                orden = modelos["OrdenCompra"].query.filter_by(
                    id=int(request.form.get("orden_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                ).first()
                if orden is None:
                    raise ValueError("La orden no pertenece al tenant y unidad activos.")
                recepcion = preparar_recepcion(
                    request.form, orden=orden, organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                    RecepcionCompra=modelos["RecepcionCompra"],
                    RecepcionCompraItem=modelos["RecepcionCompraItem"],
                    db_session=db.session, usuario_id=getattr(usuario, "id", None),
                )
                mensaje = f"Recepción {recepcion.numero} preparada sin impacto en stock o costos."
            else:
                raise ValueError("La acción de compras no es válida.")
            dependencias["registrar_auditoria"](
                f"Compras: {accion}", entidad="compras", detalle=mensaje,
            )
            return redirect(url_for("admin_compras.panel", ok=mensaje))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for("admin_compras.panel", error=str(error)))

    return blueprint
