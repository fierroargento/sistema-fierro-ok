from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from services import consulta_padron_arca as arca

CUIT = '20224107030'


def persona(cuit=CUIT, extra='', juridica=False):
    nombre = '<razonSocial>Empresa &amp; Cía</razonSocial>' if juridica else '<apellido>Apellido</apellido><nombre>Nombre</nombre>'
    tipo = 'JURIDICA' if juridica else 'FISICA'
    return f'''<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><r:getPersona_v2Response xmlns:r="http://a5.soap.ws.server.puc.sr/"><personaReturn><datosGenerales><idPersona>{cuit}</idPersona><estadoClave>ACTIVO</estadoClave><tipoPersona>{tipo}</tipoPersona>{nombre}<domicilioFiscal><direccion>Calle 123</direccion><localidad>Viedma</localidad><descripcionProvincia>Río Negro</descripcionProvincia><codPostal>8500</codPostal></domicilioFiscal></datosGenerales>{extra}</personaReturn></r:getPersona_v2Response></s:Body></s:Envelope>'''.encode()


def ticket(vigente=True):
    fecha = datetime.now(timezone.utc) + timedelta(hours=1 if vigente else -1)
    return f'<loginTicketResponse><header><expirationTime>{fecha.isoformat()}</expirationTime></header><credentials><token>secreto-token</token><sign>secreto-sign</sign></credentials></loginTicketResponse>'


@pytest.mark.parametrize('cuit', ['20-22410703-0', CUIT, '20.22410703.0'])
def test_normaliza_cuit(cuit):
    assert arca.normalizar_cuit(cuit) == CUIT


@pytest.mark.parametrize('cuit', ['', '1234', '20224107031', 'abc20224107030', '00000000000'])
def test_rechaza_cuit_invalido_sin_red(cuit, monkeypatch):
    red = Mock(); monkeypatch.setattr(arca.requests, 'post', red)
    with pytest.raises(arca.ErrorPadron): arca.consultar_cuit(7, cuit)
    red.assert_not_called()


def test_laboratorio_bloquea_aun_con_otros_flags_habilitados(monkeypatch):
    for clave, valor in {'MODO_LABORATORIO_DESCONECTADO':'true','SISTEMA_FIERRO_ENTORNO':'staging','CONEXIONES_EXTERNAS_HABILITADAS':'true','ARCA_CONEXION_HABILITADA':'true'}.items():
        monkeypatch.setenv(clave, valor)
    red, config = Mock(), Mock()
    monkeypatch.setattr(arca.requests, 'post', red); monkeypatch.setattr(arca, 'configuracion_tenant', config)
    with pytest.raises(arca.ErrorPadron) as error: arca.consultar_cuit(7, CUIT)
    assert error.value.codigo == 'desconectado'
    red.assert_not_called(); config.assert_not_called()


@pytest.mark.parametrize('juridica', [False, True])
def test_normaliza_solo_datos_fiscales_reales(juridica):
    datos = arca.interpretar_persona(persona(juridica=juridica), CUIT)
    assert datos['razon_social'] == ('Empresa & Cía' if juridica else 'Apellido Nombre')
    assert datos['domicilio'] == 'Calle 123' and datos['codigo_postal'] == '8500'
    assert 'email' not in datos and 'telefono' not in datos and 'persona_contacto' not in datos


@pytest.mark.parametrize('respuesta', [b'<html>error</html>', persona('30540889356'), b'<!DOCTYPE x><x/>', b'<malformado', persona().replace(b'ACTIVO', b'INACTIVO'), b'<Envelope><Fault><faultstring>secreto-token</faultstring></Fault></Envelope>'])
def test_no_acepta_datos_inverificables_ni_expone_respuesta(respuesta):
    with pytest.raises(arca.ErrorPadron) as error: arca.interpretar_persona(respuesta, CUIT)
    assert 'secreto' not in str(error.value)


@pytest.mark.parametrize('valor', ['', ticket(False), '<x/>'])
def test_autorizacion_ausente_o_vencida(valor):
    with pytest.raises(arca.ErrorPadron): arca.leer_ticket(valor)


def test_consulta_usa_solo_endpoint_oficial_autorizado_y_no_filtra_credenciales(monkeypatch):
    monkeypatch.setattr(arca, 'conexiones_externas_habilitadas', lambda canal: True)
    config = Mock(return_value=(arca.ENDPOINTS['homologacion'], CUIT, ticket()))
    monkeypatch.setattr(arca, 'configuracion_tenant', config)
    red = Mock(return_value=SimpleNamespace(status_code=200, content=persona()))
    monkeypatch.setattr(arca.requests, 'post', red)
    datos = arca.consultar_cuit(7, CUIT)
    config.assert_called_once_with(7)
    assert datos['cuit'] == CUIT
    assert red.call_args.kwargs['allow_redirects'] is False and red.call_args.kwargs['timeout'] == (3, 8)
    assert 'secreto' not in str(datos)
    red.side_effect = requests.Timeout('secreto-token')
    with pytest.raises(arca.ErrorPadron) as error: arca.consultar_cuit(7, CUIT)
    assert 'secreto' not in str(error.value)


def test_respuesta_web_desconectada_es_json_y_no_se_cachea(monkeypatch):
    from flask import Flask
    from services.consulta_padron_web import responder_consulta_padron
    monkeypatch.setenv('MODO_LABORATORIO_DESCONECTADO', 'true')
    app = Flask(__name__)
    with app.test_request_context('/', method='POST', data={'cuit':CUIT}):
        respuesta = responder_consulta_padron(7)
    assert respuesta.status_code == 503 and respuesta.json['codigo'] == 'desconectado'
    assert respuesta.headers['Cache-Control'] == 'no-store'
