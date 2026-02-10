from httpx import AsyncClient


async def test_resolve_handle(client: AsyncClient):
    create = await client.post(
        "/v1/agents",
        json={"display_name": "Resolve Me", "handle": "resolve.me"},
    )
    assert create.status_code == 201

    response = await client.post(
        "/v1/directory/resolve",
        json={"handle": "resolve.me"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Resolve Me"
    assert data["handle"] == "resolve.me"
    assert data["agent_id"] == create.json()["id"]


async def test_resolve_nonexistent(client: AsyncClient):
    response = await client.post(
        "/v1/directory/resolve",
        json={"handle": "does.not.exist"},
    )
    assert response.status_code == 404
