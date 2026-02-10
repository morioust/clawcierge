from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from clawcierge.database import get_session
from clawcierge.errors import AuthenticationError
from clawcierge.services.key_manager import AuthContext, validate_api_key


async def get_auth_context(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AuthContext:
    """Extract and validate Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise AuthenticationError("Missing Authorization header")

    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        raise AuthenticationError("Invalid Authorization header format")

    raw_key = parts[1]
    ctx = await validate_api_key(session, raw_key)
    if ctx is None:
        raise AuthenticationError("Invalid or expired API key")

    return ctx
