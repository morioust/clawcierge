from httpx import AsyncClient


async def _create_agent(client: AsyncClient, handle: str = "cap.agent") -> dict:
    resp = await client.post(
        "/v1/agents",
        json={"display_name": "Cap Agent", "handle": handle},
    )
    return resp.json()


async def test_upload_capabilities(client: AsyncClient):
    agent = await _create_agent(client)
    response = await client.put(
        f"/v1/agents/{agent['id']}/capabilities",
        headers={"Authorization": f"Bearer {agent['api_key']}"},
        json={
            "capabilities": [
                {
                    "action": "calendar.schedule",
                    "params_schema": {
                        "type": "object",
                        "required": ["title"],
                        "properties": {"title": {"type": "string"}},
                    },
                    "constraints": {"max_duration_minutes": 120},
                }
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == 1
    assert data["is_active"] is True
    assert len(data["capabilities"]) == 1


async def test_upload_capabilities_versioning(client: AsyncClient):
    agent = await _create_agent(client, "cap.ver")
    headers = {"Authorization": f"Bearer {agent['api_key']}"}

    # First upload
    resp1 = await client.put(
        f"/v1/agents/{agent['id']}/capabilities",
        headers=headers,
        json={"capabilities": [{"action": "v1.action"}]},
    )
    assert resp1.json()["version"] == 1

    # Second upload should be version 2
    resp2 = await client.put(
        f"/v1/agents/{agent['id']}/capabilities",
        headers=headers,
        json={"capabilities": [{"action": "v2.action"}]},
    )
    assert resp2.json()["version"] == 2


async def test_upload_invalid_json_schema(client: AsyncClient):
    agent = await _create_agent(client, "cap.bad")
    response = await client.put(
        f"/v1/agents/{agent['id']}/capabilities",
        headers={"Authorization": f"Bearer {agent['api_key']}"},
        json={
            "capabilities": [
                {
                    "action": "bad.action",
                    "params_schema": {"type": "not_a_valid_type"},
                }
            ]
        },
    )
    assert response.status_code == 422


async def test_upload_capabilities_no_auth(client: AsyncClient):
    agent = await _create_agent(client, "cap.noauth")
    response = await client.put(
        f"/v1/agents/{agent['id']}/capabilities",
        json={"capabilities": [{"action": "test.action"}]},
    )
    assert response.status_code == 401
