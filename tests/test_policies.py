from httpx import AsyncClient


async def _create_agent(client: AsyncClient, handle: str = "pol.agent") -> dict:
    resp = await client.post(
        "/v1/agents",
        json={"display_name": "Policy Agent", "handle": handle},
    )
    return resp.json()


async def test_upload_policies(client: AsyncClient):
    agent = await _create_agent(client)
    response = await client.put(
        f"/v1/agents/{agent['id']}/policies",
        headers={"Authorization": f"Bearer {agent['api_key']}"},
        json={
            "rules": [
                {
                    "condition": "sender_id == 'blocked_user'",
                    "action": "reject",
                    "reason": "User is blocked",
                }
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == 1
    assert data["is_active"] is True


async def test_upload_policies_versioning(client: AsyncClient):
    agent = await _create_agent(client, "pol.ver")
    headers = {"Authorization": f"Bearer {agent['api_key']}"}

    resp1 = await client.put(
        f"/v1/agents/{agent['id']}/policies",
        headers=headers,
        json={"rules": [{"condition": "True", "action": "reject", "reason": "v1"}]},
    )
    assert resp1.json()["version"] == 1

    resp2 = await client.put(
        f"/v1/agents/{agent['id']}/policies",
        headers=headers,
        json={"rules": [{"condition": "True", "action": "reject", "reason": "v2"}]},
    )
    assert resp2.json()["version"] == 2


async def test_upload_invalid_expression(client: AsyncClient):
    agent = await _create_agent(client, "pol.bad")
    response = await client.put(
        f"/v1/agents/{agent['id']}/policies",
        headers={"Authorization": f"Bearer {agent['api_key']}"},
        json={
            "rules": [
                {
                    "condition": "import os",
                    "action": "reject",
                    "reason": "bad",
                }
            ]
        },
    )
    assert response.status_code == 422
