"""Ejemplos y análisis de archivos offline, sin persistencia ni conexiones."""

import io
import json

from flask import Blueprint, abort, redirect, render_template, request, send_file, session, url_for

from services.escenarios_rentabilidad_ml import CUENTA_ENSAYO, ESCENARIOS, escenario_rentabilidad
from services.rentabilidad_ml_offline import analizar_rentabilidad
from services.archivo_rentabilidad_ml import MAX_ARCHIVO_BYTES, analizar_archivo
from werkzeug.exceptions import RequestEntityTooLarge
from services.tenant_context import TenantError, resolver_tenant_usuario


def crear_blueprint_rentabilidad_ml(*, dependencias):
    bp = Blueprint("admin_rentabilidad_ml", __name__)

    def contexto_activo():
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
        return membresia, unidad

    def exportacion(evidencia, nombre):
        return send_file(io.BytesIO(json.dumps(evidencia, ensure_ascii=False,
            sort_keys=True, indent=2).encode()), as_attachment=True,
            download_name=nombre, mimetype="application/json")

    @bp.after_request
    def no_cache(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @bp.route("/admin/comercial/rentabilidad-ml", methods=["GET"])
    @dependencias["login_required"]
    def panel():
        contexto = contexto_activo()
        if not isinstance(contexto, tuple):
            return contexto
        membresia, unidad = contexto
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
                    return exportacion(evidencia, f"rentabilidad_ml_ensayo_{clave}.json")
            except ValueError as exc:
                error = str(exc)
                estado_http = 400
        elif clave not in ESCENARIOS:
            error = "Elegí uno de los ejemplos disponibles."
            estado_http = 400
        return render_template("admin_rentabilidad_ml.html", unidad_activa=unidad,
            escenarios=ESCENARIOS, clave=clave, resultado=resultado, meta=meta, error=error), estado_http

    @bp.route("/admin/comercial/rentabilidad-ml/archivo", methods=["POST"])
    @dependencias["login_required"]
    def archivo():
        contexto = contexto_activo()
        if not isinstance(contexto, tuple):
            return contexto
        membresia, unidad = contexto
        resultado = meta = evidencia = None
        error = None
        estado_http = 200
        try:
            if request.mimetype != "application/json":
                raise ValueError("Seleccioná el JSON y usá Analizar archivo con JavaScript habilitado.")
            if request.content_length is not None and request.content_length > MAX_ARCHIVO_BYTES:
                raise ValueError("Seleccioná un JSON de hasta 2 MB.")
            entrada, resultado = analizar_archivo(request.stream.read(MAX_ARCHIVO_BYTES + 1),
                organizacion_id=membresia.organizacion_id, unidad_negocio_id=unidad.id,
                cuenta_codigo=CUENTA_ENSAYO)
            meta = {"nombre": "Archivo offline", "descripcion": resultado["referencia_venta"],
                "contexto": "Datos declarados; fuente no verificada con ML/MP",
                "precio_objetivo_centavos": None, "criterio_objetivo": None}
            evidencia = {"entrada": entrada, "resultado": resultado, "escenario": meta}
        except ValueError as exc:
            error = str(exc)
            estado_http = 400
        except RequestEntityTooLarge:
            error = "El archivo o formulario excede el tamaño permitido. Usá un JSON de hasta 2 MB."
            estado_http = 413
        return render_template("admin_rentabilidad_ml.html", unidad_activa=unidad,
            escenarios=ESCENARIOS, clave="simple", resultado=resultado, meta=meta,
            error=error, desde_archivo=True, evidencia_archivo=evidencia), estado_http

    return bp
