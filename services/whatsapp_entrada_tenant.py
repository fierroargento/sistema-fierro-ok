"""Credenciales de entrada WhatsApp aisladas por cuenta empresarial.

La resolución es pura: no consulta base, no persiste y no abre red. Los
secretos sólo se leen del mapping de entorno recibido por el llamador.
"""

from dataclasses import dataclass, field
import hmac

from services.contexto_webhook_whatsapp import resolver_contexto_webhook_whatsapp
from services.whatsapp_salida_tenant import sufijo_credencial


class ConfiguracionEntradaWhatsAppError(ValueError):
    pass


@dataclass(frozen=True)
class ConfiguracionEntradaWhatsApp:
    organizacion_id: int
    unidad_negocio_id: int
    phone_number_id: str
    verify_token: str = field(default="", repr=False)
    app_secret: str = field(default="", repr=False)


def nombres_variables_entrada(phone_number_id):
    sufijo = sufijo_credencial(phone_number_id)
    return {
        "verify_token": f"WHATSAPP_VERIFY_TOKEN_{sufijo}",
        "app_secret": f"WHATSAPP_APP_SECRET_{sufijo}",
    }


def _valor(registro, nombre, default=None):
    if isinstance(registro, dict):
        return registro.get(nombre, default)
    return getattr(registro, nombre, default)


def resolver_configuracion_post_whatsapp(payload, vinculos, *, environ):
    contexto = resolver_contexto_webhook_whatsapp(payload, vinculos)
    variables = nombres_variables_entrada(contexto["phone_number_id"])
    app_secret = str((environ or {}).get(variables["app_secret"]) or "").strip()
    if not app_secret:
        raise ConfiguracionEntradaWhatsAppError(
            f"Webhook bloqueado: falta {variables['app_secret']}."
        )
    return ConfiguracionEntradaWhatsApp(
        organizacion_id=contexto["organizacion_id"],
        unidad_negocio_id=contexto["unidad_negocio_id"],
        phone_number_id=contexto["phone_number_id"],
        app_secret=app_secret,
    )


def resolver_configuracion_verificacion_whatsapp(
    verify_token_recibido, vinculos, *, environ,
):
    recibido = str(verify_token_recibido or "").strip()
    if not recibido:
        raise ConfiguracionEntradaWhatsAppError(
            "Verificación bloqueada: falta token recibido."
        )

    candidatos = []
    for vinculo in vinculos or []:
        if str(_valor(vinculo, "canal", "") or "").lower() != "whatsapp":
            continue
        if str(_valor(vinculo, "estado", "") or "").lower() != "activo":
            continue
        phone = str(_valor(vinculo, "whatsapp_phone_number_id", "") or "").strip()
        if not phone:
            continue
        variable = nombres_variables_entrada(phone)["verify_token"]
        esperado = str((environ or {}).get(variable) or "").strip()
        if esperado and hmac.compare_digest(recibido, esperado):
            candidatos.append((vinculo, phone))

    if len(candidatos) != 1:
        motivo = "sin cuenta coincidente" if not candidatos else "cuenta ambigua"
        raise ConfiguracionEntradaWhatsAppError(
            f"Verificación bloqueada: {motivo}."
        )

    vinculo, phone = candidatos[0]
    try:
        organizacion_id = int(_valor(vinculo, "organizacion_id"))
        unidad_negocio_id = int(_valor(vinculo, "unidad_negocio_id"))
    except (TypeError, ValueError) as error:
        raise ConfiguracionEntradaWhatsAppError(
            "Verificación bloqueada: identidad tenant inválida."
        ) from error
    if organizacion_id <= 0 or unidad_negocio_id <= 0:
        raise ConfiguracionEntradaWhatsAppError(
            "Verificación bloqueada: identidad tenant inválida."
        )
    return ConfiguracionEntradaWhatsApp(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        phone_number_id=phone,
        verify_token=recibido,
    )
