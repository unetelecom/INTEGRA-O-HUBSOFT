"""
Cliente GraphQL para a API Hubsoft.

Permite executar queries e mutations com:
  - Injeção automática do token Bearer
  - Paginação cursor-based via iter_graphql()
  - Suporte a filtros de data (de / ate)
  - Suporte a orderBy
"""

import logging
from typing import Any, Dict, Generator, List, Optional

import requests

from .auth import HubsoftAuth
from .config import HUBSOFT_URL, GRAPHQL_ENDPOINT

logger = logging.getLogger(__name__)


class HubsoftGraphQL:
    """
    Cliente GraphQL para a API Hubsoft.

    Exemplo de uso:
        gql = HubsoftGraphQL()

        # Query simples
        result = gql.query('''
            query {
                clientes(page: 1, first: 10) {
                    paginatorInfo { total currentPage lastPage }
                    data { id_cliente nome_razaosocial cpf_cnpj }
                }
            }
        ''')

        # Iterar todas as páginas automaticamente
        for page in gql.iter_pages("clientes", fields="id_cliente nome_razaosocial", first=50):
            for cliente in page:
                print(cliente)

        # Com filtro de data
        for page in gql.iter_pages(
            "cobrancas",
            fields="id_cobranca valor vencimento",
            first=100,
            filtros={"de": "2024-01-01", "ate": "2024-03-31"},
        ):
            ...
    """

    def __init__(
        self,
        auth: Optional[HubsoftAuth] = None,
        base_url: str = HUBSOFT_URL,
        timeout: int = 30,
    ):
        self.endpoint = f"{base_url.rstrip('/')}{GRAPHQL_ENDPOINT}"
        self.auth     = auth or HubsoftAuth()
        self.timeout  = timeout
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Execução bruta de query/mutation
    # ------------------------------------------------------------------

    def query(
        self,
        gql: str,
        variables: Optional[Dict] = None,
        operation_name: Optional[str] = None,
    ) -> Dict:
        """
        Executa uma query ou mutation GraphQL e retorna o dict completo.

        Levanta HubsoftGraphQLError se a resposta contiver erros GraphQL.
        """
        payload: Dict[str, Any] = {"query": gql}
        if variables:
            payload["variables"] = variables
        if operation_name:
            payload["operationName"] = operation_name

        logger.debug("GraphQL → %s…", gql[:120].replace("\n", " "))

        try:
            response = self._session.post(
                self.endpoint,
                headers=self.auth.get_headers(),
                json=payload,
                timeout=self.timeout,
            )
        except requests.exceptions.RequestException as exc:
            raise HubsoftGraphQLError(f"Erro de conexão: {exc}") from exc

        if response.status_code == 401:
            logger.warning("Token expirado (401) no GraphQL. Renovando…")
            self.auth.invalidate()
            return self.query(gql, variables=variables, operation_name=operation_name)

        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            raise HubsoftGraphQLError(f"Erros GraphQL: {data['errors']}")

        return data.get("data", {})

    # ------------------------------------------------------------------
    # Paginação automática
    # ------------------------------------------------------------------

    def iter_pages(
        self,
        resource: str,
        fields: str,
        first: int = 50,
        filtros: Optional[Dict] = None,
        order_by: Optional[str] = None,
    ) -> Generator[List[Dict], None, None]:
        """
        Itera automaticamente por todas as páginas de um recurso GraphQL.

        Args:
            resource:  Nome do campo GraphQL raiz (ex: "clientes", "cobrancas").
            fields:    Campos desejados dentro de data {}.
            first:     Itens por página.
            filtros:   Dict com parâmetros extras (de, ate, id_cliente, etc.).
            order_by:  Campo de ordenação, ex: "created_at".

        Yields:
            Lista de dicts de cada página.
        """
        current_page = 1

        while True:
            args_parts = [f"page: {current_page}", f"first: {first}"]

            if filtros:
                for k, v in filtros.items():
                    args_parts.append(f'{k}: "{v}"')

            if order_by:
                args_parts.append(f'orderBy: [{{"column": "{order_by}", "order": ASC}}]')

            args = ", ".join(args_parts)

            gql = f"""
            query PageQuery {{
                {resource}({args}) {{
                    paginatorInfo {{
                        currentPage
                        lastPage
                        total
                    }}
                    data {{
                        {fields}
                    }}
                }}
            }}
            """

            result      = self.query(gql)
            resource_data = result.get(resource, {})
            paginator   = resource_data.get("paginatorInfo", {})
            items       = resource_data.get("data", [])

            yield items

            last_page = paginator.get("lastPage", 1)
            logger.debug(
                "%s – página %d/%d  (%d itens)",
                resource, current_page, last_page, len(items),
            )

            if current_page >= last_page:
                break

            current_page += 1

    def collect_all(
        self,
        resource: str,
        fields: str,
        first: int = 50,
        filtros: Optional[Dict] = None,
        order_by: Optional[str] = None,
    ) -> List[Dict]:
        """Coleta todos os registros de todas as páginas em uma lista."""
        result: List[Dict] = []
        for page in self.iter_pages(resource, fields, first=first, filtros=filtros, order_by=order_by):
            result.extend(page)
        return result

    # ------------------------------------------------------------------
    # Queries prontas — exemplos de uso comum
    # ------------------------------------------------------------------

    def listar_clientes(
        self,
        first: int = 50,
        de: Optional[str] = None,
        ate: Optional[str] = None,
    ) -> Generator[List[Dict], None, None]:
        """Itera por todos os clientes."""
        filtros = {}
        if de:
            filtros["de"] = de
        if ate:
            filtros["ate"] = ate

        fields = """
            id_cliente
            codigo_cliente
            nome_razaosocial
            cpf_cnpj
            email
            telefone
            status
        """
        return self.iter_pages("clientes", fields=fields, first=first, filtros=filtros or None)

    def listar_contratos(
        self,
        first: int = 50,
        de: Optional[str] = None,
        ate: Optional[str] = None,
    ) -> Generator[List[Dict], None, None]:
        """Itera por todos os contratos."""
        filtros = {}
        if de:
            filtros["de"] = de
        if ate:
            filtros["ate"] = ate

        fields = """
            id_contrato
            id_cliente
            plano
            status
            data_ativacao
            valor
        """
        return self.iter_pages("contratos", fields=fields, first=first, filtros=filtros or None)

    def listar_cobrancas(
        self,
        de: str,
        ate: str,
        first: int = 100,
    ) -> Generator[List[Dict], None, None]:
        """Itera cobranças financeiras em um intervalo de datas."""
        fields = """
            id_cobranca
            id_cliente
            valor
            vencimento
            status_pagamento
            data_pagamento
        """
        return self.iter_pages(
            "cobrancas",
            fields=fields,
            first=first,
            filtros={"de": de, "ate": ate},
        )


class HubsoftGraphQLError(Exception):
    """Exceção para erros GraphQL retornados pela API Hubsoft."""
