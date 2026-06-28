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

# We keep a list of known persons to seed their committee affiliations,
# which helps the AI evaluate the risk of their trades.
SEED_PERSONS = [
    {
        "name": "Nancy Pelosi", "category": "Congress", 
        "committees": ["Financial Services", "Appropriations"],
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/Nancy_Pelosi_2019_official_portrait.jpg/320px-Nancy_Pelosi_2019_official_portrait.jpg",
        "description": "Heavy focus on Big Tech and Semiconductors. Often trades options on mega-cap tech stocks, known for highly profitable, market-timing plays."
    },
    {
        "name": "Tommy Tuberville", "category": "Senate", 
        "committees": ["Armed Services", "Agriculture", "Veterans' Affairs"],
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/Senator_Tommy_Tuberville_Official_Portrait.jpg/320px-Senator_Tommy_Tuberville_Official_Portrait.jpg",
        "description": "High volume trader across agriculture, infrastructure, and defense sectors. Trades often align with Armed Services committee knowledge."
    },
    {
        "name": "Dan Crenshaw", "category": "Congress", 
        "committees": ["Energy and Commerce", "Intelligence"],
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Dan_Crenshaw_118th_Congress_portrait.jpg/320px-Dan_Crenshaw_118th_Congress_portrait.jpg",
        "description": "Focuses primarily on tech and defense. Notable trades include AI infrastructure and cybersecurity."
    },
    {
        "name": "Mark Green", "category": "Congress", 
        "committees": ["Homeland Security", "Armed Services"],
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f6/Mark_Green_official_photo.jpg/320px-Mark_Green_official_photo.jpg",
        "description": "Massive trading volume in energy pipelines, natural gas, and defense contractors. Frequent high-value transactions."
    },
    {
        "name": "Sheldon Whitehouse", "category": "Senate", 
        "committees": ["Judiciary", "Budget", "Environment"],
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Sheldon_Whitehouse_official_portrait.jpg/320px-Sheldon_Whitehouse_official_portrait.jpg",
        "description": "Trades primarily in diversified blue-chip stocks and healthcare, often intersecting with environmental and budgetary matters."
    },
    {
        "name": "Josh Gottheimer", "category": "Congress", 
        "committees": ["Financial Services"],
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Josh_Gottheimer_official_photo.jpg/320px-Josh_Gottheimer_official_photo.jpg",
        "description": "One of the most active traders in Congress. Diversified portfolio with a strong emphasis on options trading and tech."
    },
    {
        "name": "Michael McCaul", "category": "Congress", 
        "committees": ["Foreign Affairs", "Homeland Security"],
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/98/Michael_McCaul_official_photo.jpg/320px-Michael_McCaul_official_photo.jpg",
        "description": "Trades frequently in tech, semiconductors, and cybersecurity, raising conflict-of-interest questions due to his Foreign Affairs chairmanship."
    },
    {
        "name": "John Hickenlooper", "category": "Senate", 
        "committees": ["Commerce", "Energy", "Health"],
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ad/John_Hickenlooper_Official_Portrait_2021.jpg/320px-John_Hickenlooper_Official_Portrait_2021.jpg",
        "description": "Focuses on tech giants, telecom, and energy infrastructure, leveraging broad committee assignments."
    },
    {
        "name": "Ro Khanna", "category": "Congress", 
        "committees": ["Armed Services", "Oversight"],
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ae/Ro_Khanna_Official_Portrait.jpg/320px-Ro_Khanna_Official_Portrait.jpg",
        "description": "High volume trader (often through family trusts) heavily concentrated in Silicon Valley tech stocks, defense, and healthcare."
    },
    {
        "name": "Cathie Wood", "category": "Fund Manager", 
        "committees": ["ARK Invest"],
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Cathie_Wood_-_World_Economic_Forum_Annual_Meeting_2024.jpg/320px-Cathie_Wood_-_World_Economic_Forum_Annual_Meeting_2024.jpg",
        "description": "Focuses purely on disruptive innovation. High volatility portfolio including genomics, AI, blockchain, and space exploration."
    },
    {
        "name": "Warren Buffett", "category": "Fund Manager",
        "committees": ["Berkshire Hathaway"],
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/51/Warren_Buffett_at_the_2015_SelectUSA_Investment_Summit.jpg/320px-Warren_Buffett_at_the_2015_SelectUSA_Investment_Summit.jpg",
        "description": "Legendary value investor, Chairman and CEO of Berkshire Hathaway. Known for long-term investments in high-quality businesses."
    },
    {
        "name": "Elon Musk", "category": "Corporate Insider",
        "committees": ["Tesla", "SpaceX"],
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9d/Elon_Musk_Colorado_2022_%28cropped%29.jpg/320px-Elon_Musk_Colorado_2022_%28cropped%29.jpg",
        "description": "CEO @ Tesla. Known for high-profile stock sales and option exercises."
    },
    {
        "name": "Jensen Huang", "category": "Corporate Insider",
        "committees": ["NVIDIA"],
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c4/Jensen_Huang_at_CES_2018_%28cropped%29.jpg/320px-Jensen_Huang_at_CES_2018_%28cropped%29.jpg",
        "description": "CEO & Founder @ NVIDIA. Highly tracked for his systematic sales of NVIDIA stock."
    },
    {
        "name": "Oliver Dörre", "category": "Corporate Insider",
        "committees": ["HENSOLDT AG"],
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/User_icon_2.svg/320px-User_icon_2.svg.png",
        "description": "CEO @ HENSOLDT AG. Regular purchaser of HENSOLDT shares under European directors' dealings disclosures."
    },
    {
        "name": "Christian Sewing", "category": "Corporate Insider",
        "committees": ["Deutsche Bank AG"],
        "photo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/User_icon_2.svg/320px-User_icon_2.svg.png",
        "description": "CEO @ Deutsche Bank AG. Regularly acquires Deutsche Bank stock as part of investment and compensation disclosures."
    },
]


def seed_database(db: Session) -> bool:
    """Seed the database with initial configurations and target persons if they are missing."""
    seeded = False

    # 1. Seed Target Persons individually if missing
    logger.info("Checking target persons...")
    for p in SEED_PERSONS:
        existing = db.query(TargetPerson).filter(TargetPerson.name == p["name"]).first()
        if not existing:
            logger.info(f"Seeding target person: {p['name']}")
            person = TargetPerson(
                name=p["name"], category=p["category"],
                committee_affiliations=p["committees"],
                photo_url=p.get("photo_url"),
                description=p.get("description"),
                is_tracked=True,
                is_active=True,
                is_followed=p["name"] in ["Nancy Pelosi", "Tommy Tuberville", "Warren Buffett", "Jensen Huang"],
            )
            db.add(person)
            seeded = True

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
        ("sec13f", "SEC 13F (Fund Managers)"),
        ("sec_form4", "SEC Form 4 (Corporate Insiders)"),
        ("directors_dealings", "Directors' Dealings (DAX / Europe)"),
    ]
    for p_type, name in default_sources:
        existing = db.query(DataSourceConfig).filter(DataSourceConfig.provider_type == p_type).first()
        if not existing:
            logger.info(f"Seeding default Data Source: {name}")
            ds_config = DataSourceConfig(
                provider_type=p_type, name=name,
                config_json={}, is_enabled=True
            )
            db.add(ds_config)
            seeded = True

    if seeded:
        db.commit()
        logger.info("Database seeding completed.")
    return seeded
