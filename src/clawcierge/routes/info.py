from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/v1/info")
async def platform_info(request: Request) -> dict[str, Any]:
    """Machine-readable platform descriptor for AI agents."""
    base = str(request.base_url).rstrip("/")
    return {
        "name": "Clawcierge",
        "version": "0.1.0",
        "description": (
            "Secure agent registry platform. External senders submit structured "
            "requests to registered agents through an enforcement pipeline "
            "(policy rules + capability sandboxing). Agents connect via "
            "persistent WebSocket channels to receive and respond to requests."
        ),
        "authentication": {
            "type": "bearer",
            "header": "Authorization: Bearer <api_key>",
            "note": (
                "API keys are returned once on agent registration. "
                "Keys are prefixed: clw_agent_* for agents, clw_sender_* for senders."
            ),
        },
        "quickstart": {
            "steps": [
                {
                    "step": 1,
                    "action": "Register an agent",
                    "method": "POST",
                    "url": f"{base}/v1/agents",
                    "body": {"display_name": "My Agent", "handle": "my.agent"},
                    "note": "Returns api_key (shown once). Save it.",
                },
                {
                    "step": 2,
                    "action": "Upload capabilities",
                    "method": "PUT",
                    "url": f"{base}/v1/agents/{{agent_id}}/capabilities",
                    "auth": "Bearer <agent_api_key>",
                    "body": {
                        "capabilities": [
                            {
                                "action": "greet",
                                "params_schema": {
                                    "type": "object",
                                    "properties": {"name": {"type": "string"}},
                                    "required": ["name"],
                                },
                            }
                        ]
                    },
                },
                {
                    "step": 3,
                    "action": "Upload policies (optional)",
                    "method": "PUT",
                    "url": f"{base}/v1/agents/{{agent_id}}/policies",
                    "auth": "Bearer <agent_api_key>",
                    "body": {
                        "rules": [
                            {
                                "condition": "action == 'greet'",
                                "action": "allow",
                                "reason": "Greeting is always allowed",
                            }
                        ]
                    },
                },
                {
                    "step": 4,
                    "action": "Connect via WebSocket",
                    "method": "WS",
                    "url": f"{base}/v1/agents/{{agent_id}}/ws?token=<agent_api_key>",
                    "note": "Agent goes 'active' on connect, 'inactive' on disconnect.",
                },
                {
                    "step": 5,
                    "action": "Send a request to the agent",
                    "method": "POST",
                    "url": f"{base}/v1/agents/{{handle}}/requests",
                    "auth": "Bearer <any_api_key>",
                    "body": {"action": "greet", "params": {"name": "World"}},
                },
                {
                    "step": 6,
                    "action": "Poll for result",
                    "method": "GET",
                    "url": f"{base}/v1/requests/{{request_id}}",
                    "auth": "Bearer <sender_api_key>",
                },
            ],
        },
        "endpoints": [
            {
                "method": "GET",
                "path": "/health",
                "url": f"{base}/health",
                "auth": False,
                "description": "Health check",
                "response": {"status": "ok"},
            },
            {
                "method": "POST",
                "path": "/v1/agents",
                "url": f"{base}/v1/agents",
                "auth": False,
                "description": "Register a new agent with a unique handle",
                "request_body": {
                    "display_name": "string (1-200 chars)",
                    "handle": "string (3-64 chars, lowercase alphanumeric + dots)",
                },
                "response": {
                    "id": "uuid",
                    "handle": "string",
                    "api_key": "string (shown once)",
                    "display_name": "string",
                    "status": "inactive",
                },
            },
            {
                "method": "GET",
                "path": "/v1/agents/{agent_id}",
                "url": f"{base}/v1/agents/{{agent_id}}",
                "auth": False,
                "description": "Get agent details by ID",
            },
            {
                "method": "GET",
                "path": "/v1/directory/{handle}",
                "url": f"{base}/v1/directory/{{handle}}",
                "auth": False,
                "description": "Resolve a handle to an agent (includes active capabilities)",
            },
            {
                "method": "PUT",
                "path": "/v1/agents/{agent_id}/capabilities",
                "url": f"{base}/v1/agents/{{agent_id}}/capabilities",
                "auth": True,
                "auth_scope": "agent:manage",
                "description": (
                    "Upload capability contract (versioned). "
                    "Each capability has action, params_schema (JSON Schema), and constraints."
                ),
                "request_body": {
                    "capabilities": [
                        {
                            "action": "string",
                            "params_schema": "JSON Schema object (optional)",
                            "constraints": "dict (optional, e.g. max_<param>, min_<param>)",
                        }
                    ]
                },
            },
            {
                "method": "PUT",
                "path": "/v1/agents/{agent_id}/policies",
                "url": f"{base}/v1/agents/{{agent_id}}/policies",
                "auth": True,
                "auth_scope": "agent:manage",
                "description": (
                    "Upload policy rules (versioned). Rules are evaluated in order. "
                    "Conditions use safe expressions (simpleeval)."
                ),
                "request_body": {
                    "rules": [
                        {
                            "condition": "safe expression (e.g. action == 'greet')",
                            "action": "reject | allow",
                            "reason": "string (optional)",
                        }
                    ]
                },
            },
            {
                "method": "POST",
                "path": "/v1/agents/{handle}/requests",
                "url": f"{base}/v1/agents/{{handle}}/requests",
                "auth": True,
                "description": (
                    "Submit a request to an agent. Runs through enforcement pipeline "
                    "(policy engine → capability sandbox) before dispatching via WebSocket."
                ),
                "request_body": {
                    "action": "string (must match a registered capability)",
                    "params": "dict (validated against params_schema)",
                },
                "response": {
                    "id": "uuid",
                    "status": "dispatched",
                    "action_type": "string",
                },
            },
            {
                "method": "GET",
                "path": "/v1/requests/{request_id}",
                "url": f"{base}/v1/requests/{{request_id}}",
                "auth": True,
                "description": "Poll request status and result (sender must match)",
                "response": {
                    "id": "uuid",
                    "status": "pending | dispatched | acked | completed | rejected | timeout",
                    "action_type": "string",
                    "result": "dict | null",
                },
            },
            {
                "method": "WS",
                "path": "/v1/agents/{agent_id}/ws",
                "url": f"{base}/v1/agents/{{agent_id}}/ws?token=<api_key>",
                "auth": True,
                "auth_note": "Token passed as query parameter",
                "description": (
                    "Persistent WebSocket channel for agent to receive "
                    "and respond to requests"
                ),
            },
        ],
        "websocket_protocol": {
            "platform_to_agent": [
                {
                    "type": "request.received",
                    "fields": {
                        "request_id": "uuid",
                        "action": "string",
                        "params": "dict",
                        "sender_id": "string",
                    },
                },
                {
                    "type": "request.cancel",
                    "fields": {"request_id": "uuid", "reason": "string"},
                },
                {"type": "ping", "fields": {}},
            ],
            "agent_to_platform": [
                {
                    "type": "ack",
                    "fields": {"request_id": "uuid"},
                    "note": "Acknowledge receipt of a request",
                },
                {
                    "type": "action.result",
                    "fields": {
                        "request_id": "uuid",
                        "status": "completed | error",
                        "result": "dict",
                        "error": "string | null",
                    },
                    "note": "Send back the result of a completed action",
                },
                {"type": "heartbeat", "fields": {}, "note": "Keep-alive signal"},
            ],
        },
        "enforcement_pipeline": {
            "description": (
                "All requests pass through a sequential, fail-closed enforcement pipeline "
                "before reaching the agent."
            ),
            "stages": [
                {
                    "name": "Policy Engine",
                    "order": 1,
                    "description": (
                        "Evaluates policy rules against the request. "
                        "If any rule with action='reject' matches, the request is rejected."
                    ),
                },
                {
                    "name": "Capability Sandbox",
                    "order": 2,
                    "description": (
                        "Validates that the requested action exists in the agent's capability "
                        "contract, validates params against JSON Schema, and enforces constraints."
                    ),
                },
            ],
            "fail_closed": True,
            "stage_timeout_seconds": 5,
        },
    }
