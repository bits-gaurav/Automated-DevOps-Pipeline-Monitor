from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
import os


app = FastAPI()


@app.get("/")
async def index():
    return PlainTextResponse("Hello from demo app!")


@app.get("/health")
async def health():
    if os.getenv("FAIL_HEALTHCHECK", "false").lower() == "true":
        return JSONResponse({"status": "unhealthy"}, status_code=500)
    return {"status": "ok"}