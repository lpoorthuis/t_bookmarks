from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
async def search(
    request: Request,
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    active_only: bool = True,
    author: str | None = None,
    has_media: bool = False,
    lang: str | None = None,
):
    search_service = request.app.state.search_service
    return search_service.search(
        query=q,
        filters={
            "active_only": active_only,
            "author": author,
            "has_media": has_media,
            "lang": lang,
        },
        page=page,
        page_size=page_size,
    )


@router.get("/post/{post_id}")
async def get_post(request: Request, post_id: str):
    post = request.app.state.search_service.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post
