import os

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()

instrumentator = Instrumentator(excluded_handlers=["/metrics", "/healthz/.*"])
instrumentator.instrument(app).expose(app)


@app.get("/healthz/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/version")
def version() -> dict[str, str]:
    return {"version": os.getenv("APP_VERSION", "dev")}
