import logging
import os
from typing import Annotated

from fastapi import Depends, FastAPI, Response
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_engine

logger = logging.getLogger(__name__)

app = FastAPI()

instrumentator = Instrumentator(excluded_handlers=["/metrics", "/healthz/.*"])
instrumentator.instrument(app).expose(app)


@app.get("/healthz/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/healthz/ready")
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


@app.get("/api/version")
def version() -> dict[str, str]:
    return {"version": os.getenv("APP_VERSION", "dev")}
