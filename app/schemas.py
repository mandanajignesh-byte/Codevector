"""
Pydantic schemas.

These schemas define the request and response
models exposed by the API.

Keeping schemas separate from database models
prevents accidental exposure of internal fields
and keeps the API contract stable.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from pydantic import ConfigDict


# ==========================================================
# Product Response
# ==========================================================


class ProductResponse(BaseModel):
    """
    Represents a single product returned by the API.
    """

    id: int
    name: str
    category: str
    price: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


# ==========================================================
# Product List Response
# ==========================================================


class ProductListResponse(BaseModel):
    """
    Paginated response returned by the API.
    """

    products: list[ProductResponse]
    next_cursor: str | None
    has_more: bool


# ==========================================================
# Categories Response
# ==========================================================


class CategoriesResponse(BaseModel):
    """
    List of all available product categories.
    """

    categories: list[str]


# ==========================================================
# Simulate Updates Response
# ==========================================================


class SimulateUpdatesResponse(BaseModel):
    """
    Returned after inserting 50 new products.

    inserted: how many products were added.
    message:  human-readable explanation of what happened
              and why existing cursors are unaffected.
    """

    inserted: int
    message: str