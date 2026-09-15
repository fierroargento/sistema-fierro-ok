"""Certificación de membresías y roles SaaS sin modificar identidades."""

import hashlib
import io
import json
import re


ROLES = {"admin", "carga", "despacho"}


def certificar_accesos(*, organizacion_id, membresias, usuario_actual):
    tenant = [x for x in membresias if x.organizacion_id == organizacion_id]
    hallazgos = []

    def agregar(codigo, membresia, detalle):
        hallazgos.append({
            "codigo": codigo,
            "membresia_id": getattr(membresia, "id", None),
            "usuario_id": getattr(membresia, "usuario_id", None),
            "detalle": detalle,
        })

    usuarios = set()
    nombres = set()
    administradores_activos = 0
    for membresia in tenant:
        usuario = getattr(membresia, "usuario", None)
        if usuario is None:
            agregar("identidad_huerfana", membresia, "La membresía no tiene una identidad autenticable.")
            continue
        if membresia.usuario_id in usuarios:
            agregar("membresia_duplicada", membresia, "El usuario aparece más de una vez en el tenant.")
        usuarios.add(membresia.usuario_id)
        username = str(getattr(usuario, "username", "") or "").strip().lower()
        if not username or not re.fullmatch(r"[a-z0-9._@+-]{3,80}", username):
            agregar("username_invalido", membresia, "El identificador de acceso está vacío o tiene formato inválido.")
        if username in nombres:
            agregar("username_duplicado", membresia, "Dos membresías resuelven al mismo nombre de usuario.")
        nombres.add(username)
        if not str(getattr(usuario, "password_hash", "") or "").strip():
            agregar("credencial_incompleta", membresia, "La identidad no tiene una credencial almacenada.")
        if membresia.rol not in ROLES:
            agregar("rol_invalido", membresia, "El rol no pertenece al contrato vigente.")
        if bool(membresia.activa) and not bool(getattr(usuario, "activo", False)):
            agregar("identidad_global_inactiva", membresia, "La membresía está activa pero la identidad global no.")
        if membresia.rol == "admin" and membresia.activa and getattr(usuario, "activo", False):
            administradores_activos += 1

        todas = list(getattr(usuario, "membresias_organizacion", []) or [])
        pares = set()
        predeterminadas = 0
        for vinculacion in todas:
            par = (vinculacion.usuario_id, vinculacion.organizacion_id)
            if par in pares:
                agregar("vinculo_tenant_duplicado", membresia, "La identidad repite una organización.")
            pares.add(par)
            if vinculacion.predeterminada and vinculacion.activa:
                predeterminadas += 1
        activas = sum(bool(x.activa) for x in todas)
        if activas and predeterminadas != 1:
            agregar("tenant_predeterminado_invalido", membresia, "La identidad debe tener exactamente un tenant activo predeterminado.")

    if not tenant:
        hallazgos.append({"codigo": "tenant_sin_membresias", "membresia_id": None, "usuario_id": None, "detalle": "La organización no tiene usuarios."})
    if administradores_activos == 0:
        hallazgos.append({"codigo": "tenant_sin_admin", "membresia_id": None, "usuario_id": None, "detalle": "La organización no conserva un administrador activo."})
    actual_id = getattr(usuario_actual, "id", None)
    acceso_actual = [x for x in tenant if x.usuario_id == actual_id and x.activa and x.rol == "admin"]
    if len(acceso_actual) != 1:
        hallazgos.append({"codigo": "sesion_admin_inconsistente", "membresia_id": None, "usuario_id": actual_id, "detalle": "La sesión no resuelve una única membresía administrativa activa."})

    resumen = {
        "membresias": len(tenant),
        "activas": sum(bool(x.activa) for x in tenant),
        "inactivas": sum(not bool(x.activa) for x in tenant),
        "administradores_activos": administradores_activos,
        "carga_activos": sum(x.activa and x.rol == "carga" for x in tenant),
        "despacho_activos": sum(x.activa and x.rol == "despacho" for x in tenant),
        "hallazgos": len(hallazgos),
    }
    resultado = {
        "organizacion_id": organizacion_id,
        "modo": "solo_lectura",
        "aprobada": not hallazgos,
        "resumen": resumen,
        "hallazgos": hallazgos,
        "controles": {
            "aislamiento_tenant": True,
            "credenciales_expuestas": 0,
            "sesiones_modificadas": 0,
            "membresias_modificadas": 0,
            "invitaciones_enviadas": 0,
            "escrituras": 0,
            "acciones_externas": 0,
        },
    }
    resultado["huella_control"] = hashlib.sha256(
        json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return resultado


def exportar_certificacion(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
