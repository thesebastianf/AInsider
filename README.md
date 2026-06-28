<div align="center">
  <img src="logo.svg" alt="AInsider Tracker Logo" width="120" />
</div>

# AInsider Tracker

<p align="center">
  <strong><span style="color:#3b82f6">AI</span>nsider Tracker</strong> – Track congressional, senate, and insider stock trades with AI evaluation.
</p>

## 🚀 Quick Start

```bash
# 1. Clone & configure
git clone <repo-url>
cd AInsider
cp .env.example .env

# 2. Start everything
docker compose up --build

# 3. Open the app
# → http://localhost:4221
```

The app will:
- Start PostgreSQL and run database migrations
- Seed initial providers (House and Senate real data sources)
- Start the background pipeline scheduler
- Serve the React frontend on port 4221

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│            docker-compose.yml               │
│                                             │
│  ┌──────────────┐    ┌──────────────────┐   │
│  │  PostgreSQL   │◄──│       App        │   │
│  │  (port 5432)  │   │  FastAPI + React  │   │
│  │               │   │  (port 4221)      │   │
│  └──────────────┘    └──────────────────┘   │
│                              │              │
│                    ┌─────────┼─────────┐    │
│                    ▼         ▼         ▼    │
│              LLM Provider  yfinance  Notify │
│              (configurable) (API)   (config) │
└─────────────────────────────────────────────┘
```

**2 containers only** – simple and lightweight.

## 🤖 LLM Providers (UI-configurable)

Configure in **Settings → AI / LLM Provider**:

| Provider | Description |
|----------|-------------|
| 🦙 Ollama | Local models (llama3, mistral, etc.) |
| 🤖 OpenAI | GPT-4o, GPT-4o-mini, etc. |
| 🧠 Anthropic | Claude Sonnet, Haiku, etc. |
| ⚙️ Custom | Any OpenAI-compatible gateway (LM Studio, vLLM, LocalAI) |

## 🔔 Notification Providers (UI-configurable)

Configure in **Settings → Notifications**:

| Provider | Setup |
|----------|-------|
| 📨 Telegram | Bot Token + Chat ID |
| 🔔 Gotify | Server URL + App Token |
| 📲 Pushover | User Key + API Token |
| 💬 Discord | Webhook URL |
| 💼 Slack | Webhook URL |
| 📡 Ntfy | Server URL + Topic |

## 📡 Data Source Providers (UI-configurable)

Configure in **Settings → Data Sources**:

| Provider | Description |
|----------|-------------|
| 🏛️ House | House Stock Watcher API (US Representatives) |
| 🏛️ Senate | Senate Stock Watcher API (US Senators) |
| 📈 Quiver | Quiver Quantitative API (Requires API Key) |
| 🏦 SEC13F | SEC EDGAR 13F Filings (Fund Managers) |

## 📱 Features

- **Mobile-first** dark UI (works great on desktop too)
- **3 Tabs**: Portfolios, Settings, Developer
- **AI Risk Scoring**: 1-10 score with color-coded badges
- **Real-time prices**: YTD performance via yfinance
- **Background pipeline**: Auto-fetches real trades from multiple active data sources
- **Follow system**: Star persons to get notifications
- **Live logs**: Developer tab with terminal-style log viewer

## 🔧 Configuration

All environment variables are in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_PORT` | `4221` | Web interface port |
| `POSTGRES_USER` | `ainsider` | Database user |
| `POSTGRES_PASSWORD` | `changeme` | Database password |
| `SCHEDULER_INTERVAL_MINUTES` | `30` | Trade fetch interval |
| `PRICE_UPDATE_INTERVAL_MINUTES` | `15` | Price update interval |

LLM, Notification, and Data Source providers are configured via the **Settings UI**.
**Optional Seeding**: You can optionally pre-seed providers on the very first start using environment variables (`SEED_LLM_PROVIDER`, `SEED_NOTIFY_PROVIDER`, `SEED_DATASOURCE_PROVIDER`, etc.). Check `.env.example` for details.

## 🛠️ Development

```bash
# Run frontend dev server (with hot reload)
cd frontend
npm install
npm run dev
# → http://localhost:5173 (proxies API to :8000)

# Run backend separately
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## 📡 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/persons` | List persons (search, filter) |
| `PUT` | `/api/persons/:id/follow` | Toggle follow |
| `GET` | `/api/trades` | List trades (filter, paginate) |
| `GET` | `/api/performance` | Asset prices & YTD |
| `GET` | `/api/settings` | All settings + providers |
| `POST` | `/api/settings/llm` | Add LLM provider |
| `POST` | `/api/settings/notifications` | Add notification provider |
| `GET` | `/api/system/stats` | Dashboard stats |
| `POST` | `/api/system/trigger-pipeline` | Manual sync |

## ❤️ Support This Project

If AInsider Tracker helps you, you can support ongoing development on Ko-fi:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/thesebastianf)

**Ko-fi:** [https://ko-fi.com/thesebastianf](https://ko-fi.com/thesebastianf)  
**Username:** thesebastianf
