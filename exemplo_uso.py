"""
exemplo_uso.py — Demonstração da integração Hubsoft.

Execute com:
    python exemplo_uso.py
"""

import logging
import sys
import os

# Adiciona o diretório pai ao path para importar o pacote hubsoft
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hubsoft import HubsoftAuth, HubsoftClient, HubsoftGraphQL

# Configura logs visíveis
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)

# ======================================================================
# 1. Teste de autenticação
# ======================================================================
print("\n" + "="*60)
print("1. AUTENTICAÇÃO OAuth2")
print("="*60)

auth = HubsoftAuth()
try:
    token = auth.get_token()
    print(f"✅  Token obtido com sucesso!\n    {token[:40]}…")
except Exception as e:
    print(f"❌  Falha na autenticação: {e}")
    sys.exit(1)


# ======================================================================
# 2. API REST — listar clientes (1ª página)
# ======================================================================
print("\n" + "="*60)
print("2. REST — LISTAGEM DE CLIENTES (página 0)")
print("="*60)

client = HubsoftClient(auth=auth)
try:
    resultado = client.clientes(pagina=0, quantidade=5)
    print(f"✅  Total de registros: {resultado.get('paginacao', {}).get('total_registros', '?')}")
    for c in resultado.get("dados", [])[:3]:
        print(f"   → {c.get('id_cliente') or c.get('id')} | {c.get('nome_razaosocial') or c}")
except Exception as e:
    print(f"❌  Erro ao listar clientes: {e}")


# ======================================================================
# 3. API REST — iterar todas as páginas de contratos
# ======================================================================
print("\n" + "="*60)
print("3. REST — TODOS OS CONTRATOS (paginação automática)")
print("="*60)

try:
    todos_contratos = client.collect_all("/contratos", page_size=50)
    print(f"✅  Total de contratos coletados: {len(todos_contratos)}")
except Exception as e:
    print(f"❌  Erro ao coletar contratos: {e}")


# ======================================================================
# 4. API GraphQL — query manual
# ======================================================================
print("\n" + "="*60)
print("4. GRAPHQL — QUERY MANUAL DE CLIENTES")
print("="*60)

gql = HubsoftGraphQL(auth=auth)

QUERY_CLIENTES = """
query ListarClientes {
    clientes(page: 1, first: 5) {
        paginatorInfo {
            currentPage
            lastPage
            total
        }
        data {
            id_cliente
            codigo_cliente
            nome_razaosocial
            cpf_cnpj
        }
    }
}
"""

try:
    data = gql.query(QUERY_CLIENTES)
    info = data.get("clientes", {}).get("paginatorInfo", {})
    registros = data.get("clientes", {}).get("data", [])
    print(f"✅  Total: {info.get('total')}  |  Última página: {info.get('lastPage')}")
    for r in registros[:3]:
        print(f"   → {r.get('id_cliente')} | {r.get('nome_razaosocial')}")
except Exception as e:
    print(f"❌  Erro na query GraphQL: {e}")


# ======================================================================
# 5. API GraphQL — paginação automática
# ======================================================================
print("\n" + "="*60)
print("5. GRAPHQL — PAGINAÇÃO AUTOMÁTICA DE CLIENTES")
print("="*60)

try:
    total = 0
    for i, pagina in enumerate(gql.listar_clientes(first=50), start=1):
        total += len(pagina)
        print(f"   Página {i}: {len(pagina)} clientes")
        if i >= 3:          # Limita a 3 páginas neste exemplo
            print("   … (limitado a 3 páginas neste exemplo)")
            break
    print(f"✅  Clientes coletados nas primeiras páginas: {total}")
except Exception as e:
    print(f"❌  Erro na paginação GraphQL: {e}")


# ======================================================================
# 6. API GraphQL — cobranças por período
# ======================================================================
print("\n" + "="*60)
print("6. GRAPHQL — COBRANÇAS (jan-mar 2024)")
print("="*60)

try:
    cobrancas = []
    for pagina in gql.listar_cobrancas(de="2024-01-01", ate="2024-03-31", first=100):
        cobrancas.extend(pagina)
    print(f"✅  Cobranças no período: {len(cobrancas)}")
except Exception as e:
    print(f"❌  Erro ao listar cobranças: {e}")

print("\n✅  Demonstração concluída.\n")
