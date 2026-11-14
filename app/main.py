from fastapi import FastAPI

app = FastAPI()


@app.get("/healthz/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}
