# 📡 Dashboard JetTelecom · Hubsoft

App Streamlit com dados em tempo real da API Hubsoft — financeiro, clientes, contratos e ordens de serviço.

---

## ▶️ Como rodar

### 1. Instale as dependências
```bash
pip install -r requirements.txt
```

### 2. (Opcional) Configure variáveis de ambiente
As credenciais já estão no código, mas você pode sobrescrevê-las via `.env` ou variáveis de ambiente:

```bash
export HUBSOFT_URL="https://api.jettelecom.hubsoft.com.br"
export HUBSOFT_CLIENT_ID="147"
export HUBSOFT_CLIENT_SECRET="qfvEucYonGF8ZTXeHRb43CjRoE058GOsFGMuxs64"
export HUBSOFT_USERNAME="ruan.lobo@grupojet.com.br"
export HUBSOFT_PASSWORD="Miguel@578512"
```

### 3. Suba o dashboard
```bash
streamlit run app.py
```

Acesse em: **http://localhost:8501**

---

## 🗂️ Arquivos

| Arquivo | Descrição |
|---|---|
| `app.py` | Interface Streamlit — abas, gráficos, KPIs |
| `hubsoft_api.py` | Camada de acesso à API (GraphQL + REST fallback) |
| `requirements.txt` | Dependências Python |

---

## 📊 Seções do dashboard

| Aba | Conteúdo |
|---|---|
| 💰 Financeiro | Receita total, recebido, em aberto, taxa de recebimento, gráfico de receita por dia, distribuição por status |
| 👥 Clientes | KPIs de ativos/inativos, novos por mês, tabela filtrável |
| 📄 Contratos | MRR, contratos por plano (top 15), distribuição por status |
| 🔧 OS | OS abertas/concluídas/pendentes, OS por dia, por tipo, tabela filtrável |

---

## 🔄 Auto-refresh

Ative a opção **Auto-refresh (5 min)** na sidebar para atualização automática dos dados.

---

## ⚠️ Requisito de IP

O Hubsoft exige que o IP do servidor esteja liberado na configuração da API.  
Se aparecer `403 Host not in allowlist`, solicite ao administrador do Hubsoft que libere o IP.
