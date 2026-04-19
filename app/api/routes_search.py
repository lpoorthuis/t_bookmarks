from __future__ import annotations

import json

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
    sort_by: str | None = None,
    sort_order: str = "desc",
    filters: str | None = None,
):
    search_service = request.app.state.search_service
    parsed_filters = []
    if filters:
        try:
            parsed_filters = json.loads(filters)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid filters JSON") from exc
    return search_service.search(
        query=q,
        filters={
            "active_only": active_only,
            "author": author,
            "has_media": has_media,
            "lang": lang,
            "rules": parsed_filters,
        },
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/search/properties")
async def search_properties(request: Request):
    return {"properties": request.app.state.search_service.list_properties()}


@router.get("/post/{post_id}")
async def get_post(request: Request, post_id: str):
    post = request.app.state.search_service.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post
