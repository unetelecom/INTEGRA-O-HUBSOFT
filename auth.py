"""
Autenticação OAuth2 para a API Hubsoft.

Gerencia obtenção e renovação automática do access_token.
O token é armazenado em memória e renovado antes de expirar.
"""

import time
import logging
import requests
from typing import Optional

from .config import (
    HUBSOFT_URL,
    HUBSOFT_CLIENT_ID,
    HUBSOFT_CLIENT_SECRET,
    HUBSOFT_USERNAME,
    HUBSOFT_PASSWORD,
    OAUTH_TOKEN_ENDPOINT,
)

logger = logging.getLogger(__name__)


class HubsoftAuth:
    """
    Gerencia o ciclo de vida do token OAuth2 do Hubsoft.

    Uso:
        auth = HubsoftAuth()
        headers = auth.get_headers()   # {'Authorization': 'Bearer <token>'}
    """

    def __init__(
        self,
        url: str = HUBSOFT_URL,
        client_id: str = HUBSOFT_CLIENT_ID,
        client_secret: str = HUBSOFT_CLIENT_SECRET,
        username: str = HUBSOFT_USERNAME,
        password: str = HUBSOFT_PASSWORD,
    ):
        self.base_url = url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password

        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0          # timestamp unix
        self._refresh_token: Optional[str] = None

    # ------------------------------------------------------------------
    # Públicos
    # ------------------------------------------------------------------

    def get_token(self) -> str:
        """Retorna um token válido, renovando se necessário."""
        if self._is_expired():
            self._fetch_token()
        return self._access_token  # type: ignore[return-value]

    def get_headers(self) -> dict:
        """Retorna os headers HTTP com o token Bearer."""
        return {
            "Authorization": f"Bearer {self.get_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def invalidate(self) -> None:
        """Força a renovação do token na próxima chamada."""
        self._access_token = None
        self._expires_at = 0.0

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _is_expired(self) -> bool:
        """Verifica se o token expirou (com margem de 60 s)."""
        return time.time() >= self._expires_at - 60

    def _fetch_token(self) -> None:
        """Obtém um novo access_token via OAuth2 password grant."""
        url = f"{self.base_url}{OAUTH_TOKEN_ENDPOINT}"

        payload = {
            "grant_type":    "password",
            "client_id":     self.client_id,
            "client_secret": self.client_secret,
            "username":      self.username,
            "password":      self.password,
        }

        logger.debug("Obtendo token OAuth2 em %s", url)

        try:
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            logger.error("Erro HTTP ao autenticar: %s – %s", exc, response.text)
            raise HubsoftAuthError(f"Falha na autenticação: {response.status_code} {response.text}") from exc
        except requests.exceptions.RequestException as exc:
            logger.error("Erro de conexão ao autenticar: %s", exc)
            raise HubsoftAuthError(f"Erro de conexão: {exc}") from exc

        data = response.json()

        self._access_token  = data.get("access_token")
        self._refresh_token = data.get("refresh_token")
        expires_in          = int(data.get("expires_in", 3600))
        self._expires_at    = time.time() + expires_in

        if not self._access_token:
            raise HubsoftAuthError(f"access_token ausente na resposta: {data}")

        logger.info("Token OAuth2 obtido com sucesso. Expira em %d s.", expires_in)


class HubsoftAuthError(Exception):
    """Exceção lançada quando a autenticação falha."""
