from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.services.ai import LLMGateway

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "hireos-ai-backend",
        "provider_status": LLMGateway().provider_status(),
        "kafka_enabled": settings.enable_kafka,
    }

