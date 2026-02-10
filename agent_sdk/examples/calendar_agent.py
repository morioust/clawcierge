"""Example calendar agent that connects to Clawcierge and handles scheduling requests."""

import argparse
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from agent_sdk.client import ClawciergeAgent


async def handle_request(action: str, params: dict[str, Any], sender_id: str) -> dict[str, Any]:
    """Handle incoming requests from the platform."""
    if action == "calendar.schedule":
        title = params.get("title", "Untitled")
        duration = params.get("duration_minutes", 30)

        # Mock: pick a time slot (next available hour)
        scheduled_time = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        ) + timedelta(hours=1)

        return {
            "event_id": str(uuid.uuid4()),
            "title": title,
            "scheduled_time": scheduled_time.isoformat(),
            "duration_minutes": duration,
            "status": "confirmed",
        }

    return {"error": f"Unknown action: {action}"}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Clawcierge Calendar Agent")
    parser.add_argument("--url", required=True, help="WebSocket URL")
    parser.add_argument("--token", required=True, help="Agent API key")
    args = parser.parse_args()

    agent = ClawciergeAgent()
    agent.on_request(handle_request)

    print(f"Connecting to {args.url}...")
    await agent.connect(args.url, args.token)


if __name__ == "__main__":
    asyncio.run(main())
