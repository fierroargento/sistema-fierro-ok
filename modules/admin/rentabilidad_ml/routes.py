"""Pantalla de ejemplos sintéticos: solo lectura, sin importación ni persistencia."""

import io
import json

from flask import Blueprint, abort, redirect, render_template, request, send_file, session, url_for

from services.escenarios_rentabilidad_ml import CUENTA_ENSAYO, ESCENARIOS, escenario_rentabilidad
from services.rentabilidad_ml_offline import analizar_rentabilidad
from services.tenant_context import TenantError, resolver_tenant_usuario


def crear_blueprint_rentabilidad_ml(*, dependencias):
    bp = Blueprint("admin_rentabilidad_ml", __name__)

    @bp.route("/admin/comercial/rentabilidad-ml", methods=["GET"])
    @dependencias["login_required"]
    def panel():
        usuario = dependencias["usuario_actual"]()
        try:
            membresia = resolver_tenant_usuario(usuario,
                UsuarioOrganizacion=dependencias["UsuarioOrganizacion"],
                organizacion_id=session.get("organizacion_id"))
        except TenantError:
            abort(403)
        if membresia.rol != "admin":
            abort(403)
        unidad = dependencias["UnidadNegocio"].query.filter_by(
            id=session.get("unidad_negocio_id"), organizacion_id=membresia.organizacion_id,
            activa=True).first()
        if unidad is None:
            return redirect(url_for("admin_comercial.panel", error="Seleccioná una unidad activa para el ensayo."))
        clave = request.args.get("caso", "simple")
        resultado = meta = None
        error = None
        estado_http = 200
        if request.args.get("analizar") == "1" or request.args.get("descargar") == "1":
            try:
                entrada, meta = escenario_rentabilidad(clave,
                    organizacion_id=membresia.organizacion_id, unidad_negocio_id=unidad.id)
                resultado = analizar_rentabilidad(entrada,
                    organizacion_id=membresia.organizacion_id, unidad_negocio_id=unidad.id,
                    cuenta_codigo=CUENTA_ENSAYO)
                if request.args.get("descargar") == "1":
                    evidencia = {"entrada": entrada, "resultado": resultado, "escenario": meta}
                    return send_file(io.BytesIO(json.dumps(evidencia, ensure_ascii=False,
                        sort_keys=True, indent=2).encode()), as_attachment=True,
                        download_name=f"rentabilidad_ml_ensayo_{clave}.json", mimetype="application/json")
            except ValueError as exc:
                error = str(exc)
                estado_http = 400
        elif clave not in ESCENARIOS:
            error = "Elegí uno de los ejemplos disponibles."
            estado_http = 400
        return render_template("admin_rentabilidad_ml.html", unidad_activa=unidad,
            escenarios=ESCENARIOS, clave=clave, resultado=resultado, meta=meta, error=error), estado_http

    return bp
