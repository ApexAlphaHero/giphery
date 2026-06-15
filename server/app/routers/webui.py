"""Admin web console: server-rendered login + invitation management."""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import any_user_exists
from app.auth.rate_limit import limiter
from app.config import get_settings
from app.db import get_session
from app.models.user import ROLE_ADMIN, User
from app.schemas.errors import ApiError
from app.services import auth_service
from app.services import invites as invite_service
from app.services.users import create_user
from app.webui import security

settings = get_settings()
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "webui" / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(include_in_schema=False)


def _redirect(url: str) -> RedirectResponse:
    # 303 so the browser issues a GET after a POST (PRG pattern).
    return RedirectResponse(url, status_code=303)


def _parse_expires(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # HTML datetime-local has no tz → treat as UTC.
        return datetime.fromisoformat(value).replace(tzinfo=UTC)
    except ValueError:
        return None


async def _render(
    request: Request,
    response: Response,
    name: str,
    *,
    admin: User | None = None,
    **ctx: object,
) -> HTMLResponse:
    csrf = security.issue_csrf(request, response)
    page = templates.TemplateResponse(request, name, {"csrf_token": csrf, "admin": admin, **ctx})
    # Carry over any Set-Cookie headers accumulated on `response`.
    for key, value in response.headers.items():
        if key.lower() == "set-cookie":
            page.headers.append("set-cookie", value)
    return page


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> Response:
    if not await any_user_exists(session):
        return _redirect("/setup")
    admin = await security.current_admin(request, response, session)
    if admin is None:
        return _redirect("/login")
    return await _dashboard(request, response, session, admin)


async def _dashboard(
    request: Request,
    response: Response,
    session: AsyncSession,
    admin: User,
    *,
    new_code: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    invites = await invite_service.list_invites(session)
    # Resolve redeemer usernames for display.
    redeemer_ids = {inv.redeemed_by for inv in invites if inv.redeemed_by}
    names: dict[uuid.UUID, str] = {}
    if redeemer_ids:
        rows = await session.execute(
            select(User.id, User.username).where(User.id.in_(redeemer_ids))
        )
        names = {row[0]: row[1] for row in rows.all()}
    view = [
        {
            "id": inv.id,
            "code": invite_service.display_code(inv),
            "label": inv.label,
            "status": invite_service.derive_status(inv),
            "uses_count": inv.uses_count,
            "max_uses": inv.max_uses,
            "redeemed_by": names.get(inv.redeemed_by) if inv.redeemed_by else None,
            "expires_at": inv.expires_at,
            "created_at": inv.created_at,
        }
        for inv in invites
    ]
    return await _render(
        request,
        response,
        "dashboard.html",
        admin=admin,
        invites=view,
        new_code=new_code,
        error=error,
    )


# --- Setup ---------------------------------------------------------------
@router.get("/setup", response_class=HTMLResponse)
async def setup_page(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> Response:
    if await any_user_exists(session):
        return _redirect("/login")
    return await _render(request, response, "setup.html")


@router.post("/setup", response_class=HTMLResponse)
async def setup_submit(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> Response:
    if not security.validate_csrf(request, csrf_token):
        return _redirect("/setup")
    if await any_user_exists(session):
        return _redirect("/login")
    try:
        user = await create_user(session, username=username, password=password, role=ROLE_ADMIN)
    except ApiError as exc:
        return await _render(request, response, "setup.html", error=exc.message)
    tokens = await auth_service.issue_tokens_for_new_device(
        session, user, device_name=user.username, platform="web"
    )
    redirect = _redirect("/")
    security.set_session_cookies(redirect, tokens.access_token, tokens.refresh_token)
    return redirect


# --- Login / logout ------------------------------------------------------
@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> Response:
    if not await any_user_exists(session):
        return _redirect("/setup")
    return await _render(request, response, "login.html")


@router.post("/login", response_class=HTMLResponse)
@limiter.limit(settings.rate_limit_login)
async def login_submit(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> Response:
    if not security.validate_csrf(request, csrf_token):
        return await _render(request, response, "login.html", error="Invalid session, try again.")
    try:
        user, tokens = await auth_service.login(
            session, username=username, password=password, platform="web"
        )
    except ApiError:
        return await _render(request, response, "login.html", error="Invalid username or password.")
    if user.role != ROLE_ADMIN:
        return await _render(request, response, "login.html", error="Admin access required.")
    redirect = _redirect("/")
    security.set_session_cookies(redirect, tokens.access_token, tokens.refresh_token)
    return redirect


@router.post("/logout")
async def logout(
    request: Request,
    csrf_token: str = Form(...),
) -> Response:
    redirect = _redirect("/login")
    if security.validate_csrf(request, csrf_token):
        security.clear_session_cookies(redirect)
    return redirect


# --- Invitations ---------------------------------------------------------
@router.post("/invites", response_class=HTMLResponse)
async def create_invite(
    request: Request,
    response: Response,
    label: str = Form(default=""),
    max_uses: int = Form(default=1),
    expires_at: str = Form(default=""),
    csrf_token: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> Response:
    admin = await security.current_admin(request, response, session)
    if admin is None:
        return _redirect("/login")
    if not security.validate_csrf(request, csrf_token):
        return await _dashboard(request, response, session, admin, error="Invalid session.")
    _invite, code = await invite_service.create_invite(
        session,
        admin=admin,
        label=label.strip() or None,
        max_uses=max(1, min(max_uses, 1000)),
        expires_at=_parse_expires(expires_at),
    )
    return await _dashboard(request, response, session, admin, new_code=code)


@router.post("/invites/{invite_id}/revoke", response_class=HTMLResponse)
async def revoke_invite(
    invite_id: uuid.UUID,
    request: Request,
    response: Response,
    csrf_token: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> Response:
    admin = await security.current_admin(request, response, session)
    if admin is None:
        return _redirect("/login")
    if security.validate_csrf(request, csrf_token):
        with contextlib.suppress(ApiError):
            await invite_service.revoke_invite(session, invite_id, admin=admin)
    return _redirect("/")
