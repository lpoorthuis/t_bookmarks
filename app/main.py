from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes_auth import router as auth_router
from app.api.routes_search import router as search_router
from app.api.routes_status import router as status_router
from app.api.routes_sync import router as sync_router
from app.auth.oauth_client import OAuthClient
from app.auth.service import AuthService
from app.auth.token_store import TokenStore
from app.config import settings
from app.db.sqlite import Database
from app.search.service import SearchService
from app.sync.bookmark_sync import BookmarkSyncService
from app.xapi.client import XApiClient


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "ui" / "templates"))


async def periodic_sync_loop(app: FastAPI) -> None:
    interval_seconds = max(60, settings.sync_interval_minutes * 60)
    while True:
        try:
            if app.state.auth_service.get_auth_status()["connected"] and not app.state.sync_service.is_running():
                app.state.sync_service.start_sync(full=False)
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = Database(settings.database_path)
    db.initialize(BASE_DIR / "db" / "schema.sql")

    x_client = XApiClient(settings)
    token_store = TokenStore(db)
    auth_service = AuthService(OAuthClient(settings), token_store, x_client)
    search_service = SearchService(db)
    sync_service = BookmarkSyncService(db, auth_service, x_client, search_service)

    app.state.db = db
    app.state.auth_service = auth_service
    app.state.search_service = search_service
    app.state.sync_service = sync_service

    background_task = asyncio.create_task(periodic_sync_loop(app))
    try:
        yield
    finally:
        background_task.cancel()
        with suppress(asyncio.CancelledError):
            await background_task


app = FastAPI(title="t_bookmarks", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "ui" / "static")), name="static")

app.include_router(auth_router)
app.include_router(sync_router)
app.include_router(search_router)
app.include_router(status_router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return TEMPLATES.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": "t_bookmarks"},
    )
