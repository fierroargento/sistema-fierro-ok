"""
Rutas de autenticacion de la aplicacion.

La identidad se valida globalmente y el acceso operativo exige
una membresia activa dentro de una organizacion SaaS.
"""

from flask import (
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from datetime import datetime, timezone


def registrar_rutas_auth(
    app,
    *,
    dependencias,
):
    db = dependencias["db"]
    limiter = dependencias["limiter"]
    UsuarioSistema = dependencias[
        "UsuarioSistema"
    ]
    Auditoria = dependencias["Auditoria"]
    check_password_hash = dependencias[
        "check_password_hash"
    ]
    usuario_actual = dependencias[
        "usuario_actual"
    ]
    membresia_actual = dependencias[
        "membresia_actual"
    ]
    registrar_auditoria = dependencias[
        "registrar_auditoria"
    ]

    @app.route(
        "/login",
        methods=["GET", "POST"],
    )
    @limiter.limit("10 per minute")
    def login():
        if (
            usuario_actual()
            and membresia_actual() is not None
        ):
            return redirect(url_for("inicio"))

        error = (
            request.args.get("error")
            or ""
        ).strip()

        if request.method == "POST":
            username = (
                request.form.get("username")
                or ""
            ).strip()
            password = (
                request.form.get("password")
                or ""
            )
            usuario = (
                UsuarioSistema.query
                .filter_by(username=username)
                .first()
            )

            if (
                not usuario
                or not usuario.activo
                or not check_password_hash(
                    usuario.password_hash,
                    password,
                )
            ):
                error = (
                    "Usuario o contraseña incorrectos."
                )

                try:
                    auditoria = Auditoria(
                        username=(
                            username
                            or "sin_usuario"
                        ),
                        accion="Login fallido",
                        entidad="usuario",
                        entidad_id=(
                            username
                            or ""
                        ),
                        detalle=(
                            "Intento de ingreso rechazado"
                        ),
                        ip=(
                            request.headers.get(
                                "X-Forwarded-For"
                            )
                            or request.remote_addr
                            or ""
                        )[:80],
                        metodo=request.method,
                        path=request.path,
                    )
                    db.session.add(auditoria)
                    db.session.commit()
                except Exception:
                    db.session.rollback()

            else:
                session.clear()
                session.permanent = True
                session["user_id"] = usuario.id
                session["username"] = (
                    usuario.username
                )
                session["session_epoch"] = int(
                    getattr(usuario, "session_epoch", 0) or 0
                )
                session["session_issued_at"] = int(
                    datetime.now(timezone.utc).timestamp()
                )

                if membresia_actual() is None:
                    session.clear()
                    error = (
                        "El usuario no tiene acceso "
                        "a una organizacion activa."
                    )
                else:
                    registrar_auditoria(
                        "Login correcto",
                        entidad="usuario",
                        entidad_id=usuario.id,
                        detalle=(
                            f"Ingreso de "
                            f"{usuario.username}"
                        ),
                        usuario=usuario,
                    )
                    return redirect(
                        url_for("inicio")
                    )

        return render_template(
            "login.html",
            error=error,
        )

    @app.route("/logout", methods=["POST"])
    def logout():
        usuario = usuario_actual()
        if usuario is not None:
            usuario.session_epoch = int(
                getattr(usuario, "session_epoch", 0) or 0
            ) + 1
            db.session.commit()
        session.clear()
        return redirect(url_for("login"))
