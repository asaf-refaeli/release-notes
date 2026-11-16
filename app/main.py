from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import router as releases_router
from app.config import get_settings
from app.db import get_engine
from app.health import router as health_router
from app.log_config import setup_logging
from app.service import ReleaseNotFound

setup_logging(get_settings().log_level)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    engine = get_engine()
    yield
    engine.dispose()


app = FastAPI(lifespan=lifespan)

instrumentator = Instrumentator(excluded_handlers=["/metrics", "/healthz/.*"])
instrumentator.instrument(app).expose(app)

app.include_router(health_router)
app.include_router(releases_router)


@app.exception_handler(ReleaseNotFound)
async def release_not_found(request: Request, exc: ReleaseNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})
