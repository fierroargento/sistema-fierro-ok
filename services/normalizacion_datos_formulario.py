"""Formato común de datos de formularios humanos; no toca APIs, enums ni secretos."""
import re
from services.telefonos import normalizar_telefono_service

MAYUSCULAS=frozenset('nombre apellido nombres apellidos nombre_apellido nombre_completo razon_social nombre_fantasia domicilio direccion direccion_envio domicilio_fiscal localidad ciudad provincia barrio pais codigo_postal persona_contacto contacto_emergencia sector puesto categoria convenio modalidad ubicacion_trabajo observacion observaciones descripcion detalle motivo tareas_habituales observacion_sueldo observacion_horario observacion_logistica nombre_comercial nombre_catalogo nombre_operacion nombre_promocion autorizado_nombre receptor_nombre sucursal_nombre unidad_nombre atributo_nombre certificacion_observacion observacion_agregado_pendiente observacion_devolucion observacion_distribucion observacion_distribucion_costo observacion_reclamo observacion_reclamo_ml'.split())
TELEFONOS=frozenset('telefono telefono_contacto telefono_cliente telefono_destinatario telefono_envio telefono_whatsapp telefono_alternativo celular celular_contacto autorizado_telefono'.split())
FISCALES=frozenset({'cuit','cuil','cuit_emisor','cuit_receptor','cuit_destinatario'})

def telefono(valor):
    valor=str(valor or '').strip()
    if not valor:return ''
    if not re.fullmatch(r'[+0-9\s().-]+',valor):raise ValueError('Usá un teléfono sin letras ni internos; incluí la característica.')
    digitos=re.sub(r'\D','',valor)
    if valor.startswith('+') and not digitos.startswith('54'):
        if re.fullmatch(r'[1-9][0-9]{6,14}',digitos):return '+'+digitos
        raise ValueError('Revisá el teléfono internacional.')
    # Diez dígitos nacionales ya completos: no reinterpretar un prefijo local como país.
    normal='549'+digitos if len(digitos)==10 and not valor.startswith('+') else normalizar_telefono_service(valor)
    if not re.fullmatch(r'549[0-9]{10}',normal):raise ValueError('Completá el teléfono argentino con característica y 10 dígitos nacionales. Ej.: +549 2920123456.')
    return normal

def fiscal(valor):
    valor=str(valor or '').strip()
    if not valor:return ''
    if not re.fullmatch(r'[0-9\s.-]+',valor):raise ValueError('CUIT/CUIL: usá sólo números, espacios o guiones.')
    n=re.sub(r'\D','',valor)
    if len(n)!=11:raise ValueError('CUIT/CUIL: completá los 11 dígitos.')
    return n

def normalizar(nombre,valor):
    if nombre in MAYUSCULAS:return valor.upper()
    if nombre in TELEFONOS:return telefono(valor)
    if nombre in FISCALES:return fiscal(valor)
    if nombre=='documento' and len(re.sub(r'\D','',valor))==11:return fiscal(valor)
    return valor

def registrar(app):
    from flask import request,render_template,jsonify
    from werkzeug.datastructures import ImmutableMultiDict
    if app.extensions.get('normalizacion_datos_formulario'):return
    app.extensions['normalizacion_datos_formulario']=True
    @app.context_processor
    def config():return dict(normalizacion_datos_config=dict(mayusculas=sorted(MAYUSCULAS),telefonos=sorted(TELEFONOS),fiscales=sorted(FISCALES)))
    @app.before_request
    def datos_formulario():
        # Integraciones y cuerpos JSON no son formularios de carga humana.
        if request.method not in {'POST','PUT','PATCH'} or request.is_json or request.path.startswith(('/api/','/webhook')) or '/webhook' in request.path:return
        if request.mimetype not in {'application/x-www-form-urlencoded','multipart/form-data'}:return
        pares=[];errores=[]
        for nombre,valores in request.form.lists():
            for valor in valores:
                try:
                    # Dirección financiera es un enum, no un domicilio.
                    salida=valor if nombre=='direccion' and request.form.get('accion')=='registrar_movimiento' else normalizar(nombre,valor)
                    pares.append((nombre,salida))
                except ValueError as e:errores.append(nombre.replace('_',' ').capitalize()+': '+str(e))
        if errores:
            if request.headers.get('Accept','').startswith('application/json'):return jsonify(error=' '.join(errores)),400
            return render_template('datos_formulario_error.html',errores=errores),400
        request.form=ImmutableMultiDict(pares)
        request.__dict__.pop('values',None)
