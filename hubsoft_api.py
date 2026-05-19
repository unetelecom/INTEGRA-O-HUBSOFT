"""
hubsoft_api.py — Camada de acesso à API Hubsoft para o Dashboard.

Retorna pd.DataFrames normalizados prontos para visualização.
Tenta GraphQL primeiro e cai no REST como fallback.
"""

import logging
import os
import requests
import pandas as pd
from typing import Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Credenciais (variáveis de ambiente ou padrão)
# ──────────────────────────────────────────────
HUBSOFT_URL           = os.getenv("HUBSOFT_URL",           "https://api.jettelecom.hubsoft.com.br")
HUBSOFT_CLIENT_ID     = os.getenv("HUBSOFT_CLIENT_ID",     "147")
HUBSOFT_CLIENT_SECRET = os.getenv("HUBSOFT_CLIENT_SECRET", "qfvEucYonGF8ZTXeHRb43CjRoE058GOsFGMuxs64")
HUBSOFT_USERNAME      = os.getenv("HUBSOFT_USERNAME",      "ruan.lobo@grupojet.com.br")
HUBSOFT_PASSWORD      = os.getenv("HUBSOFT_PASSWORD",      "Miguel@578512")


# ══════════════════════════════════════════════
# Auth
# ══════════════════════════════════════════════
class _Auth:
    def __init__(self):
        self._token: Optional[str] = None

    def token(self) -> str:
        if not self._token:
            self._fetch()
        return self._token  # type: ignore

    def _fetch(self):
        url = f"{HUBSOFT_URL}/oauth/token"
        r = requests.post(url, data={
            "grant_type":    "password",
            "client_id":     HUBSOFT_CLIENT_ID,
            "client_secret": HUBSOFT_CLIENT_SECRET,
            "username":      HUBSOFT_USERNAME,
            "password":      HUBSOFT_PASSWORD,
        }, timeout=30)
        r.raise_for_status()
        self._token = r.json()["access_token"]

    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token()}", "Content-Type": "application/json"}

    def invalidate(self):
        self._token = None


# ══════════════════════════════════════════════
# HubsoftAPI
# ══════════════════════════════════════════════
class HubsoftAPI:
    """
    Fachada de acesso à API Hubsoft.
    Todos os métodos retornam pd.DataFrame.
    """

    def __init__(self):
        self._auth    = _Auth()
        self._session = requests.Session()

    # ──────────────────────────────────────────
    # GraphQL helper
    # ──────────────────────────────────────────
    def _gql(self, query: str) -> dict:
        url = f"{HUBSOFT_URL}/graphql/v1"
        r = self._session.post(
            url,
            headers=self._auth.headers(),
            json={"query": query},
            timeout=30,
        )
        if r.status_code == 401:
            self._auth.invalidate()
            r = self._session.post(url, headers=self._auth.headers(), json={"query": query}, timeout=30)
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            raise RuntimeError(f"GraphQL errors: {data['errors']}")
        return data.get("data", {})

    def _gql_all(self, resource: str, fields: str, filtros: str = "", page_size: int = 100) -> list:
        """Coleta todas as páginas de um recurso GraphQL."""
        all_items = []
        page = 1
        while True:
            args = f"page: {page}, first: {page_size}"
            if filtros:
                args += f", {filtros}"
            q = f"""
            query {{
                {resource}({args}) {{
                    paginatorInfo {{ currentPage lastPage }}
                    data {{ {fields} }}
                }}
            }}
            """
            data   = self._gql(q)
            res    = data.get(resource, {})
            items  = res.get("data", [])
            pager  = res.get("paginatorInfo", {})
            all_items.extend(items)
            if page >= pager.get("lastPage", 1):
                break
            page += 1
        return all_items

    # ──────────────────────────────────────────
    # REST helper
    # ──────────────────────────────────────────
    def _rest_all(self, path: str, params: dict = {}) -> list:
        """Coleta todas as páginas de um endpoint REST."""
        all_items = []
        page = 0
        while True:
            r = self._session.get(
                f"{HUBSOFT_URL}/api/v1{path}",
                headers=self._auth.headers(),
                params={**params, "pagina": page, "quantidade": 100},
                timeout=30,
            )
            if r.status_code == 401:
                self._auth.invalidate()
                r = self._session.get(
                    f"{HUBSOFT_URL}/api/v1{path}",
                    headers=self._auth.headers(),
                    params={**params, "pagina": page, "quantidade": 100},
                    timeout=30,
                )
            r.raise_for_status()
            body = r.json()

            dados = body.get("dados", body if isinstance(body, list) else [])
            if not dados:
                break
            all_items.extend(dados)

            paginacao  = body.get("paginacao", {})
            ultima_pag = paginacao.get("ultima_pagina")
            if ultima_pag is None or page >= ultima_pag:
                break
            page += 1
        return all_items

    # ──────────────────────────────────────────
    # Clientes
    # ──────────────────────────────────────────
    def get_clientes(self) -> pd.DataFrame:
        try:
            items = self._gql_all(
                "clientes",
                "id_cliente codigo_cliente nome_razaosocial cpf_cnpj email telefone status data_cadastro"
            )
        except Exception:
            logger.warning("GraphQL falhou para clientes, tentando REST…", exc_info=True)
            items = self._rest_all("/clientes")

        return pd.DataFrame(items) if items else pd.DataFrame()

    # ──────────────────────────────────────────
    # Contratos
    # ──────────────────────────────────────────
    def get_contratos(self) -> pd.DataFrame:
        try:
            items = self._gql_all(
                "contratos",
                "id_contrato id_cliente plano status valor data_ativacao"
            )
        except Exception:
            logger.warning("GraphQL falhou para contratos, tentando REST…", exc_info=True)
            items = self._rest_all("/contratos")

        return pd.DataFrame(items) if items else pd.DataFrame()

    # ──────────────────────────────────────────
    # Cobranças
    # ──────────────────────────────────────────
    def get_cobrancas(self, de: str, ate: str) -> pd.DataFrame:
        filtros = f'de: "{de}", ate: "{ate}"'
        try:
            items = self._gql_all(
                "cobrancas",
                "id_cobranca id_cliente valor vencimento status_pagamento data_pagamento",
                filtros=filtros,
            )
        except Exception:
            logger.warning("GraphQL falhou para cobranças, tentando REST…", exc_info=True)
            items = self._rest_all("/financeiro/cobrancas", params={"de": de, "ate": ate})

        df = pd.DataFrame(items) if items else pd.DataFrame()
        if "valor" in df.columns:
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
        return df

    # ──────────────────────────────────────────
    # Ordens de Serviço
    # ──────────────────────────────────────────
    def get_ordens_servico(self, de: str, ate: str) -> pd.DataFrame:
        filtros = f'de: "{de}", ate: "{ate}"'
        try:
            items = self._gql_all(
                "ordensServico",
                "id_os id_cliente tipo status descricao data_abertura data_conclusao",
                filtros=filtros,
            )
        except Exception:
            logger.warning("GraphQL falhou para OS, tentando REST…", exc_info=True)
            items = self._rest_all("/os", params={"de": de, "ate": ate})

        return pd.DataFrame(items) if items else pd.DataFrame()
