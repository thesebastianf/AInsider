# AInsider Tracker Workspace Customizations & Rules

These guidelines are loaded automatically by AI agents collaborating on this project. They establish core architectural patterns, styling conventions, and codebase rules agreed upon with the user.

---

## 1. Database Schema & Migration Policy
*   **Database Migrations:** This project uses Alembic. Schema modifications to `backend/app/models.py` must have matching migration scripts under `backend/alembic/versions/`.
*   **Squashing during iteration:** When working on dev features, squashing changes back into `001_initial.py` is acceptable to avoid file pollution, but the user must be notified to recreate database volumes (`docker-compose down -v`).
*   **Historical transaction prices:** Always store the stock price on the transaction date as `price_at_transaction` in the `Trade` model when a trade is first ingested.

## 2. Ingestion Pipeline & Repository Model
*   **All-In-Repository:** The pipeline must ingest and save all incoming trades for all filers detected in the feeds (even if they are not currently tracked: `is_tracked = False`).
*   **Auto-discovery:** If a trade belongs to an unknown person, create a new `TargetPerson` record in the database with `is_tracked = False`.
*   **Resource Conservation:** Skip CPU/API-heavy processes (like LLM evaluations, notifications, and yfinance updates) for untracked persons during sync. Perform them *exclusively* for tracked target persons (`is_tracked = True`).

## 3. Frontend & Widget Rules
*   **Starred-First Sorting:** In the portfolios tab dashboard, always sort followed (starred) profiles (`is_followed = true`) to the top, ordered alphabetically A-Z. Unfollowed profiles appear below them, also A-Z.
*   **Fallback Avatars:** If a target person's Wikipedia/Wikimedia photo fails to load (due to homelab network restrictions or broken hotlinks), do not show a broken image icon. Always fall back to a dynamic CSS-colored avatar showing their initials (e.g. "Nancy Pelosi" -> "NP") using a deterministic HSL color hash generated from their name.
*   **Performance Since Purchase:** Display the actual return since transaction date on trades (calculated from `price_at_transaction` to `current_price`) instead of a generic year-to-date (YTD) performance. Show "Avg. Trade Return" on the person card.
*   **Safety Prompts:** Wrap destructive actions (like removing a person from the dashboard) in a custom **in-app modal dialog** — never `window.confirm`. The modal should show person info, a clear description of consequences, and Cancel/Confirm buttons.

## 4. Data Sources Architecture
*   **House/Senate (Free, No Key):** `HouseStockWatcherProvider` pulls from the full S3 bulk JSON (all trades since ~2012). `SenateStockWatcherProvider` loads the full GitHub aggregate JSON. Both are open-access, no API key required.
*   **SEC 13F (Fund Managers, Free, No Key):** `SEC13FProvider` queries the official `data.sec.gov` REST API. Fund CIKs are stored as `config_json["cik_list"]` (comma-separated numbers) in the `DataSourceConfig` DB row. Quarterly holdings snapshots are ingested as synthetic `BUY` trades on the filing date.
    - Default seeded CIKs: `2045724` = Situational Awareness LP (Aschenbrenner), `1067983` = Berkshire Hathaway (Buffett)
    - Discover new CIKs: `https://data.sec.gov/submissions/CIK{10-digit-zero-padded}.json`
*   **Quiver Quantitative:** Intentionally stubbed (`return []`). Requires $30/mo paid subscription. Do NOT implement unless user explicitly provides an API key.
*   **Pipeline Deduplication:** The `(ticker, person_id, trade_date, amount_range)` composite check in `pipeline.py` ensures re-running the full bulk dataset safely skips already-stored trades.
*   **yfinance Rate Limits:** Historical price lookups use a 2s fixed delay + exponential backoff (2s→6s→18s). A `_price_cache` dict deduplicates `(ticker, date)` lookups within one pipeline run.

