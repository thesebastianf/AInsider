<div align="center">
  <img src="logo.svg" alt="AInsider Tracker Logo" width="120" />
</div>

# AInsider Tracker

<p align="center">
  <strong><span style="color:#3b82f6">AI</span>nsider Tracker</strong> – Track congressional, senate, executive branch, and insider stock trades with real-time AI evaluation.
</p>

<p align="center">
  <a href="https://ko-fi.com/thesebastianf" target="_blank">
    <img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="ko-fi">
  </a><br/>
  <em>If AInsider Tracker helps you, please consider supporting its ongoing development! (User: thesebastianf)</em>
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
- Seed initial data sources (House, Senate, Executive, SEC Form 4, 13F, etc.)
- Start the blazing fast background trade ingestion pipeline
- Serve the React frontend on port `4221`

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│            docker-compose.yml               │
│                                             │
│  ┌──────────────┐    ┌──────────────────┐   │
│  │  PostgreSQL  │◄───│       App        │   │
│  │  (port 5432) │    │  FastAPI + React │   │
│  │              │    │  (port 4221)     │   │
│  └──────────────┘    └──────────────────┘   │
│                              │              │
│                    ┌─────────┼─────────┐    │
│                    ▼         ▼         ▼    │
│              LLM Provider  yfinance  Notify │
│              (configurable) (Batch) (config)│
└─────────────────────────────────────────────┘
```

**2 containers only** – simple, lightweight, and powerful.

## 📱 Core Features

- **Blazing Fast Ingestion:** Trade syncing runs entirely detached from price fetching, parsing thousands of trades in seconds.
- **Smart Background Price Updates:** Uses a separate worker to fetch historical and current stock prices in bulk.
- **Rate Limit Protection:** Native Yahoo Finance `429 Too Many Requests` handling (auto-pauses for 1 hour with a single non-spammy push notification).
- **Automated Wikipedia Avatars:** Fetches Wikimedia profiles automatically for all tracked natural persons. Falls back to dynamic CSS hashes for entities.
- **AI Risk Scoring:** 1-10 score with color-coded badges to assess insider trade sentiment.
- **Mobile-first Dark UI:** A stunning, unified grid layout that works perfectly on desktop and mobile.

## 📡 Data Source Providers (Free & Built-in!)

All sources can be toggled via the **Settings → Data Sources** UI:

| Provider | Description | Status |
|----------|-------------|--------|
| 🏛️ **House** | House Stock Watcher API (US Representatives) | ✅ Free / Built-in |
| 🏛️ **Senate** | Senate Stock Watcher API (US Senators) | ✅ Free / Built-in |
| 🦅 **Executive Branch** | OGE Form 278-T Disclosures (President, Cabinet) | ✅ Free / Built-in |
| 🏦 **SEC 13F** | SEC EDGAR 13F Holdings (Fund Managers like Buffett) | ✅ Free / Built-in |
| 🦈 **SEC 13D** | SEC EDGAR 13D Activist Investors (Icahn, Singer) | ✅ Free / Built-in |
| 👔 **SEC Form 4** | SEC EDGAR Corporate Insiders (CEOs, CFOs) | ✅ Free / Built-in |
| 🇪🇺 **Directors' Dealings** | DAX & European Insiders via RSS | ✅ Free / Built-in |
| 📈 **Finnhub** | Finnhub Form 4 (High-speed US Insider Trading) | 🔑 Requires API Key |
| 📊 **Quiver** | Quiver Quantitative Congressional Trading API | 🔑 Requires API Key |

## 🤖 LLM Providers (UI-configurable)

Configure your LLM in **Settings → AI / LLM Provider**:

| Provider | Description |
|----------|-------------|
| 🦙 **Ollama** | Local models (llama3, mistral, etc.) - *Privacy First!* |
| 🤖 **OpenAI** | GPT-4o, GPT-4o-mini, etc. |
| 🧠 **Anthropic** | Claude Sonnet, Haiku, etc. |
| ⚙️ **Custom** | Any OpenAI-compatible gateway (LM Studio, vLLM, LocalAI) |

## 🔔 Notification Providers (UI-configurable)

Stay informed immediately when tracked individuals trade. Configure in **Settings → Notifications**:

| Provider | Setup Requirements |
|----------|--------------------|
| 📨 **Telegram** | Bot Token + Chat ID |
| 🔔 **Gotify** | Server URL + App Token |
| 📲 **Pushover** | User Key + API Token |
| 💬 **Discord** | Webhook URL |
| 💼 **Slack** | Webhook URL |
| 📡 **Ntfy** | Server URL + Topic |

### 📱 What to expect (Notification Example)

When an AI model evaluates a trade, you get beautifully formatted push notifications instantly on your phone:

> 🚨 **AInsider Alert: 🔴 HIGH RISK (9.5/10)**  
> 🏛️ **Nancy Pelosi (Congress)** just filed a **BUY** for **NVDA** (NVIDIA Corporation).  
> 💰 **Amount:** $1,000,001 - $5,000,000  
> 📅 **Trade Date:** 2026-06-25  
> 
> 🤖 **AI Analysis (GPT-4o):**  
> *"Highly suspicious timing. Congress is currently drafting a semiconductor funding bill which directly benefits NVIDIA. Purchasing 7-figure amounts immediately prior to the public announcement of the grant allocation represents a significant conflict of interest."*  
> 
> 🔗 [View Source Document](#)

## 🔧 Configuration

Core environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_PORT` | `4221` | Web interface port |
| `POSTGRES_USER` | `ainsider` | Database user |
| `POSTGRES_PASSWORD` | `changeme` | Database password |
| `SCHEDULER_INTERVAL_MINUTES` | `30` | Trade fetch & pipeline interval |
| `PRICE_UPDATE_INTERVAL_MINUTES` | `15` | Background batch price update interval |

*Note: All data sources, notifications, and AI configurations are safely editable via the Web UI.*

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
