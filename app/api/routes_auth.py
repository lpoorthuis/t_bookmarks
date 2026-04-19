from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.auth.service import AuthError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request):
    auth_service = request.app.state.auth_service
    try:
        redirect_url = auth_service.create_login_redirect()
    except AuthError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    auth_service = request.app.state.auth_service
    if error:
        raise HTTPException(status_code=400, detail=error)
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    try:
        await auth_service.handle_callback(code, state)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url="/", status_code=302)


@router.get("/status")
async def status(request: Request):
    return request.app.state.auth_service.get_auth_status()


@router.post("/logout")
async def logout(request: Request):
    request.app.state.auth_service.logout()
    return {"ok": True}
