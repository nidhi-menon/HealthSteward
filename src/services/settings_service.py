"""Runtime-editable app settings, overlaid on env defaults (DEC-016).

`src/config.py`'s `Settings` (env-file-backed, cached via `lru_cache`) remains
the fallback layer for a fresh install. This module lets the LLM provider and
its connection details be changed at runtime from the Settings UI, persisted
in the singleton `app_settings` DB row, without editing `.env` or restarting.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings, get_settings
from src.data.models import AppSettings

_SETTINGS_ID = "app-settings"

# Columns on AppSettings that overlay a same-named field on Settings.
_OVERLAY_FIELDS = (
    "llm_provider",
    "anthropic_api_key",
    "anthropic_model",
    "ollama_base_url",
    "ollama_model",
    "custom_llm_base_url",
    "custom_llm_api_key",
    "custom_llm_model",
)


async def _get_row(db: AsyncSession) -> AppSettings | None:
    result = await db.execute(select(AppSettings).where(AppSettings.id == _SETTINGS_ID))
    return result.scalar_one_or_none()


async def get_effective_settings(db: AsyncSession) -> Settings:
    """Env defaults overlaid with any non-null values from the DB row."""
    env_settings = get_settings()
    row = await _get_row(db)
    if row is None:
        return env_settings

    overrides = {
        field: getattr(row, field)
        for field in _OVERLAY_FIELDS
        if getattr(row, field) is not None
    }
    return env_settings.model_copy(update=overrides) if overrides else env_settings


async def update_settings(db: AsyncSession, updates: dict) -> AppSettings:
    """Upsert the singleton settings row with the given field updates."""
    row = await _get_row(db)
    if row is None:
        row = AppSettings(id=_SETTINGS_ID)
        db.add(row)

    for field, value in updates.items():
        if field in _OVERLAY_FIELDS:
            setattr(row, field, value)

    await db.flush()
    await db.refresh(row)
    return row
