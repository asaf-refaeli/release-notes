import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings, get_settings
from app.db import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/healthz/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/healthz/ready")
def ready(
    response: Response, engine: Annotated[Engine, Depends(get_engine)]
) -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("Readiness check failed: %s", exc)
        response.status_code = 503
        return {"status": "unavailable"}
    return {"status": "ok"}


@router.get("/api/version")
def version(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    return {"version": settings.app_version}
