"""API routes for runtime app settings — LLM provider selection (DEC-016)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import get_db
from src.models.schemas import AppSettingsResponse, AppSettingsUpdate
from src.services import settings_service

router = APIRouter(prefix="/api/settings", tags=["Settings"])


def _mask(secret: str | None) -> str | None:
    """Mask a secret to its last 4 characters, e.g. 'sk-...ab12'."""
    if not secret:
        return None
    if len(secret) <= 4:
        return "...." + secret
    return f"...{secret[-4:]}"


@router.get("/", response_model=AppSettingsResponse)
async def get_settings_route(db: AsyncSession = Depends(get_db)) -> AppSettingsResponse:
    """Get effective settings (env defaults overlaid with any DB overrides). Secrets masked."""
    effective = await settings_service.get_effective_settings(db)
    return AppSettingsResponse(
        llm_provider=effective.llm_provider,
        anthropic_api_key=_mask(effective.anthropic_api_key),
        anthropic_model=effective.anthropic_model,
        ollama_base_url=effective.ollama_base_url,
        ollama_model=effective.ollama_model,
        custom_llm_base_url=effective.custom_llm_base_url,
        custom_llm_api_key=_mask(effective.custom_llm_api_key),
        custom_llm_model=effective.custom_llm_model,
    )


@router.put("/", response_model=AppSettingsResponse)
async def update_settings_route(
    updates: AppSettingsUpdate,
    db: AsyncSession = Depends(get_db),
) -> AppSettingsResponse:
    """Update settings (e.g. switch LLM provider). Only non-null fields change."""
    payload = updates.model_dump(exclude_unset=True, exclude_none=True)
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    await settings_service.update_settings(db, payload)
    effective = await settings_service.get_effective_settings(db)
    return AppSettingsResponse(
        llm_provider=effective.llm_provider,
        anthropic_api_key=_mask(effective.anthropic_api_key),
        anthropic_model=effective.anthropic_model,
        ollama_base_url=effective.ollama_base_url,
        ollama_model=effective.ollama_model,
        custom_llm_base_url=effective.custom_llm_base_url,
        custom_llm_api_key=_mask(effective.custom_llm_api_key),
        custom_llm_model=effective.custom_llm_model,
    )
