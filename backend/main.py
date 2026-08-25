import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.api import api
from backend.auth import RENEWED_TOKEN_HEADER, renew_access_token
from backend.database import init_db

STATIC_PATH = os.environ.get(
    "STATIC_PATH", os.path.join(os.path.dirname(__file__), "static")
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
    docs_url="/api/docs",  # Move Swagger UI to /api/docs to avoid conflict with frontend /docs route
    redoc_url="/api/redoc",  # Move ReDoc to /api/redoc
    openapi_url="/api/openapi.json",
)

# CORS allowlist. Auth is a Bearer token in a header, not a cookie, so
# credentials are not needed -- and the wildcard-plus-credentials combination
# browsers reject outright is gone. Defaults to the production origin; set
# CORS_ORIGINS to a comma-separated list to allow more.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS", "https://pkanban.pearachute.com"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    # Without this the browser hides the renewal header from the app entirely,
    # and every session would still die at its 24h cliff.
    expose_headers=[RENEWED_TOKEN_HEADER],
    allow_headers=["*"],
)


@app.middleware("http")
async def renew_session_token(request, call_next):
    """Hand back a fresh token when the one presented is nearing expiry.

    Middleware rather than the auth dependency: there are three of those
    (get_current_user, get_current_admin, get_current_user_or_api_key) and a
    session should renew on any authenticated request, whichever one guarded
    it. API keys arrive as X-API-Key, never as a Bearer token, so they never
    reach this path -- they do not expire and have nothing to renew.
    """
    response = await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        renewed = renew_access_token(auth_header[7:])
        if renewed:
            response.headers[RENEWED_TOKEN_HEADER] = renewed

    return response

if os.path.exists(STATIC_PATH):
    app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")

app.include_router(api, prefix="/api")

# Serve documentation content files from docs/
CONTENT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs")


@app.get("/docs/{path:path}")
async def docs_handler(path: str):
    """Serve docs: .md files serve raw markdown, clean URLs serve SPA."""
    if path.endswith(".md"):
        # Serve the markdown file
        file_path = os.path.join(CONTENT_PATH, path)
        if os.path.exists(file_path):
            return FileResponse(file_path)

    # Clean URL or missing file → serve SPA
    index_path = os.path.join(STATIC_PATH, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "pkanban API is running"}


@app.get("/")
async def root():
    index_path = os.path.join(STATIC_PATH, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "pkanban API is running. Build the frontend to serve it here."}


@app.get("/{path:path}")
async def catch_all(path: str):
    """Serve index.html for all non-API, non-docs routes (SPA fallback)"""
    # Anything under /api/ reaching the fallback is an endpoint that does not
    # exist, and the SPA is the wrong answer for it: a 200 of HTML makes a
    # client's response.json() fail with a decode error rather than see a 404,
    # and makes a typo'd URL look like a working endpoint when probed by hand.
    # This is what produced the bad evidence in the auth-inconsistency report.
    if path == "api" or path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")

    index_path = os.path.join(STATIC_PATH, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "pkanban API is running"}
