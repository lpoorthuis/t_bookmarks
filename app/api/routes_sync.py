from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/start")
async def start_sync(request: Request, full: bool = True):
    sync_service = request.app.state.sync_service
    return sync_service.start_sync(full=full)


@router.get("/status")
async def sync_status(request: Request):
    return request.app.state.sync_service.get_sync_status()


@router.get("/history")
async def sync_history(request: Request, limit: int = 10):
    return {"runs": request.app.state.sync_service.get_sync_history(limit=limit)}
