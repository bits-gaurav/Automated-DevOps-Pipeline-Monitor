from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
import os


app = FastAPI()


@app.get("/")
async def index():
    return PlainTextResponse("Hello from demo app!")


@app.get("/health")
async def health():
    # Set this to True to intentionally fail the pipeline for testing
    FORCE_FAILURE = False
    
    if FORCE_FAILURE:
        return JSONResponse({"status": "unhealthy"}, status_code=500)
    return {"status": "ok"}