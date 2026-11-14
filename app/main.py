import os

from fastapi import FastAPI

app = FastAPI()


@app.get("/healthz/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/version")
def version() -> dict[str, str]:
    return {"version": os.getenv("APP_VERSION", "dev")}
