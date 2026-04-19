from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status")
async def app_status(request: Request):
    auth_service = request.app.state.auth_service
    sync_service = request.app.state.sync_service
    db = request.app.state.db
    with db.connect() as connection:
        bookmark_count = connection.execute(
            "SELECT COUNT(*) AS count FROM bookmarks WHERE is_bookmarked = 1"
        ).fetchone()["count"]
    return {
        "connected": auth_service.get_auth_status()["connected"],
        "last_sync_at": sync_service.latest_sync_timestamp(),
        "bookmark_count": bookmark_count,
        "sync": sync_service.get_sync_status(),
    }
