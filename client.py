"""
Cliente REST para a API Hubsoft.

Oferece métodos GET, POST, PUT e DELETE com:
  - Injeção automática do token Bearer
  - Renovação automática em caso de 401
  - Paginação automática via iter_pages()
  - Logging estruturado
"""

import logging
from typing import Any, Dict, Generator, List, Optional

import requests

from .auth import HubsoftAuth, HubsoftAuthError
from .config import HUBSOFT_URL, REST_BASE_PATH

logger = logging.getLogger(__name__)


class HubsoftClient:
    """
    Cliente REST de alto nível para a API Hubsoft.

    Exemplo de uso:
        client = HubsoftClient()

        # Buscar clientes paginados
        page = client.get("/clientes", params={"pagina": 0, "quantidade": 50})

        # Iterar todas as páginas automaticamente
        for page_data in client.iter_pages("/clientes"):
            for cliente in page_data["dados"]:
                print(cliente["nome_razaosocial"])

        # Criar OS
        os_data = client.post("/os", json={...})
    """

    def __init__(
        self,
        auth: Optional[HubsoftAuth] = None,
        base_url: str = HUBSOFT_URL,
        timeout: int = 30,
    ):
        self.base_url  = base_url.rstrip("/")
        self.auth      = auth or HubsoftAuth()
        self.timeout   = timeout
        self._session  = requests.Session()

    # ------------------------------------------------------------------
    # Métodos HTTP
    # ------------------------------------------------------------------

    def get(self, path: str, params: Optional[Dict] = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: Optional[Dict] = None) -> Any:
        return self._request("POST", path, json=json)

    def put(self, path: str, json: Optional[Dict] = None) -> Any:
        return self._request("PUT", path, json=json)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    # ------------------------------------------------------------------
    # Paginação automática
    # ------------------------------------------------------------------

    def iter_pages(
        self,
        path: str,
        params: Optional[Dict] = None,
        page_param: str = "pagina",
        size_param: str = "quantidade",
        page_size: int = 50,
    ) -> Generator[Dict, None, None]:
        """
        Itera automaticamente por todas as páginas de um endpoint.

        Yields cada página como dicionário com os dados retornados pela API.
        A iteração para quando a página atual é a última.

        Exemplo:
            for page in client.iter_pages("/clientes", page_size=100):
                processar(page["dados"])
        """
        current_page = 0
        extra_params = dict(params or {})

        while True:
            extra_params[page_param] = current_page
            extra_params[size_param] = page_size

            data = self.get(path, params=extra_params)
            yield data

            paginacao = data.get("paginacao", {})
            ultima    = paginacao.get("ultima_pagina")
            atual     = paginacao.get("pagina_atual", current_page)

            if ultima is None or atual >= ultima:
                break

            current_page += 1
            logger.debug("Próxima página: %d / %d", current_page, ultima)

    def collect_all(
        self,
        path: str,
        params: Optional[Dict] = None,
        data_key: str = "dados",
        **kwargs,
    ) -> List[Any]:
        """
        Coleta todos os registros de todas as páginas em uma lista.

        Atenção: use com cuidado em datasets muito grandes.
        """
        result: List[Any] = []
        for page in self.iter_pages(path, params=params, **kwargs):
            result.extend(page.get(data_key, []))
        return result

    # ------------------------------------------------------------------
    # Recursos atalho
    # ------------------------------------------------------------------

    def clientes(self, pagina: int = 0, quantidade: int = 50, **filtros) -> Dict:
        """Lista clientes."""
        return self.get("/clientes", params={"pagina": pagina, "quantidade": quantidade, **filtros})

    def cliente_por_id(self, id_cliente: int) -> Dict:
        """Retorna um cliente pelo ID."""
        return self.get(f"/clientes/{id_cliente}")

    def contratos(self, pagina: int = 0, quantidade: int = 50, **filtros) -> Dict:
        """Lista contratos."""
        return self.get("/contratos", params={"pagina": pagina, "quantidade": quantidade, **filtros})

    def ordens_de_servico(self, pagina: int = 0, quantidade: int = 50, **filtros) -> Dict:
        """Lista ordens de serviço."""
        return self.get("/os", params={"pagina": pagina, "quantidade": quantidade, **filtros})

    def financeiro_cobrancas(self, pagina: int = 0, quantidade: int = 50, **filtros) -> Dict:
        """Lista cobranças financeiras."""
        return self.get("/financeiro/cobrancas", params={"pagina": pagina, "quantidade": quantidade, **filtros})

    # ------------------------------------------------------------------
    # Interno
    # ------------------------------------------------------------------

    def _build_url(self, path: str) -> str:
        path = path if path.startswith("/") else f"/{path}"
        # Evita duplicar o prefixo REST
        if not path.startswith(REST_BASE_PATH):
            path = f"{REST_BASE_PATH}{path}"
        return f"{self.base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
        _retry: bool = True,
    ) -> Any:
        url     = self._build_url(path)
        headers = self.auth.get_headers()

        logger.debug("%s %s  params=%s", method, url, params)

        try:
            response = self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                timeout=self.timeout,
            )
        except requests.exceptions.RequestException as exc:
            raise HubsoftAPIError(f"Erro de conexão: {exc}") from exc

        # Renovar token e tentar novamente em caso de 401
        if response.status_code == 401 and _retry:
            logger.warning("Token expirado (401). Renovando e tentando novamente…")
            self.auth.invalidate()
            return self._request(method, path, params=params, json=json, _retry=False)

        if not response.ok:
            raise HubsoftAPIError(
                f"Erro {response.status_code} em {method} {url}: {response.text}"
            )

        # Retorna JSON quando disponível; caso contrário o texto bruto
        content_type = response.headers.get("Content-Type", "")
        if "json" in content_type:
            return response.json()
        return response.text


class HubsoftAPIError(Exception):
    """Exceção genérica para erros na API Hubsoft."""
