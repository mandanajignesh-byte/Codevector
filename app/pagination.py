"""
Cursor pagination helpers.

What is a cursor?
-----------------
A cursor is an opaque token the client sends with each request
to tell the server "give me products after this point."

It encodes the sort values of the last product the client saw:

    { "created_at": "2024-01-15T10:30:00+00:00", "id": 4821 }

The server uses these values to build a WHERE clause that skips
everything the client has already seen.

Why Base64?
-----------
Base64 makes the cursor URL-safe and opaque to the client.
The client should treat it as a black box — it never needs to
read or construct cursors itself.

Why created_at + id?
--------------------
created_at alone is not enough — many products can share the
same created_at timestamp. Adding id as a tie-breaker guarantees
every cursor points to exactly one product.

Both created_at and id are immutable after insert, so the cursor
always points to the same "position" in the list, even if other
products are added or updated while the user is browsing.
"""

import base64
import json
from datetime import datetime
from datetime import timezone
from typing import TypedDict


class CursorData(TypedDict):
    created_at: str
    id: int


def encode_cursor(
    created_at: datetime,
    product_id: int,
) -> str:
    """
    Encode cursor values into a URL-safe Base64 string.

    Args:
        created_at: created_at of the last product on the page.
        product_id: id of the last product on the page.

    Returns:
        URL-safe Base64 string.
    """

    payload: CursorData = {
        "created_at": created_at.isoformat(),
        "id": product_id,
    }

    json_bytes = json.dumps(payload).encode()
    encoded = base64.urlsafe_b64encode(json_bytes)

    return encoded.decode()


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    """
    Decode a cursor string received from the client.

    Args:
        cursor: URL-safe Base64 cursor string.

    Returns:
        Tuple of (created_at, product_id).

    Raises:
        ValueError: If the cursor is malformed or tampered with.
    """

    try:

        decoded_bytes = base64.urlsafe_b64decode(cursor.encode())
        payload: CursorData = json.loads(decoded_bytes.decode())

        created_at = datetime.fromisoformat(payload["created_at"])

        # Ensure the datetime is timezone-aware.
        # PostgreSQL stores timestamptz as UTC; Python needs a
        # tz-aware object to compare correctly.
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        return created_at, payload["id"]

    except Exception as exc:
        raise ValueError(
            f"Invalid cursor: {exc}"
        ) from exc