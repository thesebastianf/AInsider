"""
AInsider Tracker – Seed Data
Populates the database with initial known persons, LLM configs, 
Notification configs, and Data Source configs.
(No mock trades are seeded; the system relies on real data sources).
"""

import logging
from sqlalchemy.orm import Session
from app.models import TargetPerson, LLMConfig, NotificationConfig, DataSourceConfig
from app.config import settings

logger = logging.getLogger("ainsider.seed")


def seed_database(db: Session) -> bool:
    """Seed the database with initial configurations and target persons if they are missing."""
    seeded = False

    # 1. Target Persons are no longer pre-seeded.
    # They will be auto-discovered by the pipeline and added to the Discover tab.
    # 2. Seed LLM config
    existing_llm = db.query(LLMConfig).count()
    if existing_llm == 0:
        logger.info("Seeding LLM configurations...")
        if settings.SEED_LLM_PROVIDER and settings.SEED_LLM_URL and settings.SEED_LLM_MODEL:
            llm_config = LLMConfig(
                provider_type=settings.SEED_LLM_PROVIDER,
                name=f"Seeded {settings.SEED_LLM_PROVIDER.title()}",
                api_url=settings.SEED_LLM_URL,
                model_name=settings.SEED_LLM_MODEL,
                api_key=settings.SEED_LLM_API_KEY,
                is_active=True,
            )
            db.add(llm_config)
        else:
            default_llm = LLMConfig(
                provider_type="ollama", name="Local Ollama",
                api_url="http://localhost:11434", model_name="llama3",
                is_active=False,
            )
            db.add(default_llm)
        seeded = True

    # 3. Seed Notification config
    existing_notify = db.query(NotificationConfig).count()
    if existing_notify == 0 and settings.SEED_NOTIFY_PROVIDER and settings.SEED_NOTIFY_CONFIG:
        import json
        try:
            config_json = json.loads(settings.SEED_NOTIFY_CONFIG)
            notify_config = NotificationConfig(
                provider_type=settings.SEED_NOTIFY_PROVIDER,
                name=f"Seeded {settings.SEED_NOTIFY_PROVIDER.title()}",
                config_json=config_json,
                is_enabled=True,
            )
            db.add(notify_config)
            seeded = True
        except json.JSONDecodeError:
            logger.error("Failed to parse SEED_NOTIFY_CONFIG json")

    # 4. Seed Data Source config
    logger.info("Checking default Data Sources...")
    default_sources = [
        ("house", "House Stock Watcher"),
        ("senate", "Senate Stock Watcher"),
        ("executive", "Executive Branch (OGE)"),
        ("quiver", "Quiver Quantitative"),
        ("sec13f", "SEC 13F (Superinvestors)"),
        ("sec13d", "SEC 13D (Activist Investors)"),
        ("sec_form4", "SEC Form 4 (SEC EDGAR - Free)"),
        ("finnhub", "Finnhub Form 4 (Requires API Key)"),
        ("directors_dealings", "Directors' Dealings (DAX / Europe)"),
        ("social_inverse_cramer", "Inverse Cramer Tracker (Social)"),
    ]
    for p_type, name in default_sources:
        existing = db.query(DataSourceConfig).filter(DataSourceConfig.provider_type == p_type).first()
        if not existing:
            logger.info(f"Seeding default Data Source: {name}")
            # Pre-populate sec13f with known fund CIKs
            default_cfg = {}
            if p_type == "sec13f":
                default_cfg = {
                    "cik_list": "2045724,1067983,0001649339,0001336528,0001029160,0001037389,0001350694,0000921669,0001423053,0001568820",
                    "_notes": (
                        "CIKs: 2045724=Situational Awareness LP (Aschenbrenner), "
                        "1067983=Berkshire Hathaway (Buffett), "
                        "0001649339=Scion Asset Management (Burry), "
                        "0001336528=Pershing Square (Ackman), "
                        "0001029160=Duquesne Family Office (Druckenmiller), "
                        "0001037389=Renaissance Technologies (Simons), "
                        "0001350694=Bridgewater Associates (Dalio), "
                        "0000921669=Icahn Associates, "
                        "0001423053=Tudor Investment Corp (Jones), "
                        "0001568820=Point72 Asset Management (Cohen). "
                        "Add more CIKs comma-separated. Find CIKs at data.sec.gov/submissions/CIK######.json"
                    )
                }
            elif p_type == "sec13d":
                default_cfg = {
                    "cik_list": "0000921669,0001336528,0000902219,0001166559",
                    "_notes": "Carl Icahn (921669), Pershing Square (1336528), Elliott Management (902219), JANA Partners (1166559)"
                }
            elif p_type == "quiver":
                default_cfg = {
                    "api_key": "",
                    "last_status": "error",
                    "last_error": "Please provide API Key"
                }
            elif p_type == "finnhub":
                default_cfg = {
                    "api_key": "",
                    "ticker_list": "AAPL,TSLA,MSFT",
                    "_notes": "Finnhub requires specific symbols. Add more symbols comma-separated.",
                    "last_status": "error",
                    "last_error": "Please provide Finnhub API Key"
                }
            ds_config = DataSourceConfig(
                provider_type=p_type, name=name,
                config_json=default_cfg, is_enabled=(p_type not in ["quiver", "finnhub"])
            )
            db.add(ds_config)
            seeded = True

    if seeded:
        db.commit()
        logger.info("Database seeding completed.")
    return seeded
