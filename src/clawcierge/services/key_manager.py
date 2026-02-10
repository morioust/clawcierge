import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clawcierge.models.api_key import ApiKey

# Base62 alphabet for key encoding
_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _base62_encode(data: bytes) -> str:
    num = int.from_bytes(data, "big")
    if num == 0:
        return _ALPHABET[0]
    chars = []
    while num:
        num, rem = divmod(num, 62)
        chars.append(_ALPHABET[rem])
    return "".join(reversed(chars))


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


@dataclass
class AuthContext:
    owner_type: str
    owner_id: uuid.UUID
    scopes: list[str]
    key_id: uuid.UUID


async def generate_api_key(
    session: AsyncSession,
    owner_type: str,
    owner_id: uuid.UUID,
    scopes: list[str] | None = None,
) -> str:
    """Generate a new API key, store the hash, return the plaintext key (shown once)."""
    raw_bytes = secrets.token_bytes(32)
    encoded = _base62_encode(raw_bytes)

    prefix_label = "clw_agent_" if owner_type == "agent" else "clw_sender_"
    raw_key = f"{prefix_label}{encoded}"

    key_hash = _hash_key(raw_key)
    key_prefix = raw_key[:16]

    api_key = ApiKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        owner_type=owner_type,
        owner_id=owner_id,
        scopes=scopes or [],
    )
    session.add(api_key)
    await session.flush()

    return raw_key


async def validate_api_key(session: AsyncSession, raw_key: str) -> AuthContext | None:
    """Validate an API key and return the auth context, or None if invalid."""
    key_hash = _hash_key(raw_key)

    result = await session.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.revoked_at.is_(None),
        )
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        return None

    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        return None

    return AuthContext(
        owner_type=api_key.owner_type,
        owner_id=api_key.owner_id,
        scopes=api_key.scopes,
        key_id=api_key.id,
    )
