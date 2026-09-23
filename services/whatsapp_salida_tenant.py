"""Resolución offline de credenciales WhatsApp por vínculo empresarial.

Los secretos permanecen en variables de entorno; la base sólo identifica el
``phone_number_id``. Este módulo no abre red, no persiste y no habilita envíos.
"""

from dataclasses import dataclass, field
import hashlib
import re


class ConfiguracionSalidaWhatsAppError(ValueError):
    pass


@dataclass(frozen=True)
class ConfiguracionSalidaWhatsApp:
    organizacion_id: int
    unidad_negocio_id: int
    phone_number_id: str
    token: str = field(repr=False)
    api_url: str


def sufijo_credencial(phone_number_id):
    phone = str(phone_number_id or "").strip()
    if not phone:
        raise ConfiguracionSalidaWhatsAppError("Falta phone_number_id.")
    legible = re.sub(r"[^A-Za-z0-9]", "_", phone).strip("_").upper()[:24]
    huella = hashlib.sha256(phone.encode()).hexdigest()[:12].upper()
    return f"{legible}_{huella}" if legible else huella


def nombres_variables_credencial(phone_number_id):
    sufijo = sufijo_credencial(phone_number_id)
    return {
        "token": f"WHATSAPP_TOKEN_{sufijo}",
    }


def _valor(registro, nombre, default=None):
    if isinstance(registro, dict):
        return registro.get(nombre, default)
    return getattr(registro, nombre, default)


def resolver_configuracion_salida_whatsapp(
    vinculos, *, organizacion_id, unidad_negocio_id, environ,
):
    candidatos = [
        vinculo for vinculo in (vinculos or [])
        if str(_valor(vinculo, "canal", "whatsapp") or "").lower() == "whatsapp"
        and str(_valor(vinculo, "estado", "") or "").lower() == "activo"
        and int(_valor(vinculo, "organizacion_id", 0) or 0) == int(organizacion_id)
        and int(_valor(vinculo, "unidad_negocio_id", 0) or 0) == int(unidad_negocio_id)
    ]
    if len(candidatos) != 1:
        motivo = "sin vínculo activo" if not candidatos else "vínculo ambiguo"
        raise ConfiguracionSalidaWhatsAppError(
            f"Salida WhatsApp bloqueada: {motivo} para el contexto indicado."
        )
    phone = str(_valor(candidatos[0], "whatsapp_phone_number_id", "") or "").strip()
    variables = nombres_variables_credencial(phone)
    token = str((environ or {}).get(variables["token"]) or "").strip()
    if not token:
        raise ConfiguracionSalidaWhatsAppError(
            f"Salida WhatsApp bloqueada: falta {variables['token']}."
        )
    return ConfiguracionSalidaWhatsApp(
        organizacion_id=int(organizacion_id),
        unidad_negocio_id=int(unidad_negocio_id),
        phone_number_id=phone,
        token=token,
        api_url=f"https://graph.facebook.com/v19.0/{phone}/messages",
    )


def certificar_configuraciones_salida_whatsapp(vinculos, *, environ):
    resultados = []
    for vinculo in vinculos or []:
        organizacion_id = int(_valor(vinculo, "organizacion_id", 0) or 0)
        unidad_id = int(_valor(vinculo, "unidad_negocio_id", 0) or 0)
        phone = str(_valor(vinculo, "whatsapp_phone_number_id", "") or "").strip()
        try:
            config = resolver_configuracion_salida_whatsapp(
                vinculos,
                organizacion_id=organizacion_id,
                unidad_negocio_id=unidad_id,
                environ=environ,
            )
            estado, variable = "preparada", nombres_variables_credencial(phone)["token"]
            assert config.phone_number_id == phone
        except ConfiguracionSalidaWhatsAppError as error:
            estado, variable = "bloqueada", str(error)
        resultados.append({
            "organizacion_id": organizacion_id,
            "unidad_negocio_id": unidad_id,
            "phone_number_id_sha256": hashlib.sha256(phone.encode()).hexdigest(),
            "estado": estado,
            "referencia": variable,
        })
    return {
        "modo": "certificacion_salida_whatsapp_no_ejecutable",
        "preparadas": sum(x["estado"] == "preparada" for x in resultados),
        "bloqueadas": sum(x["estado"] == "bloqueada" for x in resultados),
        "resultados": resultados,
        "autorizacion_activacion": False,
        "controles": {"mensajes_enviados": 0, "conexiones_externas": 0, "secretos_persistidos": 0},
    }
