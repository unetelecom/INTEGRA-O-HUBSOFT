"""
hubsoft_api.py — Camada de acesso à API Hubsoft para o Dashboard.

Estratégia:
  1. Autentica via OAuth2
  2. Faz introspection GraphQL para descobrir os nomes REAIS dos recursos
  3. Mapeia automaticamente: clientes, contratos, cobranças, OS
  4. Nunca lança exceção no construtor — erros ficam em self.errors
"""

import logging
import os
import requests
import pandas as pd
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

HUBSOFT_URL           = os.getenv("HUBSOFT_URL",           "https://api.jettelecom.hubsoft.com.br")
HUBSOFT_CLIENT_ID     = os.getenv("HUBSOFT_CLIENT_ID",     "147")
HUBSOFT_CLIENT_SECRET = os.getenv("HUBSOFT_CLIENT_SECRET", "qfvEucYonGF8ZTXeHRb43CjRoE058GOsFGMuxs64")
HUBSOFT_USERNAME      = os.getenv("HUBSOFT_USERNAME",      "ruan.lobo@grupojet.com.br")
HUBSOFT_PASSWORD      = os.getenv("HUBSOFT_PASSWORD",      "Miguel@578512")

GQL_URL = f"{HUBSOFT_URL}/graphql/v1"

# Candidatos por categoria (do mais provável ao menos provável)
CANDIDATES = {
    "clientes":   ["clientes", "cliente", "customers", "assinantes"],
    "contratos":  ["contratos", "contrato", "assinaturas", "planos_clientes",
                   "subscriptions", "servicosClientes"],
    "cobrancas":  ["cobrancas", "cobranca", "faturas", "financeiro",
                   "boletos", "invoices", "titulos"],
    "os":         ["os", "ordens_servico", "ordensServico", "ordemServico",
                   "ordem_servico", "tickets", "chamados", "atendimentos"],
}


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

    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token()}", "Content-Type": "application/json"}

    def invalidate(self):
        self._token = None


class HubsoftAPI:
    def __init__(self):
        self._auth          = _Auth()
        self._session       = requests.Session()
        self.errors: List[str] = []
        self.resource_map: Dict[str, str]  = {}   # categoria -> nome real no schema
        self.query_fields:  List[str]      = []   # todos os campos da Query raiz
        self._type_fields:  Dict[str, List[str]] = {}

    # ──────────────────────────────────────────
    # GraphQL core
    # ──────────────────────────────────────────
    def _gql(self, query: str) -> dict:
        r = self._session.post(GQL_URL, headers=self._auth.headers(),
                               json={"query": query}, timeout=30)
        if r.status_code == 401:
            self._auth.invalidate()
            r = self._session.post(GQL_URL, headers=self._auth.headers(),
                                   json={"query": query}, timeout=30)
        r.raise_for_status()
        body = r.json()
        if "errors" in body:
            msgs = "; ".join(e.get("message", str(e)) for e in body["errors"])
            raise RuntimeError(msgs)
        return body.get("data", {})

    # ──────────────────────────────────────────
    # Introspection
    # ──────────────────────────────────────────
    def discover(self):
        """
        Descobre os campos reais do schema e preenche self.resource_map.
        Deve ser chamado uma vez no início (cached via st.cache_resource).
        """
        # 1. Lista todos os campos da Query raiz
        q = '{ __type(name: "Query") { fields { name } } }'
        data  = self._gql(q)
        self.query_fields = [f["name"] for f in
                             (data.get("__type") or {}).get("fields", [])]
        logger.info("Query fields disponíveis: %s", self.query_fields)

        # 2. Mapeia cada categoria ao nome real
        for categoria, candidates in CANDIDATES.items():
            match = next((c for c in candidates if c in self.query_fields), None)
            if match:
                self.resource_map[categoria] = match
                logger.info("Mapeado: %s → %s", categoria, match)
            else:
                logger.warning("Nenhum candidato encontrado para '%s'. "
                               "Candidatos testados: %s", categoria, candidates)

        return self.resource_map

    def get_type_fields(self, type_name: str) -> List[str]:
        """Retorna campos escalares de um tipo GraphQL."""
        if type_name in self._type_fields:
            return self._type_fields[type_name]
        q = f'''{{
            __type(name: "{type_name}") {{
                fields {{
                    name
                    type {{ kind ofType {{ kind }} }}
                }}
            }}
        }}'''
        try:
            data   = self._gql(q)
            fields = (data.get("__type") or {}).get("fields") or []
            scalars = [
                f["name"] for f in fields
                if f["type"]["kind"] in ("SCALAR", "ENUM", "NON_NULL")
                or (f["type"].get("ofType") or {}).get("kind") in ("SCALAR", "ENUM")
            ]
            self._type_fields[type_name] = scalars
            return scalars
        except Exception:
            return []

    # ──────────────────────────────────────────
    # Paginação genérica
    # ──────────────────────────────────────────
    def _all_pages(self, resource: str, fields: str,
                   filtros: str = "", page_size: int = 100) -> list:
        items, page = [], 1
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
            data  = self._gql(q)
            res   = data.get(resource, {})
            batch = res.get("data", [])
            pager = res.get("paginatorInfo", {})
            items.extend(batch)
            logger.debug("%s pág %d/%d", resource, page, pager.get("lastPage", 1))
            if page >= pager.get("lastPage", 1):
                break
            page += 1
        return items

    # ──────────────────────────────────────────
    # Campos seguros (filtra pelo schema real)
    # ──────────────────────────────────────────
    def _fields(self, type_candidates: List[str], desired: List[str]) -> str:
        for t in type_candidates:
            available = self.get_type_fields(t)
            if available:
                matched = [f for f in desired if f in available]
                if matched:
                    return " ".join(matched)
        # Fallback: usa tudo que foi pedido mesmo sem confirmação
        return " ".join(desired)

    # ──────────────────────────────────────────
    # Dados públicos
    # ──────────────────────────────────────────
    def get_clientes(self) -> pd.DataFrame:
        resource = self.resource_map.get("clientes", "clientes")
        desired  = ["id_cliente", "codigo_cliente", "nome_razaosocial",
                    "cpf_cnpj", "email", "telefone", "status", "data_cadastro"]
        fields   = self._fields(["Cliente", "Clientes", "Customer"], desired)
        items    = self._all_pages(resource, fields)
        return pd.DataFrame(items)

    def get_contratos(self) -> pd.DataFrame:
        resource = self.resource_map.get("contratos")
        if not resource:
            return pd.DataFrame()
        desired = ["id_contrato", "id_cliente", "plano", "status",
                   "valor", "data_ativacao"]
        fields  = self._fields(["Contrato", "Assinatura", "Subscription"], desired)
        items   = self._all_pages(resource, fields)
        return pd.DataFrame(items)

    def get_cobrancas(self, de: str, ate: str) -> pd.DataFrame:
        resource = self.resource_map.get("cobrancas")
        if not resource:
            return pd.DataFrame()
        desired = ["id_cobranca", "id_cliente", "valor", "vencimento",
                   "status_pagamento", "data_pagamento"]
        fields  = self._fields(["Cobranca", "Fatura", "Boleto", "Titulo"], desired)
        filtros = f'de: "{de}", ate: "{ate}"'
        items   = self._all_pages(resource, fields, filtros=filtros)
        df = pd.DataFrame(items)
        if "valor" in df.columns:
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
        return df

    def get_ordens_servico(self, de: str, ate: str) -> pd.DataFrame:
        resource = self.resource_map.get("os")
        if not resource:
            return pd.DataFrame()
        desired = ["id_os", "id_cliente", "tipo", "status",
                   "descricao", "data_abertura", "data_conclusao"]
        fields  = self._fields(["Os", "OS", "OrdemServico", "Ticket", "Chamado"], desired)
        filtros = f'de: "{de}", ate: "{ate}"'
        items   = self._all_pages(resource, fields, filtros=filtros)
        return pd.DataFrame(items)

