from httpx import AsyncClient

from clawcierge.routes.admin import COOKIE_NAME


async def _login(client: AsyncClient) -> AsyncClient:
    """Log in and return the client with the auth cookie set."""
    resp = await client.post(
        "/admin/login",
        data={"password": "oiaerjv0a8erh3248f34"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    # Extract the cookie from Set-Cookie header and set it on the client
    cookie_value = resp.cookies.get(COOKIE_NAME)
    assert cookie_value is not None
    client.cookies.set(COOKIE_NAME, cookie_value)
    return client


async def test_login_wrong_password(client: AsyncClient):
    resp = await client.post(
        "/admin/login",
        data={"password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin/login?error=1"
    assert COOKIE_NAME not in resp.cookies


async def test_login_correct_password(client: AsyncClient):
    resp = await client.post(
        "/admin/login",
        data={"password": "oiaerjv0a8erh3248f34"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin/"
    assert COOKIE_NAME in resp.cookies


async def test_dashboard_requires_auth(client: AsyncClient):
    resp = await client.get("/admin/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin/login"


async def test_dashboard_lists_agents(client: AsyncClient):
    # Create an agent first
    create_resp = await client.post(
        "/v1/agents",
        json={"display_name": "Admin Test Agent", "handle": "admin.test"},
    )
    assert create_resp.status_code == 201

    # Log in
    await _login(client)

    # Access dashboard
    resp = await client.get("/admin/", follow_redirects=False)
    assert resp.status_code == 200
    assert "Admin Test Agent" in resp.text
    assert "admin.test" in resp.text


async def test_dashboard_empty(client: AsyncClient):
    await _login(client)
    resp = await client.get("/admin/", follow_redirects=False)
    assert resp.status_code == 200
    assert "No agents registered." in resp.text


async def test_delete_agent(client: AsyncClient):
    # Create an agent
    create_resp = await client.post(
        "/v1/agents",
        json={"display_name": "Delete Me", "handle": "delete.me"},
    )
    assert create_resp.status_code == 201
    agent_id = create_resp.json()["id"]

    # Log in
    await _login(client)

    # Delete the agent
    resp = await client.post(
        f"/admin/agents/{agent_id}/delete",
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin/"

    # Verify agent is gone
    get_resp = await client.get(f"/v1/agents/{agent_id}")
    assert get_resp.status_code == 404


async def test_delete_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/admin/agents/00000000-0000-0000-0000-000000000000/delete",
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin/login"


async def test_logout(client: AsyncClient):
    await _login(client)

    # Verify we can access the dashboard
    resp = await client.get("/admin/", follow_redirects=False)
    assert resp.status_code == 200

    # Log out
    resp = await client.get("/admin/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin/login"

    # Clear cookie on client side (simulating browser behavior)
    client.cookies.delete(COOKIE_NAME)

    # Dashboard should redirect to login
    resp = await client.get("/admin/", follow_redirects=False)
    assert resp.status_code == 303


async def test_login_page_shows_error(client: AsyncClient):
    resp = await client.get("/admin/login?error=1")
    assert resp.status_code == 200
    assert "Invalid password." in resp.text


async def test_login_page_no_error(client: AsyncClient):
    resp = await client.get("/admin/login")
    assert resp.status_code == 200
    assert "Invalid password." not in resp.text
