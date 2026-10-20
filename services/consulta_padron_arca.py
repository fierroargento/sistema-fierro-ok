"""Consulta de constancia ARCA, compartida por clientes y proveedores.

No guarda personas ni habilita facturación. Reutiliza EntidadFiscal y
ConfiguracionFiscal.token_env: XML loginTicketResponse vigente de WSAA para
ws_sr_constancia_inscripcion, administrado fuera de este flujo de alta.
"""
import os
import re
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import requests
from services.seguridad_entorno import conexiones_externas_habilitadas

ENDPOINTS = {
    'homologacion': 'https://awshomo.arca.gov.ar/sr-padron/webservices/personaServiceA5',
    'produccion': 'https://aws.arca.gov.ar/sr-padron/webservices/personaServiceA5',
}


class ErrorPadron(ValueError):
    def __init__(self, mensaje, codigo='no_disponible', status=503):
        super().__init__(mensaje)
        self.codigo = codigo
        self.status = status


def normalizar_cuit(valor):
    valor = str(valor or '').strip()
    if not re.fullmatch(r'[0-9 .-]{11,20}', valor):
        raise ErrorPadron('Ingresá un CUIT válido de 11 dígitos.', 'cuit_invalido', 400)
    cuit = re.sub(r'[ .-]', '', valor)
    if len(cuit) != 11 or len(set(cuit)) == 1:
        raise ErrorPadron('Ingresá un CUIT válido de 11 dígitos.', 'cuit_invalido', 400)
    suma = sum(int(n) * peso for n, peso in zip(cuit[:10], (5,4,3,2,7,6,5,4,3,2)))
    digito = 11 - suma % 11
    digito = 0 if digito == 11 else 9 if digito == 10 else digito
    if digito != int(cuit[-1]):
        raise ErrorPadron('El dígito verificador del CUIT no es válido.', 'cuit_invalido', 400)
    return cuit


def _xml(contenido):
    if isinstance(contenido, str):
        contenido = contenido.encode('utf-8')
    if len(contenido) > 2_000_000 or b'<!DOCTYPE' in contenido.upper() or b'<!ENTITY' in contenido.upper():
        raise ErrorPadron('ARCA devolvió una respuesta no válida.', 'respuesta_invalida', 502)
    try:
        return ET.fromstring(contenido)
    except (ET.ParseError, ValueError):
        raise ErrorPadron('No se pudo interpretar la respuesta de ARCA.', 'respuesta_invalida', 502) from None


def _nodo(nodo, nombre):
    return next((n for n in nodo.iter() if n.tag.split('}')[-1] == nombre), None)


def _texto(nodo, nombre):
    item = _nodo(nodo, nombre)
    return (item.text or '').strip() if item is not None else ''


def leer_ticket(xml):
    if not xml:
        raise ErrorPadron('Falta la autorización de ARCA. Podés continuar con la carga manual.', 'autorizacion_pendiente')
    raiz = _xml(xml)
    try:
        vencimiento = datetime.fromisoformat(_texto(raiz, 'expirationTime').replace('Z', '+00:00'))
        if vencimiento.tzinfo is None or vencimiento <= datetime.now(timezone.utc):
            raise ValueError()
        token, sign = _texto(raiz, 'token'), _texto(raiz, 'sign')
        if not token or not sign:
            raise ValueError()
    except ValueError:
        raise ErrorPadron('La autorización de ARCA falta o venció. Podés continuar con la carga manual.', 'autorizacion_pendiente') from None
    return token, sign


def interpretar_persona(xml, cuit):
    raiz = _xml(xml)
    if _nodo(raiz, 'Fault') is not None:
        raise ErrorPadron('ARCA no pudo completar la consulta. Revisá la autorización o intentá más tarde.', 'consulta_rechazada', 502)
    datos = _nodo(raiz, 'datosGenerales')
    if datos is None or _texto(datos, 'idPersona') != cuit:
        raise ErrorPadron('ARCA no devolvió datos verificables para este CUIT.', 'sin_datos', 404)
    razon = _texto(datos, 'razonSocial') or ' '.join(filter(None, (_texto(datos, 'apellido'), _texto(datos, 'nombre'))))
    if not razon or _texto(datos, 'estadoClave') != 'ACTIVO':
        raise ErrorPadron('El CUIT no figura activo o su identificación está incompleta en ARCA.', 'sin_datos', 422)
    domicilio = _nodo(datos, 'domicilioFiscal')
    return {
        'cuit': cuit, 'razon_social': razon,
        'tipo': 'empresa' if _texto(datos, 'tipoPersona') == 'JURIDICA' else 'persona',
        'domicilio': _texto(domicilio, 'direccion') if domicilio is not None else '',
        'localidad': _texto(domicilio, 'localidad') if domicilio is not None else '',
        'provincia': _texto(domicilio, 'descripcionProvincia') if domicilio is not None else '',
        'codigo_postal': _texto(domicilio, 'codPostal') if domicilio is not None else '',
        'fuente': 'ARCA · Constancia de inscripción',
    }


def configuracion_tenant(organizacion_id):
    # Selección explícita, aislada por organización. No se elige el primer CUIT.
    from models.configuracion_fiscal import ConfiguracionFiscal
    from models.entidad_fiscal import EntidadFiscal
    elegido = os.getenv(f'ARCA_PADRON_ENTIDAD_{int(organizacion_id)}', '')
    if not elegido.isdigit():
        raise ErrorPadron('La consulta ARCA todavía no está configurada. Podés completar los datos manualmente.', 'configuracion_pendiente')
    configuracion = ConfiguracionFiscal.query.filter_by(organizacion_id=organizacion_id, entidad_fiscal_id=int(elegido), proveedor='arca').first()
    entidad = EntidadFiscal.query.filter_by(organizacion_id=organizacion_id, id=int(elegido)).first()
    if configuracion is None or entidad is None or configuracion.ambiente not in ENDPOINTS or not configuracion.token_env:
        raise ErrorPadron('Falta preparar la autorización del padrón de ARCA.', 'configuracion_pendiente')
    return ENDPOINTS[configuracion.ambiente], normalizar_cuit(entidad.cuit), os.getenv(configuracion.token_env, '')


def consultar_cuit(organizacion_id, valor):
    cuit = normalizar_cuit(valor)
    if not conexiones_externas_habilitadas('ARCA'):
        raise ErrorPadron('Consulta ARCA deshabilitada en este entorno. Podés completar los datos manualmente.', 'desconectado')
    endpoint, representada, ticket = configuracion_tenant(organizacion_id)
    token, sign = leer_ticket(ticket)
    sobre = ET.Element('soap:Envelope', {'xmlns:soap': 'http://schemas.xmlsoap.org/soap/envelope/', 'xmlns:a5': 'http://a5.soap.ws.server.puc.sr/'})
    body = ET.SubElement(sobre, 'soap:Body')
    operacion = ET.SubElement(body, 'a5:getPersona_v2')
    for clave, dato in [('token', token), ('sign', sign), ('cuitRepresentada', representada), ('idPersona', cuit)]:
        ET.SubElement(operacion, clave).text = dato
    try:
        respuesta = requests.post(endpoint, data=ET.tostring(sobre, encoding='utf-8', xml_declaration=True),
            headers={'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': '""'}, timeout=(3, 8), allow_redirects=False)
        if respuesta.status_code != 200:
            raise ErrorPadron('ARCA no pudo completar la consulta. Intentá más tarde o completá los datos manualmente.', 'servicio_no_disponible', 502)
        return interpretar_persona(respuesta.content, cuit)
    except requests.RequestException:
        raise ErrorPadron('No se pudo comunicar con ARCA. Tus datos se conservaron; podés continuar manualmente.', 'servicio_no_disponible', 502) from None
