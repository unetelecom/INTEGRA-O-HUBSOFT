"""
hubsoft — integração Python com a API Hubsoft (REST + GraphQL).

Exemplo rápido:
    from hubsoft import HubsoftClient, HubsoftGraphQL

    # REST
    client = HubsoftClient()
    dados  = client.clientes()

    # GraphQL
    gql    = HubsoftGraphQL()
    for page in gql.listar_clientes(first=100):
        for c in page:
            print(c["nome_razaosocial"])
"""

from .auth           import HubsoftAuth, HubsoftAuthError
from .client         import HubsoftClient, HubsoftAPIError
from .graphql_client import HubsoftGraphQL, HubsoftGraphQLError

__all__ = [
    "HubsoftAuth",
    "HubsoftAuthError",
    "HubsoftClient",
    "HubsoftAPIError",
    "HubsoftGraphQL",
    "HubsoftGraphQLError",
]
