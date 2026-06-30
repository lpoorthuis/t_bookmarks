"""Read-only X API cost probe for calibrating spend after recharging credits.

It makes ONE real bookmarks request (this costs a few credits — that is the
point) and prints the billable footprint plus a USD estimate. It does NOT write
to the bookmarks/posts tables, so it does not change your synced data.

How to use it (the recharge experiment):

    1. Note your credit balance in the X Developer Console.
    2. Run:   uv run python -m scripts.probe_cost
    3. Refresh the Console and compare the balance DROP to the printed TOTAL.

Measured on this account: a 99-post page with 74 authors + 35 media cost $0.10
(= 99 x $0.001). Only the bookmarked posts are billed; expansion authors and
media are free. So the cost depends on how many posts you read across UTC days,
not on the author expansion. Re-running the same UTC day should cost ~$0 (dedup).

The Console balance is the source of truth. The GET /2/usage/tweets cross-check
is optional and often returns 403 with this app's user token (it is a
project-level endpoint that needs app-only access); the probe just skips it then.
"""

from __future__ import annotations

import argparse
import asyncio
import json

import httpx

from app.auth.oauth_client import OAuthClient
from app.auth.service import AuthError, AuthService
from app.auth.token_store import TokenStore
from app.config import BASE_DIR, settings
from app.db.sqlite import Database
from app.xapi.client import XApiClient, estimate_cost, summarize_footprint


async def _try_usage(x_client: XApiClient, access_token: str) -> str:
    """Return the usage payload as text, or a short reason why it is unavailable."""
    try:
        payload = await x_client.get_usage(access_token)
        return json.dumps(payload)
    except httpx.HTTPStatusError as exc:
        return f"unavailable (HTTP {exc.response.status_code} — usage endpoint needs app-only access)"
    except (AuthError, httpx.HTTPError, RuntimeError) as exc:
        return f"unavailable ({exc})"


async def _run(include_authors: bool, max_results: int) -> None:
    db = Database(settings.database_path)
    db.initialize(BASE_DIR / "app" / "db" / "schema.sql")

    token_store = TokenStore(db)
    x_client = XApiClient(settings)
    auth_service = AuthService(OAuthClient(settings), token_store, x_client)

    try:
        access_token = await auth_service.get_valid_access_token()
        user_id = auth_service.get_current_user_id()
    except AuthError as exc:
        print(f"Not connected to X: {exc}")
        print("Connect first by running the app and authorizing at /auth/login.")
        return

    usage_before = await _try_usage(x_client, access_token)
    payload = await x_client.get_bookmarks_page(
        access_token,
        user_id,
        max_results=max_results,
        include_author_expansion=include_authors,
    )
    usage_after = await _try_usage(x_client, access_token)

    footprint = summarize_footprint(payload)
    cost = estimate_cost(footprint, settings)

    print("=== X API cost probe (1 real bookmarks request) ===")
    print(f"include_author_expansion : {include_authors}")
    print(f"max_results              : {max_results}")
    print("--- footprint (this request) ---")
    print(f"posts (owned reads)      : {footprint.posts}")
    print(f"users (authors, free)    : {footprint.users}")
    print(f"media (free)             : {footprint.media}")
    print(f"referenced posts         : {footprint.referenced_posts}")
    print("--- estimated cost (upper bound; ignores 24h dedup) ---")
    print(
        f"posts   : ${cost.posts_usd:.4f}  "
        f"({footprint.posts} x ${settings.cost_owned_read_usd})"
    )
    print(f"users   : ${cost.users_usd:.4f}  (author expansion is not billed)")
    print(
        f"refs    : ${cost.referenced_usd:.4f}  "
        f"({footprint.referenced_posts} x ${settings.cost_post_read_usd})"
    )
    print(f"TOTAL   : ${cost.total_usd:.4f}")
    print("--- usage endpoint cross-check (optional) ---")
    print(f"before : {usage_before}")
    print(f"after  : {usage_after}")
    print(
        "\nNext: refresh your Developer Console balance and compare the DROP to "
        f"TOTAL (${cost.total_usd:.4f}).\n"
        "Measured on this account: only the bookmarked posts are billed "
        "($0.001 each); author/media expansions are free. The cost lever is the "
        "number of posts read across UTC days, so the main saving is fewer/"
        "smaller reads (INCREMENTAL_MAX_RESULTS) and avoiding repeat full syncs, "
        "not the author toggle."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only X API cost probe (makes one real bookmarks request)."
    )
    parser.add_argument(
        "--no-author",
        action="store_true",
        help="Fetch without the author_id expansion to compare the footprint.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=settings.full_max_results,
        help="Page size to request (default: FULL_MAX_RESULTS).",
    )
    args = parser.parse_args()
    asyncio.run(_run(include_authors=not args.no_author, max_results=args.max_results))


if __name__ == "__main__":
    main()
