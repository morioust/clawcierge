import uuid
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from clawcierge.database import get_session
from clawcierge.models.agent import Agent
from clawcierge.services.connection_manager import connection_manager

ADMIN_PASSWORD = "oiaerjv0a8erh3248f34"
COOKIE_NAME = "clawcierge_admin"
SECRET_KEY = "clawcierge-admin-signing-key"

_signer = URLSafeSerializer(SECRET_KEY)

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

router = APIRouter(prefix="/admin", tags=["admin"])


def _verify_cookie(admin_session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> bool:
    if admin_session is None:
        return False
    try:
        return _signer.loads(admin_session) == "authenticated"
    except BadSignature:
        return False


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    error_msg = "Invalid password." if request.query_params.get("error") else None
    return templates.TemplateResponse(request, "admin_login.html", {"error": error_msg})


@router.post("/login")
async def login(password: str = Form(...)):
    if password != ADMIN_PASSWORD:
        return RedirectResponse("/admin/login?error=1", status_code=303)
    response = RedirectResponse("/admin/", status_code=303)
    token = _signer.dumps("authenticated")
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
    return response


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    is_admin: bool = Depends(_verify_cookie),
    session: AsyncSession = Depends(get_session),
):
    if not is_admin:
        return RedirectResponse("/admin/login", status_code=303)

    result = await session.execute(
        select(Agent).options(selectinload(Agent.handle)).order_by(Agent.created_at.desc())
    )
    agents = list(result.scalars().all())

    # Attach heartbeat info from connection manager
    for agent in agents:
        conn = connection_manager.get_connection(agent.id)
        if conn:
            agent.last_heartbeat = conn.last_heartbeat.strftime("%Y-%m-%d %H:%M")  # type: ignore[attr-defined]
        else:
            agent.last_heartbeat = None  # type: ignore[attr-defined]

    return templates.TemplateResponse(request, "admin_dashboard.html", {"agents": agents})


@router.post("/agents/{agent_id}/delete")
async def delete_agent(
    agent_id: uuid.UUID,
    is_admin: bool = Depends(_verify_cookie),
    session: AsyncSession = Depends(get_session),
):
    if not is_admin:
        return RedirectResponse("/admin/login", status_code=303)

    result = await session.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent:
        # Disconnect WebSocket if connected
        if connection_manager.is_connected(agent_id):
            conn = connection_manager.get_connection(agent_id)
            if conn:
                try:
                    await conn.websocket.close(code=1000, reason="Deleted by admin")
                except Exception:
                    pass
            await connection_manager.remove(agent_id)
        await session.delete(agent)
        await session.commit()
    return RedirectResponse("/admin/", status_code=303)


@router.get("/logout")
async def logout():
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response
