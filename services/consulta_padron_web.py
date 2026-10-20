"""Respuesta común; cada blueprint conserva su control de acceso y CSRF."""
from flask import jsonify, request
from services.consulta_padron_arca import consultar_cuit, ErrorPadron


def responder_consulta_padron(organizacion_id):
    try:
        datos = consultar_cuit(organizacion_id, request.form.get('cuit'))
        respuesta = jsonify(ok=True, datos=datos)
    except ErrorPadron as error:
        respuesta = jsonify(ok=False, codigo=error.codigo, mensaje=str(error))
        respuesta.status_code = error.status
    respuesta.headers['Cache-Control'] = 'no-store'
    return respuesta
