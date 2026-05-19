"""
hubsoft_api.py — Camada de acesso à API Hubsoft para o Dashboard.

Retorna pd.DataFrames normalizados prontos para visualização.
Usa exclusivamente GraphQL (/graphql/v1) — sem fallback REST.

Ao inicializar, executa introspection para descobrir os nomes
exatos dos campos disponíveis no schema do cliente.
"""

import logging
import os
import requests
import pandas as pd
from typing import Optional, List

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Credenciais
# ──────────────────────────────────────────────
HUBSOFT_URL           = os.getenv("HUBSOFT_URL",           "https://api.jettelecom.hubsoft.com.br")
HUBSOFT_CLIENT_ID     = os.getenv("HUBSOFT_CLIENT_ID",     "147")
HUBSOFT_CLIENT_SECRET = os.getenv("HUBSOFT_CLIENT_SECRET", "qfvEucYonGF8ZTXeHRb43CjRoE058GOsFGMuxs64")
HUBSOFT_USERNAME      = os.getenv("HUBSOFT_USERNAME",      "ruan.lobo@grupojet.com.br")
HUBSOFT_PASSWORD      = os.getenv("HUBSOFT_PASSWORD",      "Miguel@578512")

GQL_URL = f"{HUBSOFT_URL}/graphql/v1"


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
        r = requests.post(
            f"{HUBSOFT_URL}/oauth/token",
            data={
                "grant_type":    "password",
                "client_id":     HUBSOFT_CLIENT_ID,
                "client_secret": HUBSOFT_CLIENT_SECRET,
                "username":      HUBSOFT_USERNAME,
                "password":      HUBSOFT_PASSWORD,
            },
            timeout=30,
        )
        r.raise_for_status()
        self._token = r.json()["access_token"]
        logger.info("Token OAuth2 obtido com sucesso.")

    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token()}", "Content-Type": "application/json"}

    def invalidate(self):
        self._token = None


# ══════════════════════════════════════════════
# HubsoftAPI
# ══════════════════════════════════════════════
class HubsoftAPI:
    """
    Fachada de acesso à API Hubsoft via GraphQL.
    Todos os métodos públicos retornam pd.DataFrame.
    """

    def __init__(self):
        self._auth    = _Auth()
        self._session = requests.Session()
        self._schema_fields: dict = {}   # cache: resource -> [campos]

    # ──────────────────────────────────────────
    # GraphQL core
    # ──────────────────────────────────────────
    def _gql_raw(self, query: str) -> dict:
        """Executa query e retorna data{}. Lança RuntimeError em erros."""
        r = self._session.post(
            GQL_URL,
            headers=self._auth.headers(),
            json={"query": query},
            timeout=30,
        )
        if r.status_code == 401:
            self._auth.invalidate()
            r = self._session.post(GQL_URL, headers=self._auth.headers(),
                                   json={"query": query}, timeout=30)
        r.raise_for_status()
        body = r.json()
        if "errors" in body:
            msgs = "; ".join(e.get("message", str(e)) for e in body["errors"])
            raise RuntimeError(f"GraphQL error: {msgs}")
        return body.get("data", {})

    # ──────────────────────────────────────────
    # Introspection — descobre campos reais
    # ──────────────────────────────────────────
    def get_schema_fields(self, type_name: str) -> List[str]:
        """
        Retorna a lista de campos escalares disponíveis para um tipo GraphQL.
        Usa cache em memória para não repetir a chamada.
        """
        if type_name in self._schema_fields:
            return self._schema_fields[type_name]

        q = f"""
        query {{
            __type(name: "{type_name}") {{
                fields {{
                    name
                    type {{ kind ofType {{ kind }} }}
                }}
            }}
        }}
        """
        try:
            data   = self._gql_raw(q)
            fields = data.get("__type", {}).get("fields") or []
            # Mantém apenas campos escalares (não objetos/listas aninhadas)
            scalars = [
                f["name"] for f in fields
                if f["type"]["kind"] in ("SCALAR", "ENUM", "NON_NULL")
                or (f["type"].get("ofType") or {}).get("kind") in ("SCALAR", "ENUM")
            ]
            self._schema_fields[type_name] = scalars
            logger.debug("Campos de %s: %s", type_name, scalars)
            return scalars
        except Exception as exc:
            logger.warning("Introspection falhou para %s: %s", type_name, exc)
            return []

    def list_query_fields(self) -> List[str]:
        """Lista todos os campos disponíveis na raiz Query."""
        q = """
        query {
            __type(name: "Query") {
                fields { name }
            }
        }
        """
        try:
            data = self._gql_raw(q)
            return [f["name"] for f in (data.get("__type", {}).get("fields") or [])]
        except Exception as exc:
            logger.error("Não foi possível listar Query fields: %s", exc)
            return []

    # ──────────────────────────────────────────
    # Paginação genérica
    # ──────────────────────────────────────────
    def _gql_all(
        self,
        resource: str,
        fields: str,
        filtros: str = "",
        page_size: int = 100,
    ) -> list:
        all_items: list = []
        page = 1
        while True:
            args = f"page: {page}, first: {page_size}"
            if filtros:
                args += f", {filtros}"
            q = f"""
            query {{
                {resource}({args}) {{
                    paginatorInfo {{ currentPage lastPage total }}
                    data {{ {fields} }}
                }}
            }}
            """
            data  = self._gql_raw(q)
            res   = data.get(resource, {})
            items = res.get("data", [])
            pager = res.get("paginatorInfo", {})
            all_items.extend(items)
            logger.debug("%s pág %d/%d — %d itens", resource, page,
                         pager.get("lastPage", 1), len(items))
            if page >= pager.get("lastPage", 1):
                break
            page += 1
        return all_items

    # ──────────────────────────────────────────
    # Helpers: campos seguros via introspection
    # ──────────────────────────────────────────
    def _safe_fields(self, type_name: str, desired: List[str]) -> str:
        """
        Retorna apenas os campos de `desired` que existem de fato no schema.
        Se a introspection falhar, usa todos os desired (melhor esforço).
        """
        available = self.get_schema_fields(type_name)
        if not available:
            return " ".join(desired)
        return " ".join(f for f in desired if f in available)

    # ──────────────────────────────────────────
    # Clientes
    # ──────────────────────────────────────────
    def get_clientes(self) -> pd.DataFrame:
        desired = ["id_cliente", "codigo_cliente", "nome_razaosocial",
                   "cpf_cnpj", "email", "telefone", "status", "data_cadastro"]
        fields = self._safe_fields("Cliente", desired) or " ".join(desired)
        items  = self._gql_all("clientes", fields)
        return pd.DataFrame(items) if items else pd.DataFrame()

    # ──────────────────────────────────────────
    # Contratos
    # ──────────────────────────────────────────
    def get_contratos(self) -> pd.DataFrame:
        desired = ["id_contrato", "id_cliente", "plano", "status",
                   "valor", "data_ativacao"]
        fields = self._safe_fields("Contrato", desired) or " ".join(desired)
        items  = self._gql_all("contratos", fields)
        return pd.DataFrame(items) if items else pd.DataFrame()

    # ──────────────────────────────────────────
    # Cobranças
    # ──────────────────────────────────────────
    def get_cobrancas(self, de: str, ate: str) -> pd.DataFrame:
        desired = ["id_cobranca", "id_cliente", "valor", "vencimento",
                   "status_pagamento", "data_pagamento"]
        fields  = self._safe_fields("Cobranca", desired) or " ".join(desired)
        filtros = f'de: "{de}", ate: "{ate}"'
        items   = self._gql_all("cobrancas", fields, filtros=filtros)
        df = pd.DataFrame(items) if items else pd.DataFrame()
        if "valor" in df.columns:
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
        return df

    # ──────────────────────────────────────────
    # Ordens de Serviço
    # ──────────────────────────────────────────
    def get_ordens_servico(self, de: str, ate: str) -> pd.DataFrame:
        # Tenta nomes comuns para o recurso OS no schema Hubsoft
        resource_candidates = ["os", "ordens_servico", "ordensServico",
                                "ordem_servico", "ordemServico", "tickets"]
        query_fields = self.list_query_fields()
        resource = next((c for c in resource_candidates if c in query_fields),
                        "os")  # fallback

        desired = ["id_os", "id_cliente", "tipo", "status",
                   "descricao", "data_abertura", "data_conclusao"]
        # Introspection com nomes de tipo candidatos
        type_candidates = ["Os", "OS", "OrdemServico", "OrdemDeServico", "Ticket"]
        fields = ""
        for t in type_candidates:
            f = self._safe_fields(t, desired)
            if f:
                fields = f
                break
        fields = fields or " ".join(desired)

        filtros = f'de: "{de}", ate: "{ate}"'
        items   = self._gql_all(resource, fields, filtros=filtros)
        return pd.DataFrame(items) if items else pd.DataFrame()
