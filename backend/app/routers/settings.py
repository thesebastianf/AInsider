"""
AInsider Tracker – Settings Router
CRUD for LLM providers, notification providers, and app settings.
All provider configs stored in DB and editable via UI.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.config import settings
from app.models import LLMConfig, NotificationConfig, DataSourceConfig
from app.schemas import (
    LLMConfigCreate, LLMConfigOut, LLMConfigUpdate, LLMTestResult,
    NotificationConfigCreate, NotificationConfigOut, NotificationConfigUpdate,
    NotificationTestResult, AppSettingsOut, AppSettingsUpdate,
    NOTIFICATION_PROVIDER_FIELDS, DataSourceConfigCreate,
    DataSourceConfigOut, DataSourceConfigUpdate, DATASOURCE_PROVIDER_FIELDS
)

router = APIRouter(prefix="/api/settings", tags=["Settings"])

# Runtime overrides for app-level settings
_runtime_overrides = {}


# ═══════════════════════════════════════════════════════════════
# App Settings
# ═══════════════════════════════════════════════════════════════

@router.get("", response_model=AppSettingsOut)
def get_settings(db: Session = Depends(get_db)):
    """Get all application settings including provider configs."""
    llm_configs = db.query(LLMConfig).all()
    notify_configs = db.query(NotificationConfig).all()
    ds_configs = db.query(DataSourceConfig).all()

    return AppSettingsOut(
        scheduler_interval_minutes=_runtime_overrides.get(
            "scheduler_interval_minutes", settings.SCHEDULER_INTERVAL_MINUTES
        ),
        price_update_interval_minutes=_runtime_overrides.get(
            "price_update_interval_minutes", settings.PRICE_UPDATE_INTERVAL_MINUTES
        ),
        last_pipeline_run=_runtime_overrides.get("last_pipeline_run"),
        is_pipeline_running=__import__("app.state", fromlist=["app_state"]).app_state.get("is_pipeline_running", False),
        llm_providers=[
            LLMConfigOut(
                id=c.id, provider_type=c.provider_type, name=c.name,
                api_url=c.api_url, has_api_key=bool(c.api_key),
                model_name=c.model_name, is_active=c.is_active,
                created_at=c.created_at,
            ) for c in llm_configs
        ],
        notification_providers=[
            NotificationConfigOut.model_validate(c) for c in notify_configs
        ],
        data_source_providers=[
            DataSourceConfigOut.model_validate(c) for c in ds_configs
        ]
    )


@router.put("", response_model=AppSettingsOut)
def update_app_settings(update: AppSettingsUpdate = Body(...), db: Session = Depends(get_db)):
    """Update app-level settings (runtime, non-persistent)."""
    for k, v in update.model_dump(exclude_none=True).items():
        _runtime_overrides[k] = v
    return get_settings(db)


# ═══════════════════════════════════════════════════════════════
# LLM Providers
# ═══════════════════════════════════════════════════════════════

@router.get("/llm", response_model=List[LLMConfigOut])
def list_llm_providers(db: Session = Depends(get_db)):
    configs = db.query(LLMConfig).all()
    return [
        LLMConfigOut(
            id=c.id, provider_type=c.provider_type, name=c.name,
            api_url=c.api_url, has_api_key=bool(c.api_key),
            model_name=c.model_name, is_active=c.is_active,
            created_at=c.created_at,
        ) for c in configs
    ]


@router.post("/llm", response_model=LLMConfigOut, status_code=201)
def create_llm_provider(data: LLMConfigCreate, db: Session = Depends(get_db)):
    config = LLMConfig(
        provider_type=data.provider_type,
        name=data.name,
        api_url=data.api_url,
        api_key=data.api_key,
        model_name=data.model_name,
        is_active=False,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return LLMConfigOut(
        id=config.id, provider_type=config.provider_type, name=config.name,
        api_url=config.api_url, has_api_key=bool(config.api_key),
        model_name=config.model_name, is_active=config.is_active,
        created_at=config.created_at,
    )


@router.put("/llm/{config_id}", response_model=LLMConfigOut)
def update_llm_provider(config_id: int, data: LLMConfigUpdate, db: Session = Depends(get_db)):
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="LLM config not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return LLMConfigOut(
        id=config.id, provider_type=config.provider_type, name=config.name,
        api_url=config.api_url, has_api_key=bool(config.api_key),
        model_name=config.model_name, is_active=config.is_active,
        created_at=config.created_at,
    )


@router.put("/llm/{config_id}/activate")
def activate_llm_provider(config_id: int, db: Session = Depends(get_db)):
    """Set this provider as the active one (deactivates all others)."""
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="LLM config not found")
    # Deactivate all others
    db.query(LLMConfig).update({"is_active": False})
    config.is_active = True
    db.commit()
    return {"id": config.id, "is_active": True}


@router.delete("/llm/{config_id}", status_code=204)
def delete_llm_provider(config_id: int, db: Session = Depends(get_db)):
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="LLM config not found")
    db.delete(config)
    db.commit()
    return None


@router.post("/llm/{config_id}/test", response_model=LLMTestResult)
def test_llm_provider(config_id: int, db: Session = Depends(get_db)):
    """Test connectivity to an LLM provider."""
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="LLM config not found")
    from app.services.llm_provider import test_llm_connection
    success, message, response = test_llm_connection(config)
    return LLMTestResult(success=success, message=message, response=response)


# ═══════════════════════════════════════════════════════════════
# Notification Providers
# ═══════════════════════════════════════════════════════════════

@router.get("/notifications", response_model=List[NotificationConfigOut])
def list_notification_providers(db: Session = Depends(get_db)):
    return [
        NotificationConfigOut.model_validate(c)
        for c in db.query(NotificationConfig).all()
    ]


@router.get("/notifications/fields")
def get_notification_fields():
    """Get required fields for each notification provider type."""
    return NOTIFICATION_PROVIDER_FIELDS


@router.post("/notifications", response_model=NotificationConfigOut, status_code=201)
def create_notification_provider(data: NotificationConfigCreate, db: Session = Depends(get_db)):
    config = NotificationConfig(
        provider_type=data.provider_type,
        name=data.name,
        config_json=data.config_json,
        is_enabled=True,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return NotificationConfigOut.model_validate(config)


@router.put("/notifications/{config_id}", response_model=NotificationConfigOut)
def update_notification_provider(
    config_id: int, data: NotificationConfigUpdate, db: Session = Depends(get_db)
):
    config = db.query(NotificationConfig).filter(NotificationConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Notification config not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return NotificationConfigOut.model_validate(config)


@router.delete("/notifications/{config_id}", status_code=204)
def delete_notification_provider(config_id: int, db: Session = Depends(get_db)):
    config = db.query(NotificationConfig).filter(NotificationConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Notification config not found")
    db.delete(config)
    db.commit()
    return None


@router.post("/notifications/{config_id}/test", response_model=NotificationTestResult)
def test_notification_provider(config_id: int, db: Session = Depends(get_db)):
    """Send a test notification."""
    config = db.query(NotificationConfig).filter(NotificationConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Notification config not found")
    from app.services.notifier import test_notification
    success, message = test_notification(config)
    if success:
        config.last_test = datetime.now()
        db.commit()
    return NotificationTestResult(success=success, message=message)


# ═══════════════════════════════════════════════════════════════
# Data Source Providers
# ═══════════════════════════════════════════════════════════════

@router.get("/datasources", response_model=List[DataSourceConfigOut])
def list_datasource_providers(db: Session = Depends(get_db)):
    return [
        DataSourceConfigOut.model_validate(c)
        for c in db.query(DataSourceConfig).all()
    ]


@router.get("/datasources/fields")
def get_datasource_fields():
    return DATASOURCE_PROVIDER_FIELDS


@router.post("/datasources", response_model=DataSourceConfigOut, status_code=201)
def create_datasource_provider(data: DataSourceConfigCreate, db: Session = Depends(get_db)):
    config = DataSourceConfig(
        provider_type=data.provider_type,
        name=data.name,
        config_json=data.config_json,
        is_enabled=True,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return DataSourceConfigOut.model_validate(config)


@router.put("/datasources/{config_id}", response_model=DataSourceConfigOut)
def update_datasource_provider(
    config_id: int, data: DataSourceConfigUpdate, db: Session = Depends(get_db)
):
    config = db.query(DataSourceConfig).filter(DataSourceConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="DataSource config not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return DataSourceConfigOut.model_validate(config)


@router.delete("/datasources/{config_id}", status_code=204)
def delete_datasource_provider(config_id: int, db: Session = Depends(get_db)):
    config = db.query(DataSourceConfig).filter(DataSourceConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="DataSource config not found")
    db.delete(config)
    db.commit()
    return None
