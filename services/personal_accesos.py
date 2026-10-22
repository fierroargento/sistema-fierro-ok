"""Accesos del legajo: cuenta auténtica existente y código de alarma cifrado."""
import base64
import hashlib
import json
import re
from flask import current_app
from cryptography.fernet import Fernet, InvalidToken
from models.personal_administrativo import PersonalAcceso
from models.usuario_organizacion import UsuarioOrganizacion
from services.usuarios_admin import crear_usuario_tenant, editar_membresia_tenant

SECRETOS = {'password','password_confirm','codigo_alarma'}


def formulario_publico(formulario):
    datos={k:v for k,v in formulario.items() if k not in SECRETOS}
    if hasattr(formulario,'getlist') and 'inicial_dias' in formulario:datos['inicial_dias']=formulario.getlist('inicial_dias')
    return datos


def _cifrador(organizacion_id):
    clave = current_app.secret_key
    if not clave:
        raise ValueError('Falta configurar la clave estable del sistema para proteger el código de alarma.')
    material = clave.encode() if isinstance(clave,str) else clave
    contexto = f'personal-alarma-v1:{organizacion_id}:'.encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(contexto+material).digest()))


def estado_accesos(e, db_session):
    from sqlalchemy import inspect
    if not inspect(db_session.get_bind()).has_table(PersonalAcceso.__tablename__):
        return {'revision_accesos':'0','usuario_sistema':'','tiene_codigo_alarma':False,'usuario_habilitado':False}
    acceso=db_session.get(PersonalAcceso,e.id)
    mem=acceso.membresia if acceso else None
    # La pertenencia se valida al escribir y también al presentar el vínculo.
    if mem and mem.organizacion_id != e.organizacion_id:mem=None
    return {'revision_accesos':str(acceso.revision if acceso else 0),
            'usuario_sistema':mem.usuario.username if mem else '',
            'tiene_codigo_alarma':bool(acceso and acceso.codigo_alarma_cifrado),
            'usuario_habilitado':bool(mem and mem.activa and mem.usuario.activo)}


def guardar_accesos(e, form, *, organizacion, modelos, db_session, creador):
    if form.get('accesos_presentados') != '1':return
    acceso=db_session.get(PersonalAcceso,e.id)
    actual=str(acceso.revision if acceso else 0)
    if str(form.get('revision_accesos') or '0') != actual:
        raise ValueError('Los accesos cambiaron mientras editabas. Recargá el legajo antes de guardar.')
    accion=form.get('acceso_accion','conservar')
    if accion not in {'conservar','crear','vincular'}:raise ValueError('Elegí una opción de usuario válida.')
    password=str(form.get('password') or '')
    if password:
        if len(password)>128:raise ValueError('La contraseña admite hasta 128 caracteres.')
        if password != form.get('password_confirm'):raise ValueError('Las contraseñas no coinciden.')
    codigo=str(form.get('codigo_alarma') or '')
    quitar=form.get('quitar_codigo_alarma')=='1'
    if codigo and quitar:raise ValueError('Elegí cargar un código de alarma o quitar el actual.')
    if codigo and not re.fullmatch(r'[0-9A-Za-z#*_-]{4,32}',codigo):
        raise ValueError('El código de alarma admite de 4 a 32 caracteres: letras, números, #, *, guion y guion bajo.')
    mem=acceso.membresia if acceso else None
    if mem and mem.organizacion_id!=e.organizacion_id:raise ValueError('El usuario no pertenece a la organización.')
    if accion in {'crear','vincular'} and mem:
        raise ValueError('El empleado ya tiene un usuario vinculado. Conservá esa cuenta para mantener su identidad.')
    if accion=='crear':
        username=str(form.get('username') or '').strip()
        if not username or len(username)>80:raise ValueError('Completá un usuario de hasta 80 caracteres.')
        if not password:raise ValueError('Completá la contraseña de la nueva cuenta.')
        mem,_=crear_usuario_tenant({'username':username,'nombre':e.nombre[:120],
            'password':password,'rol':'carga'},organizacion=organizacion,
            UsuarioSistema=modelos['UsuarioSistema'],UsuarioOrganizacion=modelos['UsuarioOrganizacion'],
            db_session=db_session,creador=creador,commit=False)
        # Preparar credenciales no habilita permisos operativos durante la construcción.
        mem.activa=False;mem.usuario.activo=False
    elif accion=='vincular':
        ident=str(form.get('usuario_organizacion_id') or '')
        mem=db_session.query(UsuarioOrganizacion).filter_by(id=int(ident),organizacion_id=e.organizacion_id).with_for_update().first() if ident.isdecimal() else None
        if mem is None:raise ValueError('El usuario elegido no pertenece a la organización.')
        if db_session.query(PersonalAcceso.empleado_id).filter_by(usuario_organizacion_id=mem.id).first():
            raise ValueError('Esa cuenta ya está vinculada a otro empleado.')
    if password and accion!='crear':
        if mem is None:raise ValueError('Vinculá un usuario antes de establecer su contraseña.')
        editar_membresia_tenant(mem.id,{'nombre':mem.usuario.nombre,'rol':mem.rol,'password':password},
            organizacion=organizacion,UsuarioOrganizacion=modelos['UsuarioOrganizacion'],db_session=db_session,commit=False)
    cambio=accion!='conservar' or bool(password) or bool(codigo) or quitar
    if not cambio:return
    if acceso is None:acceso=PersonalAcceso(empleado_id=e.id,revision=0);db_session.add(acceso)
    if mem:acceso.usuario_organizacion_id=mem.id
    if codigo:
        payload=json.dumps({'empleado_id':e.id,'codigo':codigo}).encode()
        acceso.codigo_alarma_cifrado=_cifrador(e.organizacion_id).encrypt(payload)
    elif quitar:acceso.codigo_alarma_cifrado=None
    acceso.revision+=1
    db_session.flush()


def leer_codigo_alarma(e, db_session):
    acceso=db_session.get(PersonalAcceso,e.id)
    if not acceso or not acceso.codigo_alarma_cifrado:return ''
    try:
        payload=json.loads(_cifrador(e.organizacion_id).decrypt(acceso.codigo_alarma_cifrado))
        if payload.get('empleado_id')!=e.id:raise ValueError()
        return payload['codigo']
    except (InvalidToken,ValueError,KeyError,TypeError) as error:
        raise ValueError('No se pudo abrir el código de alarma. Revisá la clave del sistema antes de reemplazarlo.') from error
