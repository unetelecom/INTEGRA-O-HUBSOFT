"""
Configurações da integração Hubsoft.
Carrega as variáveis de ambiente ou usa os valores padrão definidos aqui.
"""

import os

HUBSOFT_URL           = os.getenv("HUBSOFT_URL",           "https://api.jettelecom.hubsoft.com.br")
HUBSOFT_CLIENT_ID     = os.getenv("HUBSOFT_CLIENT_ID",     "147")
HUBSOFT_CLIENT_SECRET = os.getenv("HUBSOFT_CLIENT_SECRET", "qfvEucYonGF8ZTXeHRb43CjRoE058GOsFGMuxs64")
HUBSOFT_USERNAME      = os.getenv("HUBSOFT_USERNAME",      "ruan.lobo@grupojet.com.br")
HUBSOFT_PASSWORD      = os.getenv("HUBSOFT_PASSWORD",      "Miguel@578512")

# Endpoints
OAUTH_TOKEN_ENDPOINT  = "/oauth/token"
REST_BASE_PATH        = "/api/v1"
GRAPHQL_ENDPOINT      = "/graphql/v1"
