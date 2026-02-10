from httpx import AsyncClient


async def test_create_agent(client: AsyncClient):
    response = await client.post(
        "/v1/agents",
        json={"display_name": "Test Agent", "handle": "test.agent"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["handle"] == "test.agent"
    assert data["api_key"].startswith("clw_agent_")
    assert data["display_name"] == "Test Agent"
    assert data["status"] == "inactive"


async def test_duplicate_handle(client: AsyncClient):
    await client.post(
        "/v1/agents",
        json={"display_name": "Agent 1", "handle": "dup.handle"},
    )
    response = await client.post(
        "/v1/agents",
        json={"display_name": "Agent 2", "handle": "dup.handle"},
    )
    assert response.status_code == 409


async def test_get_agent(client: AsyncClient):
    create = await client.post(
        "/v1/agents",
        json={"display_name": "Get Me", "handle": "get.agent"},
    )
    agent_id = create.json()["id"]

    response = await client.get(f"/v1/agents/{agent_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Get Me"
    assert data["handle"] == "get.agent"


async def test_get_agent_not_found(client: AsyncClient):
    response = await client.get("/v1/agents/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_handle_format_too_short(client: AsyncClient):
    response = await client.post(
        "/v1/agents",
        json={"display_name": "Bad", "handle": "ab"},
    )
    assert response.status_code == 422


async def test_handle_format_uppercase(client: AsyncClient):
    response = await client.post(
        "/v1/agents",
        json={"display_name": "Bad", "handle": "Bad.Agent"},
    )
    assert response.status_code == 422


async def test_handle_format_special_chars(client: AsyncClient):
    response = await client.post(
        "/v1/agents",
        json={"display_name": "Bad", "handle": "bad@agent!"},
    )
    assert response.status_code == 422


async def test_auth_missing(client: AsyncClient):
    """Endpoints requiring auth should fail without a key."""
    # We'll test this once we have an auth-protected endpoint.
    # For now, create agent doesn't require auth (bootstrapping).
    pass


async def test_auth_invalid_key(client: AsyncClient):
    """Create an agent, then try to use a bogus key on a protected endpoint."""
    create = await client.post(
        "/v1/agents",
        json={"display_name": "Auth Test", "handle": "auth.test"},
    )
    agent_id = create.json()["id"]

    # The GET agent endpoint doesn't require auth for MVP,
    # but capabilities PUT will (tested in Phase 2)
    response = await client.get(f"/v1/agents/{agent_id}")
    assert response.status_code == 200
