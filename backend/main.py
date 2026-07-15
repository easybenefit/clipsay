import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.utils.logging import setup_logger
from backend.db import lifespan
from backend.api import router, pipeline_router, canvas_layout_router

logger = setup_logger("main")

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
    val = os.environ.get(var, "").strip()
    if val and "localhost" in val or "127.0.0.1" in val:
        logger.warning("Proxy env %s=%s detected \u2014 if AI APIs are unreachable, stop the proxy or unset this variable", var, val)

app = FastAPI(lifespan=lifespan)

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from pathlib import Path
from backend.utils.paths import DATA_ROOT

local_root = Path(
    os.environ.get("CLIPSAY_LOCAL_DIR")
    or DATA_ROOT
)
local_root.mkdir(parents=True, exist_ok=True)
app.mount("/local", StaticFiles(directory=str(local_root)), name="local")

app.include_router(router)
app.include_router(pipeline_router)
app.include_router(canvas_layout_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(status_code=422, content={"error": str(exc)})


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})
