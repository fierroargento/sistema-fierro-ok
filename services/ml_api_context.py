"""
services/ml_api_context.py

Contexto de API Mercado Libre por cuenta.

Objetivo SaaS/multicuenta:
- Toda llamada a ML debe ejecutarse con una MercadoLibreCuenta concreta.
- Este módulo no busca cuentas.
- Este módulo no conoce Pedido.
- Este módulo no usa MercadoLibreCuenta.query.first().
"""

from modules.bot_ml.api_client import (
    ml_api_get_binario_con_token,
    ml_api_get_con_token,
    ml_api_post_json_con_token,
    ml_refresh_access_token,
    ml_token_vencido,
)


class MLApiContextError(Exception):
    """Error base del contexto API Mercado Libre."""


class MLApiCuentaInvalida(MLApiContextError):
    """La cuenta ML recibida no sirve para operar."""


class MLApiTokenInvalido(MLApiContextError):
    """La cuenta ML no tiene access token utilizable."""


def _normalizar_texto(valor):
    return str(valor or "").strip()


class MLApiContext:
    """Cliente de API ML atado a una cuenta concreta.

    No resuelve cuentas por sí mismo. La cuenta debe venir desde services/ml_cuentas.py
    o desde una capa orquestadora explícita.
    """

    def __init__(
        self,
        cuenta,
        db_session=None,
        token_vencido_fn=None,
        refresh_fn=None,
        get_fn=None,
        post_json_fn=None,
        get_binario_fn=None,
        logger_fn=None,
    ):
        self.cuenta = cuenta
        self.db_session = db_session
        self.token_vencido_fn = token_vencido_fn or ml_token_vencido
        self.refresh_fn = refresh_fn or ml_refresh_access_token
        self.get_fn = get_fn or ml_api_get_con_token
        self.post_json_fn = post_json_fn or ml_api_post_json_con_token
        self.get_binario_fn = get_binario_fn or ml_api_get_binario_con_token
        self.logger_fn = logger_fn

    @property
    def cuenta_id(self):
        return getattr(self.cuenta, "id", None)

    @property
    def seller_id(self):
        return _normalizar_texto(getattr(self.cuenta, "user_id_ml", ""))

    def _log(self, mensaje):
        if self.logger_fn:
            self.logger_fn(mensaje)

    def _validar_cuenta(self):
        if not self.cuenta:
            raise MLApiCuentaInvalida("No se recibió cuenta Mercado Libre.")

        if not self.cuenta_id:
            raise MLApiCuentaInvalida("La cuenta Mercado Libre no tiene id.")

        if not self.seller_id:
            raise MLApiCuentaInvalida("La cuenta Mercado Libre no tiene user_id_ml.")

        return True

    def _commit_si_corresponde(self):
        if self.db_session is not None:
            self.db_session.commit()

    def asegurar_token(self):
        """Devuelve access_token vigente para la cuenta del contexto.

        Si el token está vencido, refresca esa cuenta concreta.
        """
        self._validar_cuenta()

        try:
            vencido = bool(self.token_vencido_fn(self.cuenta))
        except Exception as e:
            raise MLApiTokenInvalido(f"No se pudo validar vencimiento token ML: {e}")

        if vencido:
            self._log(
                f"[ML API] Refresh token cuenta_id={self.cuenta_id} seller_id={self.seller_id}"
            )
            self.cuenta = self.refresh_fn(self.cuenta)
            self._commit_si_corresponde()

        access_token = _normalizar_texto(getattr(self.cuenta, "access_token", ""))

        if not access_token:
            raise MLApiTokenInvalido(
                f"La cuenta ML id={self.cuenta_id} no tiene access_token."
            )

        return access_token

    def get(self, path, params=None):
        token = self.asegurar_token()
        self._log(f"[ML API] GET cuenta_id={self.cuenta_id} seller_id={self.seller_id} path={path}")
        return self.get_fn(token, path, params=params)

    def post_json(self, path, payload=None):
        token = self.asegurar_token()
        self._log(f"[ML API] POST cuenta_id={self.cuenta_id} seller_id={self.seller_id} path={path}")
        return self.post_json_fn(token, path, payload=payload)

    def get_binario(self, path, params=None, accept="application/pdf"):
        token = self.asegurar_token()
        self._log(
            f"[ML API] GET_BINARIO cuenta_id={self.cuenta_id} seller_id={self.seller_id} path={path}"
        )
        return self.get_binario_fn(token, path, params=params, accept=accept)


def ml_api_contexto(cuenta, **kwargs):
    """Factory chica para mantener call sites legibles."""
    return MLApiContext(cuenta, **kwargs)
