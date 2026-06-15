# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Streamlit dashboard for JetTelecom that pulls real-time data from the Hubsoft ERP via GraphQL (with REST fallback). The codebase has two distinct layers:

1. **`hubsoft/` package** (`auth.py`, `client.py`, `graphql_client.py`, `config.py`) — a reusable Python SDK for the Hubsoft API.
2. **`hubsoft_api.py`** — a standalone `HubsoftAPI` class used directly by the dashboard; it duplicates authentication logic and is the one `app.py` imports.

## Running the app

```bash
pip install -r requirements.txt
streamlit run app.py
# Dashboard opens at http://localhost:8501
```

There is no test suite.

## Configuration

Credentials are hardcoded as defaults in `config.py` and `hubsoft_api.py`. Override via environment variables:

```bash
export HUBSOFT_URL="https://api.jettelecom.hubsoft.com.br"
export HUBSOFT_CLIENT_ID="147"
export HUBSOFT_CLIENT_SECRET="..."
export HUBSOFT_USERNAME="..."
export HUBSOFT_PASSWORD="..."
```

**Important**: Hubsoft whitelists IP addresses. A `403 Host not in allowlist` error means the server's IP must be registered with the Hubsoft administrator.

## Architecture

### Authentication

`HubsoftAuth` (in `auth.py`) manages the full OAuth2 token lifecycle: it fetches a token via `password` grant and auto-renews it 60 seconds before expiry. The `_Auth` class inside `hubsoft_api.py` is a simpler version that does not auto-renew.

### Resource discovery via introspection

Because the Hubsoft GraphQL schema field names vary by tenant, `HubsoftAPI.discover()` runs a `__type(name: "Query")` introspection query on startup to learn the actual field names available. It then matches them against `CANDIDATES` (a dict of logical categories → ranked name alternatives) to build `self.resource_map`, e.g. `{"clientes": "clientes", "cobrancas": "faturas"}`.

`_fields()` similarly introspects the return type of a resource to filter the requested fields against only those that exist in the schema, preventing query errors.

### Pagination

`_all_pages()` in `HubsoftAPI` iterates using `paginatorInfo { currentPage lastPage }` — a Laravel-style paginator. It increments `page` until `currentPage >= lastPage`.

### Dashboard caching

`app.py` uses two Streamlit cache decorators:
- `@st.cache_resource` on `get_api()` — creates one `HubsoftAPI` singleton (including the introspection call) for the entire server lifetime.
- `@st.cache_data(ttl=300)` on each `load_*` function — caches data for 5 minutes. The `invalidar_cache()` function clears all four loaders at once (triggered by the sidebar "Atualizar agora" button or auto-refresh).

`safe_load()` wraps every data-fetch call and returns a `(DataFrame, error_msg_or_None)` tuple so individual failures do not crash the whole dashboard.

### Code language

Variable names, comments, log messages, and UI text are in Brazilian Portuguese (`clientes`, `cobranças`, `data_cadastro`, etc.). Match this convention when adding new code.
